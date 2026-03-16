from __future__ import annotations

from app.schemas.dashboard import TodayDashboard
from app.schemas.settings import UserSettingsOut


def render_today_dashboard(dashboard: TodayDashboard) -> str:
    lines = [f"Сегодня: {dashboard.date.isoformat()}"]
    if dashboard.next_event:
        lines.append(f"Ближайшее событие: {dashboard.next_event.title} в {dashboard.next_event.start_time.strftime('%H:%M')}")
    lines.append("")
    lines.append(f"События: {len(dashboard.events)}")
    lines.append(f"Задачи: {len(dashboard.tasks)}")
    lines.append(f"Просрочено: {len(dashboard.overdue_tasks)}")
    if dashboard.inbox_preview:
        lines.append(f"Во входящих: {len(dashboard.inbox_preview)}")
    return "\n".join(lines)


def render_task(task) -> str:
    due = ""
    if task.due_date:
        due = f" | до {task.due_date.isoformat()}"
        if task.due_time:
            due += f" {task.due_time.strftime('%H:%M')}"
    return f"Задача #{task.id}: {task.title}{due}"


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
