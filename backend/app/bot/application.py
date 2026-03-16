from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.formatters import help_text, render_event, render_inbox, render_settings, render_task, render_today_dashboard
from app.bot.keyboards import add_menu_keyboard, event_actions_keyboard, main_menu_keyboard, settings_keyboard, task_actions_keyboard
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


def parse_task_input(text: str) -> TaskCreate:
    parts = [part.strip() for part in text.split("|")]
    title = parts[0]
    due_date = None
    due_time = None
    if len(parts) > 1 and parts[1]:
        parsed = datetime.strptime(parts[1], "%Y-%m-%d %H:%M")
        due_date = parsed.date()
        due_time = parsed.time().replace(second=0, microsecond=0)
    return TaskCreate(title=title, due_date=due_date, due_time=due_time)


def parse_event_input(text: str) -> EventCreate:
    parts = [part.strip() for part in text.split("|")]
    title = parts[0]
    parsed = datetime.strptime(parts[1], "%Y-%m-%d %H:%M")
    duration = int(parts[2]) if len(parts) > 2 and parts[2] else None
    end_time = None
    if duration:
        end_time = (parsed + timedelta(minutes=duration)).time().replace(second=0, microsecond=0)
    return EventCreate(
        title=title,
        event_date=parsed.date(),
        start_time=parsed.time().replace(second=0, microsecond=0),
        duration_minutes=duration,
        end_time=end_time,
    )


def parse_reschedule_input(text: str) -> tuple:
    parsed = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M")
    return parsed.date(), parsed.time().replace(second=0, microsecond=0)


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
            await self.bot.set_webhook(self.settings.webhook_url)
        elif self.settings.telegram_use_polling:
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
        if self.settings.is_production:
            await self.bot.delete_webhook(drop_pending_updates=False)
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


