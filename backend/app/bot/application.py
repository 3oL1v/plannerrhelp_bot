from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, CallbackQuery, InlineKeyboardMarkup, MenuButtonCommands, MenuButtonWebApp, Message, Update, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.formatters import render_planner_handoff, render_today_dashboard, render_today_events, render_today_tasks
from app.bot.keyboards import CANCEL_TEXT, MENU_PLANNER_TEXT, MENU_TODAY_TEXT, TODAY_TEXT, main_menu_keyboard, planner_handoff_keyboard, today_tasks_keyboard
from app.config import Settings
from app.services.dashboard import build_today_dashboard
from app.services.events import get_event
from app.services.tasks import complete_task, get_task
from app.services.users import ensure_user


@dataclass
class ChatViewState:
    summary_message_id: int | None = None
    events_message_id: int | None = None
    tasks_message_id: int | None = None
    handoff_message_id: int | None = None


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


def build_router(settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> Router:
    router = Router()
    chat_views: dict[int, ChatViewState] = {}

    def menu_keyboard():
        return main_menu_keyboard(settings.effective_webapp_url)

    def planner_markup() -> InlineKeyboardMarkup | None:
        return planner_handoff_keyboard(settings.effective_webapp_url)

    def get_chat_view(chat_id: int) -> ChatViewState:
        return chat_views.setdefault(chat_id, ChatViewState())

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

    async def delete_slot(bot: Bot, chat_id: int, slot: str) -> None:
        view = get_chat_view(chat_id)
        message_id = getattr(view, slot)
        if not message_id:
            return
        with contextlib.suppress(TelegramBadRequest, TelegramNetworkError):
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        setattr(view, slot, None)

    async def upsert_slot(
        bot: Bot,
        chat_id: int,
        slot: str,
        text: str,
        *,
        send_markup=None,
        edit_markup: InlineKeyboardMarkup | None = None,
    ) -> int:
        view = get_chat_view(chat_id)
        message_id = getattr(view, slot)
        if message_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=edit_markup,
                )
                return message_id
            except TelegramBadRequest as exc:
                if "message is not modified" in str(exc).lower():
                    return message_id
            except TelegramNetworkError:
                pass

        sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=send_markup)
        setattr(view, slot, sent.message_id)
        return sent.message_id

    async def send_planner_handoff(bot: Bot, chat_id: int, title: str, body: str) -> None:
        markup = planner_markup()
        await upsert_slot(
            bot,
            chat_id,
            "handoff_message_id",
            render_planner_handoff(title, body),
            send_markup=markup,
            edit_markup=markup,
        )

    async def refresh_today_view(bot: Bot, chat_id: int, user_id: int) -> None:
        async with session_factory() as session:
            dashboard = await build_today_dashboard(session, user_id)

        await delete_slot(bot, chat_id, "handoff_message_id")
        await upsert_slot(
            bot,
            chat_id,
            "summary_message_id",
            render_today_dashboard(dashboard),
            send_markup=menu_keyboard(),
        )

        if dashboard.events:
            await upsert_slot(
                bot,
                chat_id,
                "events_message_id",
                render_today_events(dashboard),
            )
        else:
            await delete_slot(bot, chat_id, "events_message_id")

        has_tasks_block = bool(dashboard.tasks or dashboard.completed_tasks or dashboard.overdue_tasks)
        if has_tasks_block:
            tasks_markup = today_tasks_keyboard(dashboard.tasks, dashboard.overdue_tasks)
            await upsert_slot(
                bot,
                chat_id,
                "tasks_message_id",
                render_today_tasks(dashboard),
                send_markup=tasks_markup,
                edit_markup=tasks_markup,
            )
        else:
            await delete_slot(bot, chat_id, "tasks_message_id")

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        user = await ensure_message_user(message)
        await refresh_today_view(message.bot, message.chat.id, user.id)

    @router.message(StateFilter(None), F.text.in_({MENU_TODAY_TEXT, TODAY_TEXT}))
    async def today_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        await refresh_today_view(message.bot, message.chat.id, user.id)

    @router.message(StateFilter(None), F.text == "+")
    async def plus_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message.bot,
            message.chat.id,
            "✨ Всё управление — в Planner",
            "Создавай задачи, события и заметки прямо в Mini App.",
        )

    @router.message(StateFilter(None), F.text == "Входящие")
    async def inbox_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message.bot,
            message.chat.id,
            "📝 Inbox теперь в Planner",
            "Все заметки и конвертация в задачи или события живут в Mini App.",
        )

    @router.message(StateFilter(None), F.text == "Настройки")
    async def settings_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message.bot,
            message.chat.id,
            "⚙️ Настройки — в Planner",
            "Часовой пояс, утреннюю сводку и напоминания удобнее менять в Mini App.",
        )

    @router.message(StateFilter(None), F.text == "Помощь")
    async def help_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message.bot,
            message.chat.id,
            "✨ Planner Help",
            "Бот показывает день, присылает напоминания и помогает быстро отмечать выполнение.",
        )

    @router.message(StateFilter(None), F.text.in_({MENU_PLANNER_TEXT, "Открыть планировщик"}))
    async def open_planner_handler(message: Message) -> None:
        await ensure_message_user(message)
        if settings.effective_webapp_url:
            await send_planner_handoff(
                message.bot,
                message.chat.id,
                "📲 Planner под рукой",
                f"Открывай Mini App здесь: {settings.effective_webapp_url}",
            )
            return
        await upsert_slot(message.bot, message.chat.id, "handoff_message_id", "📲 Planner пока недоступен. Сначала укажи WEBAPP_URL.")

    @router.message(StateFilter("*"), F.text == CANCEL_TEXT)
    async def cancel_state_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        await upsert_slot(message.bot, message.chat.id, "handoff_message_id", "Действие отменено.")

    @router.callback_query(F.data.in_({"planner:handoff", "add:task", "add:event", "add:note"}))
    async def planner_handoff_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await ensure_callback_user(callback)
        if callback.message:
            await send_planner_handoff(
                callback.bot,
                callback.message.chat.id,
                "📲 Всё управление — в Planner",
                "Создание, редактирование и переносы теперь живут в Mini App.",
            )
        await callback.answer()

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
                await state.clear()
                await send_planner_handoff(
                    callback.bot,
                    chat_id,
                    "🗂 Управление задачей — в Planner",
                    "Перенос, удаление и все правки теперь делаются в Mini App.",
                )
                await callback.answer()
                return

        await state.clear()
        await refresh_today_view(callback.bot, chat_id, user.id)
        if callback.message:
            current_tasks_id = get_chat_view(chat_id).tasks_message_id
            if callback.message.message_id != current_tasks_id:
                with contextlib.suppress(TelegramBadRequest, TelegramNetworkError):
                    await callback.message.delete()
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
            await send_planner_handoff(
                callback.bot,
                callback.message.chat.id,
                "📍 Управление событием — в Planner",
                "Перенос, удаление и редактирование событий теперь делаются в Mini App.",
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("settings:"))
    async def settings_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        await state.clear()
        if callback.message:
            await send_planner_handoff(
                callback.bot,
                callback.message.chat.id,
                "⚙️ Настройки — в Planner",
                "Часовой пояс, утреннюю сводку и напоминания лучше менять в Mini App.",
            )
        await callback.answer()

    @router.message(StateFilter(None), F.text)
    async def free_text_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message.bot,
            message.chat.id,
            "📝 Быстрые мысли — в Planner",
            "Для заметок, задач и событий открой Mini App: там больше свободы и меньше лишних шагов.",
        )

    return router
