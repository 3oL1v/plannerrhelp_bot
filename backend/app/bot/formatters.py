from __future__ import annotations

from app.schemas.dashboard import TodayDashboard
from app.schemas.settings import UserSettingsOut


def format_task_time(task) -> str:
    if task.due_time:
        return task.due_time.strftime("%H:%M")
    return ""


def format_task_deadline(task) -> str:
    if not task.due_date:
        return ""
    deadline = task.due_date.isoformat()
    if task.due_time:
        deadline += f" {task.due_time.strftime('%H:%M')}"
    return deadline


def render_today_dashboard(dashboard: TodayDashboard) -> str:
    lines = [f"Сегодня • {dashboard.date.isoformat()}"]
    if dashboard.next_event:
        lines.append(f"Ближайшее: {dashboard.next_event.title} в {dashboard.next_event.start_time.strftime('%H:%M')}")

    stats = [
        f"События {len(dashboard.events)}",
        f"Задачи {len(dashboard.tasks)}",
        f"Просрочено {len(dashboard.overdue_tasks)}",
    ]
    if dashboard.inbox_preview:
        stats.append(f"Входящие {len(dashboard.inbox_preview)}")
    lines.append(" • ".join(stats))

    if dashboard.events:
        lines.append("")
        lines.append("События")
        for event in dashboard.events[:5]:
            end_time = f"-{event.end_time.strftime('%H:%M')}" if event.end_time else ""
            lines.append(f"• {event.start_time.strftime('%H:%M')}{end_time} {event.title}")

    if dashboard.tasks:
        lines.append("")
        lines.append("Задачи")
        for task in dashboard.tasks[:5]:
            task_time = format_task_time(task)
            suffix = f" • {task_time}" if task_time else ""
            lines.append(f"• {task.title}{suffix}")

    if dashboard.overdue_tasks:
        lines.append("")
        lines.append("Просроченные")
        for task in dashboard.overdue_tasks[:5]:
            lines.append(f"• {task.title} • {format_task_deadline(task)}")

    if len(lines) == 2 and not dashboard.events and not dashboard.tasks and not dashboard.overdue_tasks:
        lines.append("")
        lines.append("На сегодня пусто.")
    return "\n".join(lines)


def render_task(task) -> str:
    deadline = format_task_deadline(task)
    suffix = f" | до {deadline}" if deadline else ""
    return f"Задача #{task.id}: {task.title}{suffix}"


def render_event(event) -> str:
    end_time = f"-{event.end_time.strftime('%H:%M')}" if event.end_time else ""
    return f"Событие #{event.id}: {event.title} | {event.event_date.isoformat()} {event.start_time.strftime('%H:%M')}{end_time}"


def render_inbox(items) -> str:
    if not items:
        return "Входящие пусты."
    lines = ["Входящие:"]
    for item in items[:10]:
        lines.append(f"#{item.id}: {item.text}")
    return "\n".join(lines)


def render_settings(settings: UserSettingsOut) -> str:
    return (
        f"Часовой пояс: {settings.timezone}\n"
        f"Утренняя сводка: {'вкл' if settings.morning_digest_enabled else 'выкл'} в {settings.morning_digest_time.strftime('%H:%M')}\n"
        f"Напоминания: {'вкл' if settings.notifications_enabled else 'выкл'}\n"
        f"Напоминание по умолчанию: {settings.default_reminder_minutes} мин"
    )


def help_text(webapp_url: str | None) -> str:
    url_line = f"\nMini App: {webapp_url}" if webapp_url else ""
    return (
        "Команды:\n"
        "/start - обновить меню\n"
        "Сегодня - сводка на день\n"
        "+ - добавить задачу, событие или запись\n"
        "Любой свободный текст автоматически попадет во входящие."
        f"{url_line}"
    )
