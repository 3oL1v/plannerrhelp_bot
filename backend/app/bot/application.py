from __future__ import annotations

import asyncio
import contextlib
import re
from dataclasses import dataclass, field
from typing import Literal

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    CallbackQuery,
    InlineKeyboardMarkup,
    MenuButtonCommands,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardRemove,
    Update,
    WebAppInfo,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.formatters import render_today_dashboard, render_today_events, render_today_tasks
from app.bot.keyboards import MENU_PLANNER_TEXT, planner_handoff_keyboard, reminder_event_keyboard, reminder_task_keyboard, today_tasks_keyboard
from app.config import Settings
from app.services.dashboard import build_today_dashboard
from app.services.inbox import create_inbox_item
from app.services.settings import clear_today_completed_for_user, get_settings_for_user, persist_bot_today_slots
from app.services.tasks import complete_task, get_task
from app.services.users import ensure_user


SlotStatus = Literal["ok", "missing"]
LEGACY_TODAY_TEXT = "Сегодня"
LEGACY_ADD_TEXT = "+"
LEGACY_PLANNER_TEXTS = {MENU_PLANNER_TEXT, "✨ Planner", "Planner"}
HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class ChatViewState:
    summary_message_id: int | None = None
    events_message_id: int | None = None
    tasks_message_id: int | None = None
    show_completed_tasks: bool = False


