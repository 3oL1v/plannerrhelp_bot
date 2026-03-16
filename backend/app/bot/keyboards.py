from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard(webapp_url: str | None) -> ReplyKeyboardMarkup:
    planner_button = [KeyboardButton(text="Открыть планировщик")]
    if webapp_url:
        planner_button = [KeyboardButton(text="Открыть планировщик", web_app=WebAppInfo(url=webapp_url))]
    rows = [
        [KeyboardButton(text="Сегодня"), KeyboardButton(text="+")],
        [KeyboardButton(text="Входящие")],
        planner_button,
        [KeyboardButton(text="Настройки"), KeyboardButton(text="Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def add_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Задача", callback_data="add:task")
    builder.button(text="Событие", callback_data="add:event")
    builder.button(text="Быстрая запись", callback_data="add:note")
    builder.adjust(1)
    return builder.as_markup()


def task_actions_keyboard(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Выполнить", callback_data=f"task:complete:{task_id}")
    builder.button(text="Перенести", callback_data=f"task:reschedule:{task_id}")
    builder.button(text="Удалить", callback_data=f"task:delete:{task_id}")
    builder.adjust(1)
    return builder.as_markup()


def event_actions_keyboard(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перенести", callback_data=f"event:reschedule:{event_id}")
    builder.button(text="Удалить", callback_data=f"event:delete:{event_id}")
    builder.adjust(1)
    return builder.as_markup()


def settings_keyboard(morning_digest_enabled: bool, notifications_enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"Утренняя сводка: {'Вкл' if morning_digest_enabled else 'Выкл'}",
        callback_data="settings:toggle_digest",
    )
    builder.button(
        text=f"Напоминания: {'Вкл' if notifications_enabled else 'Выкл'}",
        callback_data="settings:toggle_notifications",
    )
    builder.adjust(1)
    return builder.as_markup()
