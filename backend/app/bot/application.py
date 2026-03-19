from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import date, datetime, time

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, CallbackQuery, InlineKeyboardMarkup, MenuButtonCommands, MenuButtonWebApp, Message, ReplyKeyboardMarkup, Update, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.formatters import render_planner_handoff, render_today_dashboard, render_today_events, render_today_tasks
from app.bot.keyboards import (
    BACK_TEXT,
    CANCEL_TEXT,
    MENU_PLANNER_TEXT,
    MENU_TODAY_TEXT,
    NO_TIME_TEXT,
    TODAY_TEXT,
    add_menu_keyboard,
    event_date_keyboard,
    event_time_keyboard,
    flow_cancel_keyboard,
    main_menu_keyboard,
    planner_handoff_keyboard,
    task_date_keyboard,
    task_time_keyboard,
    today_tasks_keyboard,
)
from app.bot.states import PlannerStates
from app.config import Settings
from app.schemas.event import EventCreate
from app.schemas.inbox import InboxCreate
from app.schemas.task import TaskCreate
from app.services.dashboard import build_today_dashboard
from app.services.events import create_event, get_event
from app.services.inbox import create_inbox_item
from app.services.settings import get_settings_for_user
from app.services.tasks import complete_task, create_task, get_task
from app.services.users import ensure_user
from app.utils.datetime import today_in_timezone


@dataclass
class ChatViewState:
    summary_message_id: int | None = None
    events_message_id: int | None = None
    tasks_message_id: int | None = None
    handoff_message_id: int | None = None
    flow_message_id: int | None = None


def parse_time_input(value: str) -> time:
    return datetime.strptime(value.strip(), "%H:%M").time().replace(second=0, microsecond=0)


