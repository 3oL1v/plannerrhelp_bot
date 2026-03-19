from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


TODAY_TEXT = "Сегодня"
TOMORROW_TEXT = "Завтра"
NO_DATE_TEXT = "Без даты"
NO_TIME_TEXT = "Без времени"
CUSTOM_DATE_TEXT = "Ввести свою"
CUSTOM_TIME_TEXT = "Ввести свое"
CUSTOM_DURATION_TEXT = "Ввести свою"
BACK_TEXT = "Назад"
CANCEL_TEXT = "Отмена"

TASK_TIME_OPTIONS = ("09:00", "14:00", "19:00")
EVENT_TIME_OPTIONS = ("09:00", "14:00", "19:00")
EVENT_DURATION_OPTIONS = ("30 мин", "60 мин", "90 мин")


def build_reply_keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
    )


def main_menu_keyboard(webapp_url: str | None) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="Сегодня"), KeyboardButton(text="+")],
        [KeyboardButton(text="Входящие")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def add_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Задача", callback_data="add:task")
    builder.button(text="Событие", callback_data="add:event")
    builder.button(text="Быстрая запись", callback_data="add:note")
    builder.adjust(1)
    return builder.as_markup()


def flow_cancel_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard([[CANCEL_TEXT]])


def task_date_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            [TODAY_TEXT, TOMORROW_TEXT],
            [NO_DATE_TEXT, CUSTOM_DATE_TEXT],
            [BACK_TEXT, CANCEL_TEXT],
        ]
    )


def task_time_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            list(TASK_TIME_OPTIONS),
            [NO_TIME_TEXT, CUSTOM_TIME_TEXT],
            [BACK_TEXT, CANCEL_TEXT],
        ]
    )


def event_date_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            [TODAY_TEXT, TOMORROW_TEXT],
            [CUSTOM_DATE_TEXT],
            [BACK_TEXT, CANCEL_TEXT],
        ]
    )


def event_time_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            list(EVENT_TIME_OPTIONS),
            [CUSTOM_TIME_TEXT],
            [BACK_TEXT, CANCEL_TEXT],
        ]
    )


def event_duration_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            list(EVENT_DURATION_OPTIONS),
            [CUSTOM_DURATION_TEXT],
            [BACK_TEXT, CANCEL_TEXT],
        ]
    )


def manual_input_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard([[BACK_TEXT, CANCEL_TEXT]])


def task_actions_keyboard(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Выполнить", callback_data=f"task:complete:{task_id}")
    builder.button(text="Перенести", callback_data=f"task:reschedule:{task_id}")
    builder.button(text="Удалить", callback_data=f"task:delete:{task_id}")
    builder.adjust(3)
    return builder.as_markup()


def event_actions_keyboard(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перенести", callback_data=f"event:reschedule:{event_id}")
    builder.button(text="Удалить", callback_data=f"event:delete:{event_id}")
    builder.adjust(2)
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
