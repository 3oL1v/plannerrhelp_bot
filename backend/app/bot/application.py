from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, CallbackQuery, MenuButtonCommands, MenuButtonWebApp, Message, Update, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.formatters import help_text, render_inbox, render_settings, render_today_dashboard
from app.bot.keyboards import (
    BACK_TEXT,
    CANCEL_TEXT,
    CUSTOM_DATE_TEXT,
    CUSTOM_DURATION_TEXT,
    CUSTOM_TIME_TEXT,
    EVENT_DURATION_OPTIONS,
    EVENT_TIME_OPTIONS,
    NO_DATE_TEXT,
    NO_TIME_TEXT,
    TASK_TIME_OPTIONS,
    TODAY_TEXT,
    TOMORROW_TEXT,
    add_menu_keyboard,
    event_date_keyboard,
    event_duration_keyboard,
    event_time_keyboard,
    flow_cancel_keyboard,
    main_menu_keyboard,
    manual_input_keyboard,
    settings_keyboard,
    today_actions_keyboard,
    task_date_keyboard,
    task_time_keyboard,
)
from app.bot.states import PlannerStates
from app.config import Settings
from app.schemas.event import EventCreate, EventReschedule
from app.schemas.inbox import InboxCreate
from app.schemas.settings import UserSettingsUpdate
from app.schemas.task import TaskCreate, TaskReschedule
from app.services.dashboard import build_today_dashboard
from app.services.events import create_event, delete_event, get_event, reschedule_event
from app.services.inbox import create_inbox_item, list_inbox
from app.services.settings import get_settings_for_user, update_settings_for_user
from app.services.tasks import complete_task, create_task, delete_task, get_task, reschedule_task
from app.services.users import ensure_user
from app.utils.datetime import today_in_timezone


def parse_time_input(value: str) -> time:
    return datetime.strptime(value.strip(), "%H:%M").time().replace(second=0, microsecond=0)


def parse_date_input(value: str) -> date:
    return date.fromisoformat(value.strip())


def parse_duration_input(value: str) -> int:
    cleaned = value.strip().lower().replace("мин", "").strip()
    duration = int(cleaned)
    if duration <= 0:
        raise ValueError("Duration must be positive")
    return duration


def parse_reschedule_input(text: str) -> tuple[date, time]:
    parsed = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M")
    return parsed.date(), parsed.time().replace(second=0, microsecond=0)


def build_event_end_time(start_time: time, duration_minutes: int) -> time:
    start_dt = datetime.combine(date.today(), start_time)
    return (start_dt + timedelta(minutes=duration_minutes)).time().replace(second=0, microsecond=0)


def get_today_value(settings: Settings, data: dict) -> date:
    return today_in_timezone(data.get("timezone") or settings.default_timezone)


def build_task_payload(data: dict) -> TaskCreate:
    due_date = parse_date_input(data["due_date"]) if data.get("due_date") else None
    due_time = parse_time_input(data["due_time"]) if data.get("due_time") else None
    return TaskCreate(
        title=data["title"],
        due_date=due_date,
        due_time=due_time,
    )


def build_event_payload(data: dict) -> EventCreate:
    event_date = parse_date_input(data["event_date"])
    start_time = parse_time_input(data["start_time"])
    duration_minutes = int(data["duration_minutes"])
    return EventCreate(
        title=data["title"],
        event_date=event_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
        end_time=build_event_end_time(start_time, duration_minutes),
    )


def format_task_creation_message(task, today: date) -> str:
    lines = [f"Задача создана: {task.title}"]
    if task.due_date:
        when = task.due_date.isoformat()
        if task.due_time:
            when += f" {task.due_time.strftime('%H:%M')}"
        lines.append(f"Срок: {when}")
        if task.due_date != today:
            lines.append(f"Она не появится в разделе «Сегодня», потому что сегодня {today.isoformat()}.")
    else:
        lines.append("Срок не задан.")
    return "\n".join(lines)


