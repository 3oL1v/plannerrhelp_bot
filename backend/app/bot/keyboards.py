from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo


MENU_TODAY_TEXT = "✨ Сегодня"
MENU_PLANNER_TEXT = "📲 Planner"
TODAY_TEXT = "Сегодня"
TOMORROW_TEXT = "Завтра"
NO_DATE_TEXT = "Без даты"
NO_TIME_TEXT = "Без времени"
CUSTOM_DATE_TEXT = "Ввести свою"
CUSTOM_DURATION_TEXT = "Ввести свою"
BACK_TEXT = "Назад"
CANCEL_TEXT = "Отмена"
EVENT_DURATION_OPTIONS = ("30 мин", "60 мин", "90 мин")


def build_reply_keyboard(rows: list[list[KeyboardButton]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def build_inline_planner_button(webapp_url: str | None, text: str = MENU_PLANNER_TEXT) -> InlineKeyboardButton | None:
    if not webapp_url:
        return None
    if webapp_url.startswith("https://"):
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=webapp_url))
    return InlineKeyboardButton(text=text, url=webapp_url)


def main_menu_keyboard(_webapp_url: str | None) -> ReplyKeyboardMarkup:
    return build_reply_keyboard([[KeyboardButton(text="+")]])


def add_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Задача", callback_data="add:task"),
                InlineKeyboardButton(text="Событие", callback_data="add:event"),
            ]
        ]
    )


def planner_handoff_keyboard(webapp_url: str | None) -> InlineKeyboardMarkup | None:
    planner_button = build_inline_planner_button(webapp_url, text="📲 Открыть Planner")
    if not planner_button:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[planner_button]])


def build_task_complete_label(title: str, *, overdue: bool = False) -> str:
    label = title.strip() or "Задача"
    if len(label) > 24:
        label = f"{label[:21].rstrip()}..."
    prefix = "⚠️ " if overdue else "✅ "
    return f"{prefix}{label}"


def today_tasks_keyboard(dashboard, *, show_completed: bool = False) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = []
    for task in dashboard.tasks[:8]:
        rows.append([InlineKeyboardButton(text=build_task_complete_label(task.title), callback_data=f"task:complete:{task.id}")])
    for task in dashboard.overdue_tasks[:8]:
        rows.append([InlineKeyboardButton(text=build_task_complete_label(task.title, overdue=True), callback_data=f"task:complete:{task.id}")])
    if dashboard.completed_tasks:
        toggle_text = "Скрыть выполненные" if show_completed else "Показать выполненные"
        rows.append([InlineKeyboardButton(text=toggle_text, callback_data="today:completed:toggle")])
        rows.append([InlineKeyboardButton(text="Очистить список", callback_data="today:completed:clear")])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)
def task_date_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            [KeyboardButton(text=TODAY_TEXT), KeyboardButton(text=TOMORROW_TEXT)],
            [KeyboardButton(text=BACK_TEXT), KeyboardButton(text=CANCEL_TEXT)],
        ]
    )


def event_date_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            [KeyboardButton(text=TODAY_TEXT), KeyboardButton(text=TOMORROW_TEXT)],
            [KeyboardButton(text=BACK_TEXT), KeyboardButton(text=CANCEL_TEXT)],
        ]
    )


def task_time_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard(
        [
            [KeyboardButton(text=NO_TIME_TEXT)],
            [KeyboardButton(text=BACK_TEXT), KeyboardButton(text=CANCEL_TEXT)],
        ]
    )


def event_time_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard([[KeyboardButton(text=BACK_TEXT), KeyboardButton(text=CANCEL_TEXT)]])


def flow_cancel_keyboard() -> ReplyKeyboardMarkup:
    return build_reply_keyboard([[KeyboardButton(text=CANCEL_TEXT)]])


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