@dataclass
class BotApplication:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    bot: Bot | None = None
    dispatcher: Dispatcher | None = None
    polling_task: asyncio.Task | None = None
    production_setup_task: asyncio.Task | None = None
    chat_views: dict[int, ChatViewState] = field(default_factory=dict)
    user_chats: dict[int, set[int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.settings.telegram_bot_token:
            return
        self.bot = Bot(
            token=self.settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dispatcher = Dispatcher()
        self.dispatcher.include_router(build_router(self))

    def register_chat(self, user_id: int, chat_id: int) -> None:
        self.user_chats.setdefault(user_id, set()).add(chat_id)
        self.chat_views.setdefault(chat_id, ChatViewState())

    def get_chat_view(self, chat_id: int) -> ChatViewState:
        return self.chat_views.setdefault(chat_id, ChatViewState())

    async def load_persisted_today_slots(self, user_id: int, chat_id: int) -> None:
        view = self.get_chat_view(chat_id)
        if view.summary_message_id and view.events_message_id and view.tasks_message_id:
            return
        async with self.session_factory() as session:
            user_settings = await get_settings_for_user(session, user_id)
        if user_settings.bot_chat_id and user_settings.bot_chat_id != chat_id:
            return
        if view.summary_message_id is None:
            view.summary_message_id = user_settings.bot_summary_message_id
        if view.events_message_id is None:
            view.events_message_id = user_settings.bot_events_message_id
        if view.tasks_message_id is None:
            view.tasks_message_id = user_settings.bot_tasks_message_id

    async def persist_today_slots(self, user_id: int, chat_id: int) -> None:
        view = self.get_chat_view(chat_id)
        async with self.session_factory() as session:
            await persist_bot_today_slots(
                session,
                user_id,
                chat_id=chat_id,
                summary_message_id=view.summary_message_id,
                events_message_id=view.events_message_id,
                tasks_message_id=view.tasks_message_id,
            )

    async def start(self) -> None:
        if not self.bot or not self.dispatcher:
            return
        if self.settings.is_production and self.settings.webhook_url:
            self.production_setup_task = asyncio.create_task(self._configure_production_webhook())
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
        if self.production_setup_task:
            self.production_setup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.production_setup_task
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

    async def send_message(self, telegram_id: int, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
        if not self.bot:
            return
        try:
            await self.bot.send_message(telegram_id, text, reply_markup=reply_markup)
        except TelegramBadRequest:
            return

    async def send_reminder_message(self, telegram_id: int, *, entity_type: str, entity_id: int, text: str) -> None:
        markup: InlineKeyboardMarkup | None = None
        if entity_type == "task":
            markup = reminder_task_keyboard(entity_id, self.settings.effective_webapp_url)
        elif entity_type == "event":
            markup = reminder_event_keyboard(self.settings.effective_webapp_url)
        await self.send_message(telegram_id, text, reply_markup=markup)

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

    async def delete_messages(self, chat_id: int, message_ids: list[int]) -> None:
        if not self.bot:
            return
        for message_id in dict.fromkeys(message_ids):
            with contextlib.suppress(TelegramBadRequest, TelegramNetworkError):
                await self.bot.delete_message(chat_id=chat_id, message_id=message_id)

    def schedule_message_cleanup(self, chat_id: int, message_ids: list[int], delay_seconds: float = 5) -> None:
        if not self.bot or not message_ids:
            return
        asyncio.create_task(self._delete_messages_after_delay(chat_id, message_ids, delay_seconds))

    async def _delete_messages_after_delay(self, chat_id: int, message_ids: list[int], delay_seconds: float) -> None:
        await asyncio.sleep(delay_seconds)
        await self.delete_messages(chat_id, message_ids)

    async def remove_legacy_keyboard(self, chat_id: int) -> None:
        if not self.bot:
            return
        try:
            sent = await self.bot.send_message(chat_id=chat_id, text="\u2060", reply_markup=ReplyKeyboardRemove())
        except (TelegramBadRequest, TelegramNetworkError):
            return
        self.schedule_message_cleanup(chat_id, [sent.message_id], delay_seconds=1.0)

    @staticmethod
    def _plain_text(text: str) -> str:
        cleaned = HTML_TAG_RE.sub("", text)
        return cleaned.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

    async def _edit_slot(
        self,
        chat_id: int,
        message_id: int | None,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> SlotStatus:
        if not self.bot or not message_id:
            return "missing"
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return "ok"
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return "ok"
            if "parse entities" in str(exc).lower():
                try:
                    await self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=self._plain_text(text),
                        reply_markup=reply_markup,
                    )
                    return "ok"
                except (TelegramBadRequest, TelegramNetworkError):
                    return "missing"
            return "missing"
        except TelegramNetworkError:
            return "ok"

    async def _send_slot_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message:
        if not self.bot:
            raise RuntimeError("Bot is not initialized")
        try:
            return await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            if "parse entities" not in str(exc).lower():
                raise
            return await self.bot.send_message(
                chat_id=chat_id,
                text=self._plain_text(text),
                reply_markup=reply_markup,
            )

    async def _send_summary_slot(self, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | None) -> None:
        sent = await self._send_slot_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        self.get_chat_view(chat_id).summary_message_id = sent.message_id

    async def _send_events_slot(self, chat_id: int, text: str) -> None:
        sent = await self._send_slot_message(chat_id=chat_id, text=text)
        self.get_chat_view(chat_id).events_message_id = sent.message_id

    async def _send_tasks_slot(self, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | None) -> None:
        sent = await self._send_slot_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        self.get_chat_view(chat_id).tasks_message_id = sent.message_id

    async def _send_today_trio(
        self,
        chat_id: int,
        *,
        summary_text: str,
        summary_markup: InlineKeyboardMarkup | None,
        events_text: str,
        tasks_text: str,
        tasks_markup: InlineKeyboardMarkup | None,
    ) -> None:
        await self._send_summary_slot(chat_id, summary_text, summary_markup)
        await self._send_events_slot(chat_id, events_text)
        await self._send_tasks_slot(chat_id, tasks_text, tasks_markup)

    async def _send_events_and_tasks(
        self,
        chat_id: int,
        *,
        events_text: str,
        tasks_text: str,
        tasks_markup: InlineKeyboardMarkup | None,
    ) -> None:
        await self._send_events_slot(chat_id, events_text)
        await self._send_tasks_slot(chat_id, tasks_text, tasks_markup)

    async def _recreate_today_trio(
        self,
        chat_id: int,
        user_id: int,
        *,
        summary_text: str,
        summary_markup: InlineKeyboardMarkup | None,
        events_text: str,
        tasks_text: str,
        tasks_markup: InlineKeyboardMarkup | None,
    ) -> None:
        await self.delete_slot(chat_id, "summary_message_id")
        await self.delete_slot(chat_id, "events_message_id")
        await self.delete_slot(chat_id, "tasks_message_id")
        await self._send_today_trio(
            chat_id,
            summary_text=summary_text,
            summary_markup=summary_markup,
            events_text=events_text,
            tasks_text=tasks_text,
            tasks_markup=tasks_markup,
        )
        await self.persist_today_slots(user_id, chat_id)

    async def refresh_today_view(self, chat_id: int, user_id: int) -> None:
        await self.load_persisted_today_slots(user_id, chat_id)
        view = self.get_chat_view(chat_id)

        async with self.session_factory() as session:
            dashboard = await build_today_dashboard(session, user_id)

        summary_text = render_today_dashboard(dashboard)
        summary_markup = planner_handoff_keyboard(self.settings.effective_webapp_url)
        events_text = render_today_events(dashboard)
        tasks_text = render_today_tasks(dashboard, show_completed=view.show_completed_tasks)
        tasks_markup = today_tasks_keyboard(dashboard, show_completed=view.show_completed_tasks)

        if not view.summary_message_id or not view.events_message_id or not view.tasks_message_id:
            await self._recreate_today_trio(
                chat_id,
                user_id,
                summary_text=summary_text,
                summary_markup=summary_markup,
                events_text=events_text,
                tasks_text=tasks_text,
                tasks_markup=tasks_markup,
            )
            return

        summary_status = await self._edit_slot(
            chat_id,
            view.summary_message_id,
            summary_text,
            reply_markup=summary_markup,
        )
        if summary_status == "missing":
            await self._recreate_today_trio(
                chat_id,
                user_id,
                summary_text=summary_text,
                summary_markup=summary_markup,
                events_text=events_text,
                tasks_text=tasks_text,
                tasks_markup=tasks_markup,
            )
            return

        events_status = await self._edit_slot(chat_id, view.events_message_id, events_text)
        if events_status == "missing":
            await self._recreate_today_trio(
                chat_id,
                user_id,
                summary_text=summary_text,
                summary_markup=summary_markup,
                events_text=events_text,
                tasks_text=tasks_text,
                tasks_markup=tasks_markup,
            )
            return

        tasks_status = await self._edit_slot(
            chat_id,
            view.tasks_message_id,
            tasks_text,
            reply_markup=tasks_markup,
        )
        if tasks_status == "missing":
            await self._recreate_today_trio(
                chat_id,
                user_id,
                summary_text=summary_text,
                summary_markup=summary_markup,
                events_text=events_text,
                tasks_text=tasks_text,
                tasks_markup=tasks_markup,
            )
            return

        await self.persist_today_slots(user_id, chat_id)

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

    async def _configure_production_webhook(self) -> None:
        if not self.bot or not self.dispatcher or not self.settings.webhook_url:
            return
        try:
            await asyncio.wait_for(self._configure_production_bot(), timeout=10)
            await asyncio.wait_for(
                self.bot.set_webhook(
                    self.settings.webhook_url,
                    allowed_updates=self.dispatcher.resolve_used_update_types(),
                ),
                timeout=10,
            )
        except (asyncio.TimeoutError, TelegramNetworkError, TelegramBadRequest):
            return

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

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        notice = await message.answer("Обновляю блоки…")
        try:
            await bot_app.refresh_today_view(message.chat.id, user.id)
            await bot_app.remove_legacy_keyboard(message.chat.id)
            await notice.edit_text("Блоки обновлены выше ↑")
            bot_app.schedule_message_cleanup(message.chat.id, [notice.message_id], delay_seconds=12)
        except Exception:
            with contextlib.suppress(TelegramBadRequest, TelegramNetworkError):
                await notice.edit_text(
                    "Не удалось обновить блоки. Открой Planner и проверь текущее состояние.",
                    reply_markup=planner_handoff_keyboard(settings.effective_webapp_url),
                )

    @router.message(F.text == LEGACY_TODAY_TEXT)
    async def legacy_today_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        await bot_app.refresh_today_view(message.chat.id, user.id)
        await bot_app.remove_legacy_keyboard(message.chat.id)
        bot_app.schedule_message_cleanup(message.chat.id, [message.message_id], delay_seconds=1.5)

    @router.message(F.text == LEGACY_ADD_TEXT)
    async def legacy_add_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        await bot_app.refresh_today_view(message.chat.id, user.id)
        await bot_app.remove_legacy_keyboard(message.chat.id)
        if bot_app.bot:
            sent = await bot_app.bot.send_message(
                chat_id=message.chat.id,
                text="Создание задач и событий перенесено в Planner.",
                reply_markup=planner_handoff_keyboard(settings.effective_webapp_url),
            )
            bot_app.schedule_message_cleanup(message.chat.id, [message.message_id, sent.message_id], delay_seconds=6)
        else:
            bot_app.schedule_message_cleanup(message.chat.id, [message.message_id], delay_seconds=6)

    @router.message(F.text.in_(LEGACY_PLANNER_TEXTS))
    async def legacy_planner_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        await bot_app.refresh_today_view(message.chat.id, user.id)
        await bot_app.remove_legacy_keyboard(message.chat.id)
        bot_app.schedule_message_cleanup(message.chat.id, [message.message_id], delay_seconds=1.5)

    @router.callback_query(F.data == "today:completed:toggle")
    async def toggle_completed_handler(callback: CallbackQuery) -> None:
        if not callback.message:
            await callback.answer()
            return
        user = await ensure_callback_user(callback)
        view = bot_app.get_chat_view(callback.message.chat.id)
        view.show_completed_tasks = not view.show_completed_tasks
        await bot_app.refresh_today_view(callback.message.chat.id, user.id)
        await callback.answer()

    @router.callback_query(F.data == "today:completed:clear")
    async def clear_completed_handler(callback: CallbackQuery) -> None:
        if not callback.message:
            await callback.answer()
            return
        user = await ensure_callback_user(callback)
        async with session_factory() as session:
            await clear_today_completed_for_user(session, user.id)
        view = bot_app.get_chat_view(callback.message.chat.id)
        view.show_completed_tasks = False
        await bot_app.refresh_today_view(callback.message.chat.id, user.id)
        await callback.answer("Список очищен")

    @router.callback_query(F.data.startswith("task:complete:"))
    async def complete_task_handler(callback: CallbackQuery) -> None:
        if not callback.message:
            await callback.answer()
            return
        user = await ensure_callback_user(callback)
        task_id = int((callback.data or "0").split(":")[-1])
        async with session_factory() as session:
            task = await get_task(session, user.id, task_id)
            if task is None:
                await callback.answer("Задача не найдена")
                return
            await complete_task(session, task)
        await bot_app.refresh_today_view(callback.message.chat.id, user.id)
        view = bot_app.get_chat_view(callback.message.chat.id)
        trio_ids = {view.summary_message_id, view.events_message_id, view.tasks_message_id}
        if callback.message.message_id not in trio_ids:
            with contextlib.suppress(TelegramBadRequest, TelegramNetworkError):
                await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Готово")

    @router.message(F.text)
    async def free_text_handler(message: Message) -> None:
        if not message.text or message.text.startswith("/"):
            return
        text = message.text.strip()
        if not text:
            return
        user = await ensure_message_user(message)
        async with session_factory() as session:
            await create_inbox_item(session, user.id, payload={"text": text})
        response = await message.answer("Заметка добавлена")
        bot_app.schedule_message_cleanup(message.chat.id, [message.message_id, response.message_id], delay_seconds=8)

    return router