def format_event_creation_message(event, today: date) -> str:
    lines = [
        f"Событие создано: {event.title}",
        f"Слот: {event.event_date.isoformat()} {event.start_time.strftime('%H:%M')}",
    ]
    if event.event_date != today:
        lines.append(f"Оно не появится в разделе «Сегодня», потому что сегодня {today.isoformat()}.")
    return "\n".join(lines)


@dataclass
class BotApplication:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    bot: Bot | None = None
    dispatcher: Dispatcher | None = None
    polling_task: asyncio.Task | None = None

    def __post_init__(self) -> None:
        if not self.settings.telegram_bot_token:
            return
        self.bot = Bot(
            token=self.settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dispatcher = Dispatcher(storage=MemoryStorage())
        self.dispatcher.include_router(build_router(self.settings, self.session_factory))

    async def start(self) -> None:
        if not self.bot or not self.dispatcher:
            return
        if self.settings.is_production and self.settings.webhook_url:
            await self._configure_production_bot()
            await self.bot.set_webhook(
                self.settings.webhook_url,
                allowed_updates=self.dispatcher.resolve_used_update_types(),
            )
        elif self.settings.telegram_use_polling:
            await self._safe_delete_webhook()
            self.polling_task = asyncio.create_task(
                self.dispatcher.start_polling(
                    self.bot,
                    allowed_updates=self.dispatcher.resolve_used_update_types(),
                )
            )

    async def stop(self) -> None:
        if not self.bot:
            return
        if self.polling_task:
            self.polling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.polling_task
        if not self.settings.is_production:
            await self._safe_delete_webhook()
        await self.bot.session.close()

    async def process_update(self, update: Update) -> None:
        if not self.bot or not self.dispatcher:
            return
        await self.dispatcher.feed_update(self.bot, update)

    async def send_message(self, telegram_id: int, text: str) -> None:
        if not self.bot:
            return
        try:
            await self.bot.send_message(telegram_id, text)
        except TelegramBadRequest:
            return

    async def _configure_production_bot(self) -> None:
        if not self.bot:
            return
        await self.bot.set_my_commands(
            commands=[
                BotCommand(command="start", description="Open planner menu"),
            ],
            scope=BotCommandScopeAllPrivateChats(),
        )
        if self.settings.effective_webapp_url and self.settings.effective_webapp_url.startswith("https://"):
            await self.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Open Planner",
                    web_app=WebAppInfo(url=self.settings.effective_webapp_url),
                )
            )
            return
        await self.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    async def _safe_delete_webhook(self) -> None:
        if not self.bot:
            return
        try:
            await asyncio.wait_for(
                self.bot.delete_webhook(drop_pending_updates=False),
                timeout=5,
            )
        except (asyncio.TimeoutError, TelegramNetworkError):
            return


