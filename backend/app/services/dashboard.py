from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Event, InboxItem, Task
from app.schemas.dashboard import TodayDashboard, WeekDashboard, WeekDaySummary
from app.services.settings import get_settings_for_user
from app.utils.datetime import today_in_timezone, week_bounds


async def build_today_dashboard(session: AsyncSession, user_id: int) -> TodayDashboard:
    user_settings = await get_settings_for_user(session, user_id)
    today = today_in_timezone(user_settings.timezone)

    events_result = await session.execute(
        select(Event)
        .where(Event.user_id == user_id, Event.deleted_at.is_(None), Event.event_date == today)
        .order_by(Event.start_time)
    )
    tasks_result = await session.execute(
        select(Task)
        .where(Task.user_id == user_id, Task.deleted_at.is_(None), Task.status == "open", Task.due_date == today)
        .order_by(Task.due_time.is_(None), Task.due_time, Task.created_at.desc())
    )
    completed_result = await session.execute(
        select(Task).where(Task.user_id == user_id, Task.deleted_at.is_(None), Task.status == "completed", Task.due_date == today)
        .order_by(Task.completed_at.desc().nullslast(), Task.updated_at.desc())
    )
    overdue_result = await session.execute(
        select(Task)
        .where(Task.user_id == user_id, Task.deleted_at.is_(None), Task.status == "open", Task.due_date.is_not(None), Task.due_date < today)
        .order_by(Task.due_date, Task.due_time.is_(None), Task.due_time)
    )
    inbox_result = await session.execute(
        select(InboxItem)
        .where(InboxItem.user_id == user_id, InboxItem.deleted_at.is_(None), InboxItem.status == "active")
        .order_by(InboxItem.created_at.desc())
        .limit(5)
    )

    events = list(events_result.scalars().all())
    tasks = list(tasks_result.scalars().all())
    completed_tasks = list(completed_result.scalars().all())
    if user_settings.today_completed_hidden_before is not None:
        completed_tasks = [
            task
            for task in completed_tasks
            if task.completed_at is not None and task.completed_at > user_settings.today_completed_hidden_before
        ]
    overdue = list(overdue_result.scalars().all())
    inbox = list(inbox_result.scalars().all())

    return TodayDashboard(
        date=today,
        next_event=events[0] if events else None,
        events=events,
        tasks=tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue,
        inbox_preview=inbox,
    )


async def build_week_dashboard(session: AsyncSession, user_id: int) -> WeekDashboard:
    user_settings = await get_settings_for_user(session, user_id)
    today = today_in_timezone(user_settings.timezone)
    week_start, week_end = week_bounds(today, user_settings.week_starts_on)

    tasks_result = await session.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
            Task.status == "open",
            Task.due_date.is_not(None),
            Task.due_date >= week_start,
            Task.due_date <= week_end,
        )
        .order_by(Task.due_date, Task.due_time.is_(None), Task.due_time)
    )
    events_result = await session.execute(
        select(Event)
        .where(
            Event.user_id == user_id,
            Event.deleted_at.is_(None),
            Event.event_date >= week_start,
            Event.event_date <= week_end,
        )
        .order_by(Event.event_date, Event.start_time)
    )

    tasks_by_day: dict = {}
    for task in tasks_result.scalars().all():
        tasks_by_day.setdefault(task.due_date, []).append(task)

    events_by_day: dict = {}
    for event in events_result.scalars().all():
        events_by_day.setdefault(event.event_date, []).append(event)

    days = []
    cursor = week_start
    while cursor <= week_end:
        days.append(
            WeekDaySummary(
                date=cursor,
                tasks=tasks_by_day.get(cursor, []),
                events=events_by_day.get(cursor, []),
            )
        )
        cursor += timedelta(days=1)

    return WeekDashboard(week_start=week_start, week_end=week_end, days=days)


async def build_morning_digest_text(session: AsyncSession, user_id: int, timezone_name: str) -> str:
    dashboard = await build_today_dashboard(session, user_id)
    parts = [
        "☀️ Доброе утро",
        dashboard.date.strftime("%d.%m.%Y"),
        "",
    ]

    if not dashboard.events and not dashboard.tasks and not dashboard.overdue_tasks:
        parts.extend(
            [
                "🌿 На сегодня спокойно",
                "Задач, событий и просрочки нет.",
            ]
        )
        return "\n".join(parts)

    parts.extend(
        [
            "🌤 На сегодня",
            f"• задач: {len(dashboard.tasks)}",
            f"• событий: {len(dashboard.events)}",
            f"• просрочено: {len(dashboard.overdue_tasks)}",
        ]
    )

    if dashboard.next_event:
        parts.extend(
            [
                "",
                "⏰ Ближайший слот",
                f"{dashboard.next_event.start_time.strftime('%H:%M')} — {dashboard.next_event.title}",
            ]
        )

    return "\n".join(parts)