def build_router(settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> Router:
    router = Router()

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

    async def send_today(message: Message, user_id: int) -> None:
        async with session_factory() as session:
            dashboard = await build_today_dashboard(session, user_id)
        await message.answer(render_today_dashboard(dashboard))
        for event in dashboard.events[:5]:
            await message.answer(render_event(event), reply_markup=event_actions_keyboard(event.id))
        for task in dashboard.tasks[:5]:
            await message.answer(render_task(task), reply_markup=task_actions_keyboard(task.id))
        for task in dashboard.overdue_tasks[:5]:
            await message.answer(f"Просрочено: {render_task(task)}", reply_markup=task_actions_keyboard(task.id))

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        await message.answer(
            "Планировщик подключен.",
            reply_markup=main_menu_keyboard(settings.effective_webapp_url),
        )
        await send_today(message, user.id)

    @router.message(F.text == "Сегодня")
    async def today_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        await send_today(message, user.id)

    @router.message(F.text == "+")
    async def plus_handler(message: Message) -> None:
        await ensure_message_user(message)
        await message.answer("Что добавить?", reply_markup=add_menu_keyboard())

    @router.message(F.text == "Входящие")
    async def inbox_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        async with session_factory() as session:
            items = await list_inbox(session, user.id)
        await message.answer(render_inbox(items))

    @router.message(F.text == "Настройки")
    async def settings_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        async with session_factory() as session:
            user_settings = await get_settings_for_user(session, user.id)
        await message.answer(
            render_settings(user_settings),
            reply_markup=settings_keyboard(user_settings.morning_digest_enabled, user_settings.notifications_enabled),
        )

    @router.message(F.text == "Помощь")
    async def help_handler(message: Message) -> None:
        await ensure_message_user(message)
        await message.answer(help_text(settings.effective_webapp_url))

    @router.message(F.text == "Открыть планировщик")
    async def open_planner_handler(message: Message) -> None:
        await ensure_message_user(message)
        if settings.effective_webapp_url and settings.effective_webapp_url.startswith("https://"):
            await message.answer(f"Открой Mini App: {settings.effective_webapp_url}")
            return
        await message.answer(
            "Локально Mini App доступен как сайт: http://127.0.0.1:8000\n"
            "Внутри Telegram Mini App открывается только по https."
        )

    @router.callback_query(F.data == "add:task")
    async def add_task_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_task)
        await callback.message.answer("Отправь задачу в формате: Название | 2026-03-17 19:00")
        await callback.answer()

    @router.callback_query(F.data == "add:event")
    async def add_event_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_event)
        await callback.message.answer("Отправь событие в формате: Название | 2026-03-17 19:00 | 60")
        await callback.answer()

    @router.callback_query(F.data == "add:note")
    async def add_note_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(PlannerStates.waiting_for_quick_note)
        await callback.message.answer("Отправь текст для входящих.")
        await callback.answer()

    @router.message(PlannerStates.waiting_for_task)
    async def task_flow(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        async with session_factory() as session:
            task = await create_task(session, user.id, parse_task_input(message.text or ""))
        await state.clear()
        await message.answer(f"Задача создана: {task.title}")

    @router.message(PlannerStates.waiting_for_event)
    async def event_flow(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        async with session_factory() as session:
            event = await create_event(session, user.id, parse_event_input(message.text or ""))
        await state.clear()
        await message.answer(f"Событие создано: {event.title}")

    @router.message(PlannerStates.waiting_for_quick_note)
    async def quick_note_flow(message: Message, state: FSMContext) -> None:
        user = await ensure_message_user(message)
        async with session_factory() as session:
            item = await create_inbox_item(session, user.id, InboxCreate(text=message.text or ""))
        await state.clear()
        await message.answer(f"Сохранено во входящие #{item.id}")

    @router.callback_query(F.data.startswith("task:"))
    async def task_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
        _, action, raw_id = (callback.data or "").split(":")
        task_id = int(raw_id)
        user = await ensure_message_user(callback.message)
        async with session_factory() as session:
            task = await get_task(session, user.id, task_id)
            if task is None:
                await callback.answer("Задача не найдена", show_alert=True)
                return
            if action == "complete":
                await complete_task(session, task)
                await callback.message.answer("Задача выполнена.")
            elif action == "delete":
                await delete_task(session, task)
                await callback.message.answer("Задача удалена.")
            elif action == "reschedule":
                await state.set_state(PlannerStates.waiting_for_reschedule)
                await state.update_data(entity="task", entity_id=task_id)
                await callback.message.answer("Новая дата: YYYY-MM-DD HH:MM")
        await callback.answer()

    @router.callback_query(F.data.startswith("event:"))
    async def event_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
        _, action, raw_id = (callback.data or "").split(":")
        event_id = int(raw_id)
        user = await ensure_message_user(callback.message)
        async with session_factory() as session:
            event = await get_event(session, user.id, event_id)
            if event is None:
                await callback.answer("Событие не найдено", show_alert=True)
                return
            if action == "delete":
                await delete_event(session, event)
                await callback.message.answer("Событие удалено.")
            elif action == "reschedule":
                await state.set_state(PlannerStates.waiting_for_reschedule)
                await state.update_data(entity="event", entity_id=event_id)
                await callback.message.answer("Новая дата: YYYY-MM-DD HH:MM")
        await callback.answer()

    @router.callback_query(F.data.startswith("settings:"))
    async def settings_callbacks(callback: CallbackQuery) -> None:
        user = await ensure_message_user(callback.message)
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
        new_date, new_time = parse_reschedule_input(message.text or "")
        async with session_factory() as session:
            if entity == "task":
                task = await get_task(session, user.id, int(entity_id))
                if task:
                    await reschedule_task(session, task, TaskReschedule(due_date=new_date, due_time=new_time))
                    await message.answer("Задача перенесена.")
            elif entity == "event":
                event = await get_event(session, user.id, int(entity_id))
                if event:
                    await reschedule_event(session, event, EventReschedule(event_date=new_date, start_time=new_time))
                    await message.answer("Событие перенесено.")
        await state.clear()

    @router.message(F.text)
    async def free_text_handler(message: Message, state: FSMContext) -> None:
        if await state.get_state():
            return
        user = await ensure_message_user(message)
        async with session_factory() as session:
            item = await create_inbox_item(session, user.id, InboxCreate(text=message.text))
        await message.answer(f"Сохранил во входящие #{item.id}")

    return router