def build_router(settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> Router:
    router = Router()

    def menu_keyboard():
        return main_menu_keyboard(settings.effective_webapp_url)

    async def ensure_message_user(message: Message):
        tg_user = message.from_user
        async with session_factory() as session:
            return await ensure_user(
                session,
                settings,
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )

    async def ensure_callback_user(callback: CallbackQuery):
        tg_user = callback.from_user
        async with session_factory() as session:
            return await ensure_user(
                session,
                settings,
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )

    async def get_user_timezone(user_id: int) -> str:
        async with session_factory() as session:
            user_settings = await get_settings_for_user(session, user_id)
        return user_settings.timezone

    async def send_today(message: Message, user_id: int) -> None:
        async with session_factory() as session:
            dashboard = await build_today_dashboard(session, user_id)
        action_keyboard = today_actions_keyboard(dashboard.tasks[:5], dashboard.overdue_tasks[:5])
        await message.answer(render_today_dashboard(dashboard), reply_markup=action_keyboard)

    async def prompt_task_title(message: Message) -> None:
        await message.answer("Как назвать задачу?", reply_markup=flow_cancel_keyboard())

    async def prompt_task_date(message: Message) -> None:
        await message.answer("Когда поставить задачу?", reply_markup=task_date_keyboard())

    async def prompt_task_custom_date(message: Message) -> None:
        await message.answer("Введи дату в формате YYYY-MM-DD", reply_markup=manual_input_keyboard())

    async def prompt_task_time(message: Message) -> None:
        await message.answer("Во сколько напомнить о задаче?", reply_markup=task_time_keyboard())

    async def prompt_task_custom_time(message: Message) -> None:
        await message.answer("Введи время в формате HH:MM", reply_markup=manual_input_keyboard())

    async def prompt_event_title(message: Message) -> None:
        await message.answer("Как назвать событие?", reply_markup=flow_cancel_keyboard())

    async def prompt_event_date(message: Message) -> None:
        await message.answer("На какую дату поставить событие?", reply_markup=event_date_keyboard())

    async def prompt_event_custom_date(message: Message) -> None:
        await message.answer("Введи дату события в формате YYYY-MM-DD", reply_markup=manual_input_keyboard())

    async def prompt_event_time(message: Message) -> None:
        await message.answer("Во сколько начинается событие?", reply_markup=event_time_keyboard())

    async def prompt_event_custom_time(message: Message) -> None:
        await message.answer("Введи время начала в формате HH:MM", reply_markup=manual_input_keyboard())

    async def prompt_event_duration(message: Message) -> None:
        await message.answer("Сколько длится событие?", reply_markup=event_duration_keyboard())

    async def prompt_event_custom_duration(message: Message) -> None:
        await message.answer("Введи длительность в минутах, например 45", reply_markup=manual_input_keyboard())

    async def complete_task_creation(message: Message, state: FSMContext, user_id: int) -> None:
        data = await state.get_data()
        payload = build_task_payload(data)
        async with session_factory() as session:
            task = await create_task(session, user_id, payload)
        await state.clear()
        today = today_in_timezone(data.get("timezone") or settings.default_timezone)
        await message.answer(format_task_creation_message(task, today), reply_markup=menu_keyboard())

    async def complete_event_creation(message: Message, state: FSMContext, user_id: int) -> None:
        data = await state.get_data()
        payload = build_event_payload(data)
        async with session_factory() as session:
            event = await create_event(session, user_id, payload)
        await state.clear()
        today = today_in_timezone(data.get("timezone") or settings.default_timezone)
        await message.answer(format_event_creation_message(event, today), reply_markup=menu_keyboard())

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        user = await ensure_message_user(message)
        await message.answer(
            "Планировщик подключен.",
            reply_markup=menu_keyboard(),
        )
        await send_today(message, user.id)

    @router.message(StateFilter(None), F.text == "Сегодня")
    async def today_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        await send_today(message, user.id)

    @router.message(StateFilter(None), F.text == "+")
    async def plus_handler(message: Message) -> None:
        await ensure_message_user(message)
        await message.answer("Что добавить?", reply_markup=add_menu_keyboard())

    @router.message(StateFilter(None), F.text == "Входящие")
    async def inbox_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        async with session_factory() as session:
            items = await list_inbox(session, user.id)
        await message.answer(render_inbox(items), reply_markup=menu_keyboard())

    @router.message(StateFilter(None), F.text == "Настройки")
    async def settings_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        async with session_factory() as session:
            user_settings = await get_settings_for_user(session, user.id)
        await message.answer(
            render_settings(user_settings),
            reply_markup=settings_keyboard(user_settings.morning_digest_enabled, user_settings.notifications_enabled),
        )

    @router.message(StateFilter(None), F.text == "Помощь")
    async def help_handler(message: Message) -> None:
        await ensure_message_user(message)
        await message.answer(help_text(settings.effective_webapp_url), reply_markup=menu_keyboard())

    @router.message(StateFilter(None), F.text == "Открыть планировщик")
    async def open_planner_handler(message: Message) -> None:
        await ensure_message_user(message)
        if settings.effective_webapp_url and settings.effective_webapp_url.startswith("https://"):
            await message.answer(f"Открой Mini App: {settings.effective_webapp_url}", reply_markup=menu_keyboard())
            return
        await message.answer(
            "Локально Mini App доступен как сайт: http://127.0.0.1:8000\n"
            "Внутри Telegram Mini App открывается только по https.",
            reply_markup=menu_keyboard(),
        )

    @router.message(StateFilter("*"), F.text == CANCEL_TEXT)
    async def cancel_state_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=menu_keyboard())

    @router.callback_query(F.data == "add:task")
    async def add_task_callback(callback: CallbackQuery, state: FSMContext) -> None:
        user = await ensure_callback_user(callback)
        timezone = await get_user_timezone(user.id)
        await state.clear()
        await state.update_data(flow="task", timezone=timezone)
        await state.set_state(PlannerStates.waiting_for_task_title)
        await prompt_task_title(callback.message)
        await callback.answer()

    @router.callback_query(F.data == "add:event")
    async def add_event_callback(callback: CallbackQuery, state: FSMContext) -> None:
        user = await ensure_callback_user(callback)
        timezone = await get_user_timezone(user.id)
        await state.clear()
        await state.update_data(flow="event", timezone=timezone)
        await state.set_state(PlannerStates.waiting_for_event_title)
        await prompt_event_title(callback.message)
        await callback.answer()

    @router.callback_query(F.data == "add:note")
    async def add_note_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_quick_note)
        await callback.message.answer("Отправь текст для входящих.", reply_markup=flow_cancel_keyboard())
        await callback.answer()

    @router.message(PlannerStates.waiting_for_task_title)
    async def task_title_flow(message: Message, state: FSMContext) -> None:
        title = (message.text or "").strip()
        if not title:
            await message.answer("Название задачи не должно быть пустым.", reply_markup=flow_cancel_keyboard())
            return
        await state.update_data(title=title, due_date=None, due_time=None)
        await state.set_state(PlannerStates.waiting_for_task_date)
        await prompt_task_date(message)

    @router.message(PlannerStates.waiting_for_task_date, F.text == BACK_TEXT)
    async def back_from_task_date(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_task_title)
        await prompt_task_title(message)

    @router.message(PlannerStates.waiting_for_task_date, F.text == TODAY_TEXT)
    async def task_date_today(message: Message, state: FSMContext) -> None:
        state_data = await state.get_data()
        await state.update_data(due_date=get_today_value(settings, state_data).isoformat(), due_time=None)
        await state.set_state(PlannerStates.waiting_for_task_time)
        await prompt_task_time(message)

    @router.message(PlannerStates.waiting_for_task_date, F.text == TOMORROW_TEXT)
    async def task_date_tomorrow(message: Message, state: FSMContext) -> None:
        state_data = await state.get_data()
        tomorrow = get_today_value(settings, state_data) + timedelta(days=1)
        await state.update_data(due_date=tomorrow.isoformat(), due_time=None)
        await state.set_state(PlannerStates.waiting_for_task_time)
        await prompt_task_time(message)

    @router.message(PlannerStates.waiting_for_task_date, F.text == NO_DATE_TEXT)
    async def task_without_date(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        await state.update_data(due_date=None, due_time=None)
        await complete_task_creation(message, state, user.id)

    @router.message(PlannerStates.waiting_for_task_date, F.text == CUSTOM_DATE_TEXT)
    async def task_custom_date_prompt(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_task_custom_date)
        await prompt_task_custom_date(message)

    @router.message(PlannerStates.waiting_for_task_date)
    async def task_date_invalid(message: Message) -> None:
        await message.answer("Выбери дату кнопкой или нажми «Ввести свою».", reply_markup=task_date_keyboard())

    @router.message(PlannerStates.waiting_for_task_custom_date, F.text == BACK_TEXT)
    async def back_from_task_custom_date(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_task_date)
        await prompt_task_date(message)

    @router.message(PlannerStates.waiting_for_task_custom_date)
    async def task_custom_date_flow(message: Message, state: FSMContext) -> None:
        try:
            parsed_date = parse_date_input(message.text or "")
        except ValueError:
            await message.answer("Нужен формат YYYY-MM-DD, например 2026-03-17.", reply_markup=manual_input_keyboard())
            return
        await state.update_data(due_date=parsed_date.isoformat(), due_time=None)
        await state.set_state(PlannerStates.waiting_for_task_time)
        await prompt_task_time(message)

    @router.message(PlannerStates.waiting_for_task_time, F.text == BACK_TEXT)
    async def back_from_task_time(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_task_date)
        await prompt_task_date(message)

    @router.message(PlannerStates.waiting_for_task_time, F.text.in_(TASK_TIME_OPTIONS))
    async def task_time_quick(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        await state.update_data(due_time=message.text)
        await complete_task_creation(message, state, user.id)

    @router.message(PlannerStates.waiting_for_task_time, F.text == NO_TIME_TEXT)
    async def task_without_time(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        await state.update_data(due_time=None)
        await complete_task_creation(message, state, user.id)

    @router.message(PlannerStates.waiting_for_task_time, F.text == CUSTOM_TIME_TEXT)
    async def task_custom_time_prompt(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_task_custom_time)
        await prompt_task_custom_time(message)

    @router.message(PlannerStates.waiting_for_task_time)
    async def task_time_invalid(message: Message) -> None:
        await message.answer("Выбери время кнопкой или нажми «Ввести свое».", reply_markup=task_time_keyboard())

    @router.message(PlannerStates.waiting_for_task_custom_time, F.text == BACK_TEXT)
    async def back_from_task_custom_time(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_task_time)
        await prompt_task_time(message)

    @router.message(PlannerStates.waiting_for_task_custom_time)
    async def task_custom_time_flow(message: Message, state: FSMContext) -> None:
        try:
            parsed_time = parse_time_input(message.text or "")
        except ValueError:
            await message.answer("Нужен формат HH:MM, например 19:00.", reply_markup=manual_input_keyboard())
            return
        user = await ensure_message_user(message)
        await state.update_data(due_time=parsed_time.strftime("%H:%M"))
        await complete_task_creation(message, state, user.id)

    @router.message(PlannerStates.waiting_for_event_title)
    async def event_title_flow(message: Message, state: FSMContext) -> None:
        title = (message.text or "").strip()
        if not title:
            await message.answer("Название события не должно быть пустым.", reply_markup=flow_cancel_keyboard())
            return
        await state.update_data(title=title, event_date=None, start_time=None, duration_minutes=None)
        await state.set_state(PlannerStates.waiting_for_event_date)
        await prompt_event_date(message)

    @router.message(PlannerStates.waiting_for_event_date, F.text == BACK_TEXT)
    async def back_from_event_date(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event_title)
        await prompt_event_title(message)

    @router.message(PlannerStates.waiting_for_event_date, F.text == TODAY_TEXT)
    async def event_date_today(message: Message, state: FSMContext) -> None:
        state_data = await state.get_data()
        await state.update_data(event_date=get_today_value(settings, state_data).isoformat(), start_time=None, duration_minutes=None)
        await state.set_state(PlannerStates.waiting_for_event_time)
        await prompt_event_time(message)

    @router.message(PlannerStates.waiting_for_event_date, F.text == TOMORROW_TEXT)
    async def event_date_tomorrow(message: Message, state: FSMContext) -> None:
        state_data = await state.get_data()
        tomorrow = get_today_value(settings, state_data) + timedelta(days=1)
        await state.update_data(event_date=tomorrow.isoformat(), start_time=None, duration_minutes=None)
        await state.set_state(PlannerStates.waiting_for_event_time)
        await prompt_event_time(message)

    @router.message(PlannerStates.waiting_for_event_date, F.text == CUSTOM_DATE_TEXT)
    async def event_custom_date_prompt(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event_custom_date)
        await prompt_event_custom_date(message)

    @router.message(PlannerStates.waiting_for_event_date)
    async def event_date_invalid(message: Message) -> None:
        await message.answer("Выбери дату кнопкой или нажми «Ввести свою».", reply_markup=event_date_keyboard())

    @router.message(PlannerStates.waiting_for_event_custom_date, F.text == BACK_TEXT)
    async def back_from_event_custom_date(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event_date)
        await prompt_event_date(message)

    @router.message(PlannerStates.waiting_for_event_custom_date)
    async def event_custom_date_flow(message: Message, state: FSMContext) -> None:
        try:
            parsed_date = parse_date_input(message.text or "")
        except ValueError:
            await message.answer("Нужен формат YYYY-MM-DD, например 2026-03-17.", reply_markup=manual_input_keyboard())
            return
        await state.update_data(event_date=parsed_date.isoformat(), start_time=None, duration_minutes=None)
        await state.set_state(PlannerStates.waiting_for_event_time)
        await prompt_event_time(message)

    @router.message(PlannerStates.waiting_for_event_time, F.text == BACK_TEXT)
    async def back_from_event_time(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event_date)
        await prompt_event_date(message)

    @router.message(PlannerStates.waiting_for_event_time, F.text.in_(EVENT_TIME_OPTIONS))
    async def event_time_quick(message: Message, state: FSMContext) -> None:
        await state.update_data(start_time=message.text, duration_minutes=None)
        await state.set_state(PlannerStates.waiting_for_event_duration)
        await prompt_event_duration(message)

    @router.message(PlannerStates.waiting_for_event_time, F.text == CUSTOM_TIME_TEXT)
    async def event_custom_time_prompt(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event_custom_time)
        await prompt_event_custom_time(message)

    @router.message(PlannerStates.waiting_for_event_time)
    async def event_time_invalid(message: Message) -> None:
        await message.answer("Выбери время кнопкой или нажми «Ввести свое».", reply_markup=event_time_keyboard())

    @router.message(PlannerStates.waiting_for_event_custom_time, F.text == BACK_TEXT)
    async def back_from_event_custom_time(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event_time)
        await prompt_event_time(message)

    @router.message(PlannerStates.waiting_for_event_custom_time)
    async def event_custom_time_flow(message: Message, state: FSMContext) -> None:
        try:
            parsed_time = parse_time_input(message.text or "")
        except ValueError:
            await message.answer("Нужен формат HH:MM, например 19:00.", reply_markup=manual_input_keyboard())
            return
        await state.update_data(start_time=parsed_time.strftime("%H:%M"), duration_minutes=None)
        await state.set_state(PlannerStates.waiting_for_event_duration)
        await prompt_event_duration(message)

    @router.message(PlannerStates.waiting_for_event_duration, F.text == BACK_TEXT)
    async def back_from_event_duration(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event_time)
        await prompt_event_time(message)

    @router.message(PlannerStates.waiting_for_event_duration, F.text.in_(EVENT_DURATION_OPTIONS))
    async def event_duration_quick(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        duration = parse_duration_input(message.text or "")
        await state.update_data(duration_minutes=str(duration))
        await complete_event_creation(message, state, user.id)

    @router.message(PlannerStates.waiting_for_event_duration, F.text == CUSTOM_DURATION_TEXT)
    async def event_custom_duration_prompt(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event_custom_duration)
        await prompt_event_custom_duration(message)

    @router.message(PlannerStates.waiting_for_event_duration)
    async def event_duration_invalid(message: Message) -> None:
        await message.answer("Выбери длительность кнопкой или нажми «Ввести свою».", reply_markup=event_duration_keyboard())

    @router.message(PlannerStates.waiting_for_event_custom_duration, F.text == BACK_TEXT)
    async def back_from_event_custom_duration(message: Message, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event_duration)
        await prompt_event_duration(message)

    @router.message(PlannerStates.waiting_for_event_custom_duration)
    async def event_custom_duration_flow(message: Message, state: FSMContext) -> None:
        try:
            duration = parse_duration_input(message.text or "")
        except ValueError:
            await message.answer("Нужно целое число минут, например 45.", reply_markup=manual_input_keyboard())
            return
        user = await ensure_message_user(message)
        await state.update_data(duration_minutes=str(duration))
        await complete_event_creation(message, state, user.id)

    @router.message(PlannerStates.waiting_for_quick_note)
    async def quick_note_flow(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        async with session_factory() as session:
            item = await create_inbox_item(session, user.id, InboxCreate(text=message.text or ""))
        await state.clear()
        await message.answer(f"Сохранено во входящие #{item.id}", reply_markup=menu_keyboard())

    @router.callback_query(F.data.startswith("task:"))
    async def task_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
        _, action, raw_id = (callback.data or "").split(":")
        task_id = int(raw_id)
        user = await ensure_callback_user(callback)
        async with session_factory() as session:
            task = await get_task(session, user.id, task_id)
            if task is None:
                await callback.answer("Задача не найдена", show_alert=True)
                return
            if action == "complete":
                await complete_task(session, task)
                await callback.message.answer("Задача выполнена.", reply_markup=menu_keyboard())
            elif action == "delete":
                await delete_task(session, task)
                await callback.message.answer("Задача удалена.", reply_markup=menu_keyboard())
            elif action == "reschedule":
                await state.set_state(PlannerStates.waiting_for_reschedule)
                await state.update_data(entity="task", entity_id=task_id)
                await callback.message.answer("Новая дата: YYYY-MM-DD HH:MM", reply_markup=flow_cancel_keyboard())
        await callback.answer()

    @router.callback_query(F.data.startswith("event:"))
    async def event_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
        _, action, raw_id = (callback.data or "").split(":")
        event_id = int(raw_id)
        user = await ensure_callback_user(callback)
        async with session_factory() as session:
            event = await get_event(session, user.id, event_id)
            if event is None:
                await callback.answer("Событие не найдено", show_alert=True)
                return
            if action == "delete":
                await delete_event(session, event)
                await callback.message.answer("Событие удалено.", reply_markup=menu_keyboard())
            elif action == "reschedule":
                await state.set_state(PlannerStates.waiting_for_reschedule)
                await state.update_data(entity="event", entity_id=event_id)
                await callback.message.answer("Новая дата: YYYY-MM-DD HH:MM", reply_markup=flow_cancel_keyboard())
        await callback.answer()

    @router.callback_query(F.data.startswith("settings:"))
    async def settings_callbacks(callback: CallbackQuery) -> None:
        user = await ensure_callback_user(callback)
        async with session_factory() as session:
            user_settings = await get_settings_for_user(session, user.id)
            if callback.data == "settings:toggle_digest":
                payload = UserSettingsUpdate(morning_digest_enabled=not user_settings.morning_digest_enabled)
            else:
                payload = UserSettingsUpdate(notifications_enabled=not user_settings.notifications_enabled)
            updated = await update_settings_for_user(session, user.id, payload)
        await callback.message.answer(
            render_settings(updated),
            reply_markup=settings_keyboard(updated.morning_digest_enabled, updated.notifications_enabled),
        )
        await callback.answer()

    @router.message(PlannerStates.waiting_for_reschedule)
    async def reschedule_flow(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        state_data = await state.get_data()
        entity = state_data.get("entity")
        entity_id = state_data.get("entity_id")
        try:
            new_date, new_time = parse_reschedule_input(message.text or "")
        except ValueError:
            await message.answer("Нужен формат YYYY-MM-DD HH:MM", reply_markup=flow_cancel_keyboard())
            return
        async with session_factory() as session:
            if entity == "task":
                task = await get_task(session, user.id, int(entity_id))
                if task:
                    await reschedule_task(session, task, TaskReschedule(due_date=new_date, due_time=new_time))
                    await message.answer("Задача перенесена.", reply_markup=menu_keyboard())
            elif entity == "event":
                event = await get_event(session, user.id, int(entity_id))
                if event:
                    await reschedule_event(session, event, EventReschedule(event_date=new_date, start_time=new_time))
                    await message.answer("Событие перенесено.", reply_markup=menu_keyboard())
        await state.clear()

    @router.message(F.text)
    async def free_text_handler(message: Message, state: FSMContext) -> None:
        if await state.get_state():
            return
        user = await ensure_message_user(message)
        async with session_factory() as session:
            item = await create_inbox_item(session, user.id, InboxCreate(text=message.text))
        await message.answer(f"Сохранил во входящие #{item.id}", reply_markup=menu_keyboard())

    return router
