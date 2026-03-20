from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


MENU_PLANNER_TEXT = "Open Planner"


def build_inline_planner_button(webapp_url: str | None, text: str = MENU_PLANNER_TEXT) -> InlineKeyboardButton | None:
    if not webapp_url:
        return None
    if webapp_url.startswith("https://"):
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=webapp_url))
    return InlineKeyboardButton(text=text, url=webapp_url)


def planner_handoff_keyboard(webapp_url: str | None) -> InlineKeyboardMarkup | None:
    planner_button = build_inline_planner_button(webapp_url)
    if not planner_button:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[planner_button]])


def reminder_task_keyboard(task_id: int, webapp_url: str | None) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="✅ Выполнить", callback_data=f"task:complete:{task_id}")]
    ]
    planner_button = build_inline_planner_button(webapp_url)
    if planner_button:
        rows.append([planner_button])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reminder_event_keyboard(webapp_url: str | None) -> InlineKeyboardMarkup | None:
    planner_button = build_inline_planner_button(webapp_url)
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
        if show_completed:
            rows.append([InlineKeyboardButton(text="Очистить список выполненных", callback_data="today:completed:clear")])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)
