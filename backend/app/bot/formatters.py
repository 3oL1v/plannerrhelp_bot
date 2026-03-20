from __future__ import annotations

from html import escape

from app.schemas.dashboard import TodayDashboard


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


def safe_text(value: str | None) -> str:
    return escape(value or "", quote=False)


def format_pretty_date(value) -> str:
    return f"{value.day} {MONTHS_RU[value.month]}"


def format_pretty_time(value) -> str:
    return value.strftime("%H:%M")


def build_task_line(task, *, overdue: bool = False) -> str:
    prefix = ""
    if overdue and task.due_date:
        prefix = format_pretty_date(task.due_date)
        if task.due_time:
            prefix += f" {format_pretty_time(task.due_time)}"
    elif task.due_time:
        prefix = format_pretty_time(task.due_time)

    text = safe_text(task.title)
    return f"• {prefix} — {text}" if prefix else f"• {text}"


def render_quote_block(lines: list[str]) -> str:
    body = "\n".join(lines) if lines else "• Пусто"
    return f"<blockquote>{body}</blockquote>"


def render_today_dashboard(dashboard: TodayDashboard) -> str:
    lines = ["✨ План на сегодня", format_pretty_date(dashboard.date), ""]

    if not dashboard.events and not dashboard.tasks and not dashboard.overdue_tasks and not dashboard.completed_tasks:
        lines.extend(
            [
                "🌿 Спокойный день",
                "Сегодня без задач, событий и просрочки.",
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
            ]
        )
    else:
        lines.append("🌿 Ближайших событий нет")

    return "\n".join(lines)


def render_today_events(dashboard: TodayDashboard) -> str:
    lines = ["📍 События"]
    if not dashboard.events:
        lines.append("Сегодня событий нет.")
        return "\n".join(lines)
    for event in dashboard.events[:5]:
        end_time = f"–{format_pretty_time(event.end_time)}" if event.end_time else ""
        lines.append(f"• {format_pretty_time(event.start_time)}{end_time} — {safe_text(event.title)}")
    return "\n".join(lines)


def render_today_tasks(dashboard: TodayDashboard, *, show_completed: bool = False) -> str:
    lines = ["🗂 Задачи"]

    if dashboard.overdue_tasks:
        overdue_lines = [build_task_line(task, overdue=True) for task in dashboard.overdue_tasks[:8]]
        lines.extend(["", "<b>⚠️ Просрочено</b>", render_quote_block(overdue_lines)])

    active_lines = [build_task_line(task) for task in dashboard.tasks[:8]]
    if not active_lines:
        active_lines = ["• Сегодня задач нет."]

    lines.extend(["", "<b>Текущие</b>", render_quote_block(active_lines)])

    if dashboard.completed_tasks:
        lines.extend(["", f"<i>✅ Выполнено сегодня: {len(dashboard.completed_tasks)}</i>"])
        if show_completed:
            completed_lines = [f"• ✅ {safe_text(task.title)}" for task in dashboard.completed_tasks[:8]]
            lines.extend(["<b>Выполненные</b>", render_quote_block(completed_lines)])

    return "\n".join(lines)
