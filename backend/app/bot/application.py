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
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, CallbackQuery, MenuButtonCommands, MenuButtonWebApp, Message, Update, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.formatters import render_planner_handoff, render_today_dashboard, render_today_events, render_today_task_card
from app.bot.keyboards import CANCEL_TEXT, MENU_PLANNER_TEXT, MENU_TODAY_TEXT, TODAY_TEXT, main_menu_keyboard, planner_handoff_keyboard, task_actions_keyboard
from app.config import Settings
from app.services.dashboard import build_today_dashboard
from app.services.events import get_event
from app.services.tasks import complete_task, get_task
from app.services.users import ensure_user


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
                BotCommand(command="start", description="План на сегодня"),
            ],
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

    def planner_markup():
        return planner_handoff_keyboard(settings.effective_webapp_url) or menu_keyboard()

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

    async def send_planner_handoff(message: Message, title: str, body: str) -> None:
        await message.answer(render_planner_handoff(title, body), reply_markup=planner_markup())

    async def send_today(message: Message, user_id: int) -> None:
        async with session_factory() as session:
            dashboard = await build_today_dashboard(session, user_id)

        await message.answer(render_today_dashboard(dashboard), reply_markup=menu_keyboard())

        if dashboard.events:
            await message.answer(render_today_events(dashboard))

        for task in dashboard.overdue_tasks[:5]:
            await message.answer(
                render_today_task_card(task, overdue=True),
                reply_markup=task_actions_keyboard(task.id, settings.effective_webapp_url),
            )

        for task in dashboard.tasks[:5]:
            await message.answer(
                render_today_task_card(task),
                reply_markup=task_actions_keyboard(task.id, settings.effective_webapp_url),
            )

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        user = await ensure_message_user(message)
        await send_today(message, user.id)

    @router.message(StateFilter(None), F.text.in_({MENU_TODAY_TEXT, TODAY_TEXT}))
    async def today_handler(message: Message) -> None:
        user = await ensure_message_user(message)
        await send_today(message, user.id)

    @router.message(StateFilter(None), F.text == "+")
    async def plus_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message,
            "✨ Всё управление — в Planner",
            "Создавай задачи, события и заметки прямо в Mini App.",
        )

    @router.message(StateFilter(None), F.text == "Входящие")
    async def inbox_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message,
            "📝 Inbox теперь в Planner",
            "Все заметки и конвертация в задачи или события живут в Mini App.",
        )

    @router.message(StateFilter(None), F.text == "Настройки")
    async def settings_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message,
            "⚙️ Настройки — в Planner",
            "Часовой пояс, утреннюю сводку и напоминания удобнее менять в Mini App.",
        )

    @router.message(StateFilter(None), F.text == "Помощь")
    async def help_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message,
            "✨ Planner Help",
            "Бот показывает день, присылает напоминания и помогает быстро отмечать выполнение.",
        )

    @router.message(StateFilter(None), F.text.in_({MENU_PLANNER_TEXT, "Открыть планировщик"}))
    async def open_planner_handler(message: Message) -> None:
        await ensure_message_user(message)
        if settings.effective_webapp_url:
            await send_planner_handoff(
                message,
                "📲 Planner под рукой",
                f"Открывай Mini App здесь: {settings.effective_webapp_url}",
            )
            return
        await message.answer("📲 Planner пока недоступен. Сначала укажи WEBAPP_URL.", reply_markup=menu_keyboard())

    @router.message(StateFilter("*"), F.text == CANCEL_TEXT)
    async def cancel_state_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=menu_keyboard())

    @router.callback_query(F.data.in_({"planner:handoff", "add:task", "add:event", "add:note"}))
    async def planner_handoff_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await ensure_callback_user(callback)
        if callback.message:
            await callback.message.answer(
                render_planner_handoff(
                    "📲 Всё управление — в Planner",
                    "Создание, редактирование и переносы теперь живут в Mini App.",
                ),
                reply_markup=planner_markup(),
            )
        await callback.answer()

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
            else:
                await state.clear()
                if callback.message:
                    await callback.message.answer(
                        render_planner_handoff(
                            "🗂 Управление задачей — в Planner",
                            "Перенос, удаление и все правки теперь делаются в Mini App.",
                        ),
                        reply_markup=planner_markup(),
                    )
                await callback.answer()
                return

        await state.clear()
        if callback.message:
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(
                f"✅ Готово\n{task.title}",
                reply_markup=menu_keyboard(),
            )
        await callback.answer()

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
            await callback.message.answer(
                render_planner_handoff(
                    "📍 Управление событием — в Planner",
                    "Перенос, удаление и редактирование событий теперь делаются в Mini App.",
                ),
                reply_markup=planner_markup(),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("settings:"))
    async def settings_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        await state.clear()
        if callback.message:
            await callback.message.answer(
                render_planner_handoff(
                    "⚙️ Настройки — в Planner",
                    "Часовой пояс, утреннюю сводку и напоминания лучше менять в Mini App.",
                ),
                reply_markup=planner_markup(),
            )
        await callback.answer()

    @router.message(StateFilter(None), F.text)
    async def free_text_handler(message: Message) -> None:
        await ensure_message_user(message)
        await send_planner_handoff(
            message,
            "📝 Быстрые мысли — в Planner",
            "Для заметок, задач и событий открой Mini App: там больше свободы и меньше лишних шагов.",
        )

    return router
