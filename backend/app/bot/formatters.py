from __future__ import annotations

from html import escape

from app.schemas.dashboard import TodayDashboard
from app.schemas.settings import UserSettingsOut


MONTHS_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def safe_text(value: str) -> str:
    return escape(value, quote=False)


def format_pretty_date(value) -> str:
    return f"{value.day} {MONTHS_RU[value.month]}"


def format_pretty_time(value) -> str:
    return value.strftime("%H:%M")


def format_task_deadline(task) -> str:
    if not task.due_date:
        return ""
    deadline = format_pretty_date(task.due_date)
    if task.due_time:
        deadline += f" • {format_pretty_time(task.due_time)}"
    return deadline


def render_today_dashboard(dashboard: TodayDashboard) -> str:
    lines = ["✨ План на сегодня", format_pretty_date(dashboard.date), ""]

    if not dashboard.events and not dashboard.tasks and not dashboard.overdue_tasks:
        lines.extend(
            [
                "🌿 Спокойный день",
                "Сегодня без задач, событий и просрочки.",
                "",
                "📲 Всё редактирование — в Planner.",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "🌤 Фокус дня",
            f"{len(dashboard.tasks)} задачи • {len(dashboard.events)} события • {len(dashboard.overdue_tasks)} просрочено",
            "",
        ]
    )

    if dashboard.next_event:
        lines.extend(
            [
                "⏰ Ближайшее",
                f"{format_pretty_time(dashboard.next_event.start_time)} — {safe_text(dashboard.next_event.title)}",
                "",
            ]
        )
    else:
        lines.extend(["🌿 Ближайших событий нет", ""])

    lines.append("📲 Всё редактирование — в Planner.")
    return "\n".join(lines)


def render_today_events(dashboard: TodayDashboard) -> str:
    lines = ["📍 События"]
    for event in dashboard.events[:5]:
        end_time = f"–{format_pretty_time(event.end_time)}" if event.end_time else ""
        lines.append(f"• {format_pretty_time(event.start_time)}{end_time} — {safe_text(event.title)}")
    return "\n".join(lines)


def render_today_task_card(task, *, overdue: bool = False) -> str:
    title = "⚠️ Просроченная задача" if overdue else "🗂 Задача"
    lines = [title, safe_text(task.title)]
    if overdue:
        deadline = format_task_deadline(task)
        lines.append(f"Срок был: {deadline}" if deadline else "Срок уже прошёл.")
    elif task.due_time:
        lines.append(f"На сегодня • {format_pretty_time(task.due_time)}")
    else:
        lines.append("Сегодня без точного времени")
    return "\n".join(lines)


def render_inbox(items) -> str:
    if not items:
        return "📭 Inbox пуст."
    lines = ["📝 Inbox"]
    for item in items[:10]:
        lines.append(f"• {safe_text(item.text)}")
    return "\n".join(lines)


def render_settings(settings: UserSettingsOut) -> str:
    return (
        f"⚙️ Настройки\n"
        f"Часовой пояс: {settings.timezone}\n"
        f"Утренняя сводка: {'вкл' if settings.morning_digest_enabled else 'выкл'} в {settings.morning_digest_time.strftime('%H:%M')}\n"
        f"Напоминания: {'вкл' if settings.notifications_enabled else 'выкл'}\n"
        f"Напоминание по умолчанию: {settings.default_reminder_minutes} мин"
    )


def render_planner_handoff(title: str, body: str) -> str:
    return "\n".join(
        [
            safe_text(title),
            safe_text(body),
            "",
            "📲 Всё создание и редактирование теперь в Planner.",
        ]
    )


def help_text(webapp_url: str | None) -> str:
    url_line = f"\nPlanner: {safe_text(webapp_url)}" if webapp_url else ""
    return (
        "✨ Planner Help\n"
        "Бот показывает день, присылает напоминания и помогает быстро отмечать выполнение.\n"
        "Всё создание и редактирование — в Mini App."
        f"{url_line}"
    )