def parse_manual_date(value: str, today_value: date) -> date:
    cleaned = value.strip()
    for fmt in ("%d.%m.%Y", "%d.%m", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        if fmt == "%d.%m":
            candidate = date(today_value.year, parsed.month, parsed.day)
            if candidate < today_value:
                candidate = date(today_value.year + 1, parsed.month, parsed.day)
            return candidate
        return parsed.date()
    raise ValueError("Invalid date")


@dataclass
class BotApplication:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    bot: Bot | None = None
    dispatcher: Dispatcher | None = None
    polling_task: asyncio.Task | None = None
    chat_views: dict[int, ChatViewState] = field(default_factory=dict)
    user_chats: dict[int, set[int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.settings.telegram_bot_token:
            return
        self.bot = Bot(
            token=self.settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dispatcher = Dispatcher(storage=MemoryStorage())
        self.dispatcher.include_router(build_router(self))

    def register_chat(self, user_id: int, chat_id: int) -> None:
        self.user_chats.setdefault(user_id, set()).add(chat_id)
        self.chat_views.setdefault(chat_id, ChatViewState())

    def get_chat_view(self, chat_id: int) -> ChatViewState:
        return self.chat_views.setdefault(chat_id, ChatViewState())

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

    async def refresh_user_views(self, user_id: int) -> None:
        if not self.bot:
            return
        for chat_id in list(self.user_chats.get(user_id, set())):
            await self.refresh_today_view(chat_id, user_id)

    async def delete_slot(self, chat_id: int, slot: str) -> None:
        if not self.bot:
            return
        view = self.get_chat_view(chat_id)
        message_id = getattr(view, slot)
        if not message_id:
            return
        with contextlib.suppress(TelegramBadRequest, TelegramNetworkError):
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
        setattr(view, slot, None)

    async def upsert_slot(
        self,
        chat_id: int,
        slot: str,
        text: str,
        *,
        send_markup: ReplyKeyboardMarkup | InlineKeyboardMarkup | None = None,
        edit_markup: InlineKeyboardMarkup | None = None,
    ) -> int | None:
        if not self.bot:
            return None
        view = self.get_chat_view(chat_id)
        message_id = getattr(view, slot)
        if message_id:
            try:
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=edit_markup,
                )
                return message_id
            except TelegramBadRequest as exc:
                if "message is not modified" in str(exc).lower():
                    return message_id
                await self.delete_slot(chat_id, slot)
            except TelegramNetworkError:
                return message_id

        sent = await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=send_markup)
        setattr(view, slot, sent.message_id)
        return sent.message_id

    async def send_flow_prompt(self, chat_id: int, text: str, reply_markup: ReplyKeyboardMarkup) -> None:
        if not self.bot:
            return
        await self.delete_slot(chat_id, "flow_message_id")
        sent = await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        self.get_chat_view(chat_id).flow_message_id = sent.message_id

    async def send_handoff(self, chat_id: int, title: str, body: str, markup: InlineKeyboardMarkup | None = None) -> None:
        await self.upsert_slot(
            chat_id,
            "handoff_message_id",
            render_planner_handoff(title, body),
            send_markup=markup,
            edit_markup=markup,
        )

    async def refresh_today_view(self, chat_id: int, user_id: int) -> None:
        async with self.session_factory() as session:
            dashboard = await build_today_dashboard(session, user_id)

        await self.delete_slot(chat_id, "flow_message_id")
        await self.delete_slot(chat_id, "handoff_message_id")

        await self.upsert_slot(
            chat_id,
            "summary_message_id",
            render_today_dashboard(dashboard),
            send_markup=main_menu_keyboard(self.settings.effective_webapp_url),
        )

        if dashboard.events:
            await self.upsert_slot(
                chat_id,
                "events_message_id",
                render_today_events(dashboard),
            )
        else:
            await self.delete_slot(chat_id, "events_message_id")

        if dashboard.tasks or dashboard.completed_tasks or dashboard.overdue_tasks:
            tasks_markup = today_tasks_keyboard(dashboard.tasks, dashboard.overdue_tasks)
            await self.upsert_slot(
                chat_id,
                "tasks_message_id",
                render_today_tasks(dashboard),
                send_markup=tasks_markup,
                edit_markup=tasks_markup,
            )
        else:
            await self.delete_slot(chat_id, "tasks_message_id")

    async def _configure_production_bot(self) -> None:
        if not self.bot:
            return
        await self.bot.set_my_commands(
            commands=[BotCommand(command="start", description="План на сегодня")],
            scope=BotCommandScopeAllPrivateChats(),
        )
        if self.settings.effective_webapp_url and self.settings.effective_webapp_url.startswith("https://"):
            await self.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="✨ Planner",
                    web_app=WebAppInfo(url=self.settings.effective_webapp_url),
                )
            )
            return
        await self.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    async def _safe_delete_webhook(self) -> None:
        if not self.bot:
            return
        try:
            await asyncio.wait_for(self.bot.delete_webhook(drop_pending_updates=False), timeout=5)
        except (asyncio.TimeoutError, TelegramNetworkError):
            return


