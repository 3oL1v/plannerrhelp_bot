from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder


MENU_TODAY_TEXT = "✨ Сегодня"
MENU_PLANNER_TEXT = "📲 Planner"
TODAY_TEXT = "Сегодня"
TOMORROW_TEXT = "Завтра"
NO_DATE_TEXT = "Без даты"
CUSTOM_DATE_TEXT = "Ввести свою"
CUSTOM_DURATION_TEXT = "Ввести свою"
BACK_TEXT = "Назад"
CANCEL_TEXT = "Отмена"
EVENT_DURATION_OPTIONS = ("30 мин", "60 мин", "90 мин")


def build_reply_keyboard(rows: list[list[KeyboardButton]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def build_planner_button(webapp_url: str | None) -> KeyboardButton:
    if webapp_url and webapp_url.startswith("https://"):
        return KeyboardButton(text=MENU_PLANNER_TEXT, web_app=WebAppInfo(url=webapp_url))
    return KeyboardButton(text=MENU_PLANNER_TEXT)


def build_inline_planner_button(webapp_url: str | None, text: str = MENU_PLANNER_TEXT) -> InlineKeyboardButton | None:
    if not webapp_url:
        return None
    if webapp_url.startswith("https://"):
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=webapp_url))
    return InlineKeyboardButton(text=text, url=webapp_url)


def main_menu_keyboard(webapp_url: str | None) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=MENU_TODAY_TEXT)],
        [build_planner_button(webapp_url)],
    ]
    return build_reply_keyboard(rows)


def add_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗂 В Planner", callback_data="planner:handoff")
    return builder.as_markup()


def flow_cancel_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard([[KeyboardButton(text=CANCEL_TEXT)]])


def task_date_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            [KeyboardButton(text=TODAY_TEXT), KeyboardButton(text=TOMORROW_TEXT)],
            [KeyboardButton(text=NO_DATE_TEXT), KeyboardButton(text=CUSTOM_DATE_TEXT)],
            [KeyboardButton(text=BACK_TEXT), KeyboardButton(text=CANCEL_TEXT)],
        ]
    )


def task_time_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard([[KeyboardButton(text=BACK_TEXT)]])


def event_date_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            [KeyboardButton(text=TODAY_TEXT), KeyboardButton(text=TOMORROW_TEXT)],
            [KeyboardButton(text=CUSTOM_DATE_TEXT)],
            [KeyboardButton(text=BACK_TEXT), KeyboardButton(text=CANCEL_TEXT)],
        ]
    )


def event_time_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard([[KeyboardButton(text=BACK_TEXT)]])


def event_duration_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            [KeyboardButton(text=EVENT_DURATION_OPTIONS[0]), KeyboardButton(text=EVENT_DURATION_OPTIONS[1]), KeyboardButton(text=EVENT_DURATION_OPTIONS[2])],
            [KeyboardButton(text=CUSTOM_DURATION_TEXT)],
            [KeyboardButton(text=BACK_TEXT), KeyboardButton(text=CANCEL_TEXT)],
        ]
    )


def manual_input_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard([[KeyboardButton(text=BACK_TEXT), KeyboardButton(text=CANCEL_TEXT)]])


def task_actions_keyboard(task_id: int, webapp_url: str | None) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text="✅ Выполнить", callback_data=f"task:complete:{task_id}")]
    planner_button = build_inline_planner_button(webapp_url)
    if planner_button:
        row.append(planner_button)
    return InlineKeyboardMarkup(inline_keyboard=[row])


def planner_handoff_keyboard(webapp_url: str | None) -> InlineKeyboardMarkup | None:
    planner_button = build_inline_planner_button(webapp_url, text="📲 Открыть Planner")
    if not planner_button:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[planner_button]])


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