def build_router(bot_app: BotApplication) -> Router:
    router = Router()
    settings = bot_app.settings
    session_factory = bot_app.session_factory

    async def ensure_message_user(message: Message):
        tg_user = message.from_user
        async with session_factory() as session:
            user = await ensure_user(
                session,
                settings,
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )
        bot_app.register_chat(user.id, message.chat.id)
        return user

    async def ensure_callback_user(callback: CallbackQuery):
        tg_user = callback.from_user
        chat_id = callback.message.chat.id if callback.message else callback.from_user.id
        async with session_factory() as session:
            user = await ensure_user(
                session,
                settings,
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )
        bot_app.register_chat(user.id, chat_id)
        return user

    async def get_user_today(user_id: int) -> date:
        async with session_factory() as session:
            user_settings = await get_settings_for_user(session, user_id)
        return today_in_timezone(user_settings.timezone)

    async def finalize_task_creation(chat_id: int, user_id: int, title: str, due_date: date, due_time: time | None) -> None:
        async with session_factory() as session:
            task = await create_task(
                session,
                user_id,
                TaskCreate(title=title, due_date=due_date, due_time=due_time),
            )
        await bot_app.refresh_today_view(chat_id, user_id)
        when = due_date.strftime("%d.%m")
        if due_time:
            when = f"{when} • {due_time.strftime('%H:%M')}"
        await bot_app.send_handoff(
            chat_id,
            "🗂 Задача добавлена",
            f"{task.title}\n{when}",
            planner_handoff_keyboard(settings.effective_webapp_url),
        )

    async def finalize_event_creation(chat_id: int, user_id: int, title: str, event_date: date, start_time: time) -> None:
        async with session_factory() as session:
            event = await create_event(
                session,
                user_id,
                EventCreate(title=title, event_date=event_date, start_time=start_time),
            )
        await bot_app.refresh_today_view(chat_id, user_id)
        await bot_app.send_handoff(
            chat_id,
            "📍 Событие добавлено",
            f"{event.title}\n{event_date.strftime('%d.%m')} • {start_time.strftime('%H:%M')}",
            planner_handoff_keyboard(settings.effective_webapp_url),
        )

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        user = await ensure_message_user(message)
        await bot_app.refresh_today_view(message.chat.id, user.id)

    @router.message(StateFilter(None), F.text.in_({MENU_TODAY_TEXT, TODAY_TEXT}))
    async def today_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        await bot_app.refresh_today_view(message.chat.id, user.id)

    @router.message(StateFilter(None), F.text == "+")
    async def plus_handler(message: Message) -> None:
        await ensure_message_user(message)
        markup = add_menu_keyboard()
        await bot_app.upsert_slot(
            message.chat.id,
            "handoff_message_id",
            "Что добавить?",
            send_markup=markup,
            edit_markup=markup,
        )

    @router.message(StateFilter(None), F.text.in_({MENU_PLANNER_TEXT, "Открыть планировщик"}))
    async def open_planner_handler(message: Message) -> None:
        await ensure_message_user(message)
        if settings.effective_webapp_url:
            await bot_app.send_handoff(
                message.chat.id,
                "📲 Planner под рукой",
                f"Открывай Mini App здесь: {settings.effective_webapp_url}",
                planner_handoff_keyboard(settings.effective_webapp_url),
            )
            return
        await bot_app.upsert_slot(message.chat.id, "handoff_message_id", "📲 Planner пока недоступен. Сначала укажи WEBAPP_URL.")

    @router.message(StateFilter("*"), F.text == CANCEL_TEXT)
    async def cancel_state_handler(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        await state.clear()
        await bot_app.delete_slot(message.chat.id, "flow_message_id")
        await bot_app.refresh_today_view(message.chat.id, user.id)

    @router.callback_query(F.data == "add:task")
    async def add_task_callback(callback: CallbackQuery, state: FSMContext) -> None:
        user = await ensure_callback_user(callback)
        await state.clear()
        await state.update_data(today=(await get_user_today(user.id)).isoformat())
        await state.set_state(PlannerStates.waiting_for_task_title)
        if callback.message:
            await bot_app.delete_slot(callback.message.chat.id, "handoff_message_id")
            await bot_app.send_flow_prompt(callback.message.chat.id, "Как назвать задачу?", flow_cancel_keyboard())
        await callback.answer()

    @router.callback_query(F.data == "add:event")
    async def add_event_callback(callback: CallbackQuery, state: FSMContext) -> None:
        user = await ensure_callback_user(callback)
        await state.clear()
        await state.update_data(today=(await get_user_today(user.id)).isoformat())
        await state.set_state(PlannerStates.waiting_for_event_title)
        if callback.message:
            await bot_app.delete_slot(callback.message.chat.id, "handoff_message_id")
            await bot_app.send_flow_prompt(callback.message.chat.id, "Как назвать событие?", flow_cancel_keyboard())
        await callback.answer()

    @router.message(PlannerStates.waiting_for_task_title)
    async def task_title_flow(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        title = (message.text or "").strip()
        if not title:
            await bot_app.send_flow_prompt(message.chat.id, "Название задачи не должно быть пустым.", flow_cancel_keyboard())
            return
        await state.update_data(task_title=title, today=(await get_user_today(user.id)).isoformat())
        await state.set_state(PlannerStates.waiting_for_task_date)
        await bot_app.send_flow_prompt(
            message.chat.id,
            "На какую дату поставить задачу?\nНажми «Сегодня» или напиши дату в формате ДД.ММ.",
            task_date_keyboard(),
        )

    @router.message(PlannerStates.waiting_for_task_date, F.text == BACK_TEXT)
    async def task_date_back(message: Message, state: FSMContext) -> None:
        await ensure_message_user(message)
        await state.set_state(PlannerStates.waiting_for_task_title)
        await bot_app.send_flow_prompt(message.chat.id, "Как назвать задачу?", flow_cancel_keyboard())

    @router.message(PlannerStates.waiting_for_task_date, F.text == TODAY_TEXT)
    async def task_date_today(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        today_value = await get_user_today(user.id)
        await state.update_data(task_date=today_value.isoformat())
        await state.set_state(PlannerStates.waiting_for_task_time)
        await bot_app.send_flow_prompt(
            message.chat.id,
            "Во сколько поставить задачу?\nНажми «Без времени» или напиши время в формате ЧЧ:ММ.",
            task_time_keyboard(),
        )

    @router.message(PlannerStates.waiting_for_task_date)
    async def task_date_manual(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        today_value = await get_user_today(user.id)
        try:
            due_date = parse_manual_date(message.text or "", today_value)
        except ValueError:
            await bot_app.send_flow_prompt(
                message.chat.id,
                "Нужен формат ДД.ММ, например 20.03.",
                task_date_keyboard(),
            )
            return
        await state.update_data(task_date=due_date.isoformat())
        await state.set_state(PlannerStates.waiting_for_task_time)
        await bot_app.send_flow_prompt(
            message.chat.id,
            "Во сколько поставить задачу?\nНажми «Без времени» или напиши время в формате ЧЧ:ММ.",
            task_time_keyboard(),
        )

    @router.message(PlannerStates.waiting_for_task_time, F.text == BACK_TEXT)
    async def task_time_back(message: Message, state: FSMContext) -> None:
        await ensure_message_user(message)
        await state.set_state(PlannerStates.waiting_for_task_date)
        await bot_app.send_flow_prompt(
            message.chat.id,
            "На какую дату поставить задачу?\nНажми «Сегодня» или напиши дату в формате ДД.ММ.",
            task_date_keyboard(),
        )

    @router.message(PlannerStates.waiting_for_task_time, F.text == NO_TIME_TEXT)
    async def task_time_none(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        data = await state.get_data()
        await state.clear()
        await bot_app.delete_slot(message.chat.id, "flow_message_id")
        await finalize_task_creation(
            message.chat.id,
            user.id,
            data["task_title"],
            date.fromisoformat(data["task_date"]),
            None,
        )

    @router.message(PlannerStates.waiting_for_task_time)
    async def task_time_manual(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        try:
            due_time = parse_time_input(message.text or "")
        except ValueError:
            await bot_app.send_flow_prompt(
                message.chat.id,
                "Нужен формат ЧЧ:ММ, например 14:30. Или нажми «Без времени».",
                task_time_keyboard(),
            )
            return
        data = await state.get_data()
        await state.clear()
        await bot_app.delete_slot(message.chat.id, "flow_message_id")
        await finalize_task_creation(
            message.chat.id,
            user.id,
            data["task_title"],
            date.fromisoformat(data["task_date"]),
            due_time,
        )

    @router.message(PlannerStates.waiting_for_event_title)
    async def event_title_flow(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        title = (message.text or "").strip()
        if not title:
            await bot_app.send_flow_prompt(message.chat.id, "Название события не должно быть пустым.", flow_cancel_keyboard())
            return
        await state.update_data(event_title=title, today=(await get_user_today(user.id)).isoformat())
        await state.set_state(PlannerStates.waiting_for_event_date)
        await bot_app.send_flow_prompt(
            message.chat.id,
            "На какую дату поставить событие?\nНажми «Сегодня» или напиши дату в формате ДД.ММ.",
            event_date_keyboard(),
        )

    @router.message(PlannerStates.waiting_for_event_date, F.text == BACK_TEXT)
    async def event_date_back(message: Message, state: FSMContext) -> None:
        await ensure_message_user(message)
        await state.set_state(PlannerStates.waiting_for_event_title)
        await bot_app.send_flow_prompt(message.chat.id, "Как назвать событие?", flow_cancel_keyboard())

    @router.message(PlannerStates.waiting_for_event_date, F.text == TODAY_TEXT)
    async def event_date_today(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        today_value = await get_user_today(user.id)
        await state.update_data(event_date=today_value.isoformat())
        await state.set_state(PlannerStates.waiting_for_event_time)
        await bot_app.send_flow_prompt(
            message.chat.id,
            "Во сколько начинается событие?\nНапиши время в формате ЧЧ:ММ.",
            event_time_keyboard(),
        )

    @router.message(PlannerStates.waiting_for_event_date)
    async def event_date_manual(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        today_value = await get_user_today(user.id)
        try:
            event_date = parse_manual_date(message.text or "", today_value)
        except ValueError:
            await bot_app.send_flow_prompt(
                message.chat.id,
                "Нужен формат ДД.ММ, например 20.03.",
                event_date_keyboard(),
            )
            return
        await state.update_data(event_date=event_date.isoformat())
        await state.set_state(PlannerStates.waiting_for_event_time)
        await bot_app.send_flow_prompt(
            message.chat.id,
            "Во сколько начинается событие?\nНапиши время в формате ЧЧ:ММ.",
            event_time_keyboard(),
        )

    @router.message(PlannerStates.waiting_for_event_time, F.text == BACK_TEXT)
    async def event_time_back(message: Message, state: FSMContext) -> None:
        await ensure_message_user(message)
        await state.set_state(PlannerStates.waiting_for_event_date)
        await bot_app.send_flow_prompt(
            message.chat.id,
            "На какую дату поставить событие?\nНажми «Сегодня» или напиши дату в формате ДД.ММ.",
            event_date_keyboard(),
        )

    @router.message(PlannerStates.waiting_for_event_time)
    async def event_time_manual(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        try:
            start_time = parse_time_input(message.text or "")
        except ValueError:
            await bot_app.send_flow_prompt(
                message.chat.id,
                "Нужен формат ЧЧ:ММ, например 14:30.",
                event_time_keyboard(),
            )
            return
        data = await state.get_data()
        await state.clear()
        await bot_app.delete_slot(message.chat.id, "flow_message_id")
        await finalize_event_creation(
            message.chat.id,
            user.id,
            data["event_title"],
            date.fromisoformat(data["event_date"]),
            start_time,
        )

    @router.callback_query(F.data.startswith("task:"))
    async def task_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
        _, action, raw_id = (callback.data or "").split(":")
        task_id = int(raw_id)
        user = await ensure_callback_user(callback)
        chat_id = callback.message.chat.id if callback.message else callback.from_user.id

        async with session_factory() as session:
            task = await get_task(session, user.id, task_id)
            if task is None:
                await callback.answer("Задача не найдена", show_alert=True)
                return
            if action == "complete":
                await complete_task(session, task)
            else:
                await bot_app.send_handoff(
                    chat_id,
                    "🗂 Управление задачей — в Planner",
                    "Перенос, удаление и все правки теперь делаются в Mini App.",
                    planner_handoff_keyboard(settings.effective_webapp_url),
                )
                await callback.answer()
                return

        await state.clear()
        await bot_app.refresh_today_view(chat_id, user.id)
        await callback.answer("Выполнено")

    @router.callback_query(F.data.startswith("event:"))
    async def event_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
        _, _, raw_id = (callback.data or "").split(":")
        event_id = int(raw_id)
        user = await ensure_callback_user(callback)
        async with session_factory() as session:
            event = await get_event(session, user.id, event_id)
            if event is None:
                await callback.answer("Событие не найдено", show_alert=True)
                return

        await state.clear()
        if callback.message:
            await bot_app.send_handoff(
                callback.message.chat.id,
                "📍 Управление событием — в Planner",
                "Перенос, удаление и редактирование событий теперь делаются в Mini App.",
                planner_handoff_keyboard(settings.effective_webapp_url),
            )
        await callback.answer()

    @router.message(StateFilter(None), F.text)
    async def free_text_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        text = (message.text or "").strip()
        if not text:
            return
        async with session_factory() as session:
            await create_inbox_item(session, user.id, InboxCreate(text=text))
        preview = text if len(text) <= 90 else f"{text[:87]}..."
        await bot_app.send_handoff(
            message.chat.id,
            "📝 Сохранено в заметки",
            preview,
            planner_handoff_keyboard(settings.effective_webapp_url),
        )

    return router
