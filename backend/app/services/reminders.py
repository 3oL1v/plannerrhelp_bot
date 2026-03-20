from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.entities import Event, Reminder, ReminderEntityType, ReminderStatus, Task, User, UserSettings
from app.utils.datetime import combine_user_datetime, to_user_timezone, utc_now


async def cancel_entity_reminders(session: AsyncSession, user_id: int, entity_type: str, entity_id: int) -> None:
    result = await session.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.entity_type == entity_type,
            Reminder.entity_id == entity_id,
            Reminder.status == ReminderStatus.PENDING.value,
        )
    )
    for reminder in result.scalars().all():
        reminder.status = ReminderStatus.CANCELED.value


async def sync_task_reminder(session: AsyncSession, task: Task, user_settings: UserSettings) -> None:
    await cancel_entity_reminders(session, task.user_id, ReminderEntityType.TASK.value, task.id)
    if task.deleted_at or task.status != "open" or task.due_date is None or task.due_time is None:
        return
    remind_at = combine_user_datetime(task.due_date, task.due_time, user_settings.timezone)
    remind_at = remind_at.replace(second=0, microsecond=0)
    remind_at = remind_at - timedelta(minutes=user_settings.default_reminder_minutes)
    if remind_at <= utc_now():
        return
    session.add(
        Reminder(
            user_id=task.user_id,
            entity_type=ReminderEntityType.TASK.value,
            entity_id=task.id,
            remind_at=remind_at,
            status=ReminderStatus.PENDING.value,
        )
    )


async def sync_event_reminder(session: AsyncSession, event: Event, user_settings: UserSettings) -> None:
    await cancel_entity_reminders(session, event.user_id, ReminderEntityType.EVENT.value, event.id)
    if event.deleted_at or event.status != "planned":
        return
    remind_at = combine_user_datetime(event.event_date, event.start_time, user_settings.timezone)
    remind_at = remind_at.replace(second=0, microsecond=0)
    remind_at = remind_at - timedelta(minutes=user_settings.default_reminder_minutes)
    if remind_at <= utc_now():
        return
    session.add(
        Reminder(
            user_id=event.user_id,
            entity_type=ReminderEntityType.EVENT.value,
            entity_id=event.id,
            remind_at=remind_at,
            status=ReminderStatus.PENDING.value,
        )
    )


async def dispatch_due_reminders(
    session_factory: async_sessionmaker[AsyncSession],
    send_reminder_message,
) -> None:
    async with session_factory() as session:
        now = utc_now()
        result = await session.execute(
            select(Reminder, User, UserSettings)
            .join(User, User.id == Reminder.user_id)
            .join(UserSettings, UserSettings.user_id == User.id)
            .where(Reminder.status == ReminderStatus.PENDING.value, Reminder.remind_at <= now)
            .order_by(Reminder.remind_at)
        )
        for reminder, user, user_settings in result.all():
            if not user_settings.notifications_enabled:
                reminder.status = ReminderStatus.CANCELED.value
                continue
            text = await build_reminder_text(session, reminder)
            if text:
                await send_reminder_message(
                    user.telegram_id,
                    entity_type=reminder.entity_type,
                    entity_id=reminder.entity_id,
                    text=text,
                )
                reminder.status = ReminderStatus.SENT.value
                reminder.sent_at = now
            else:
                reminder.status = ReminderStatus.CANCELED.value
        await session.commit()


async def build_reminder_text(session: AsyncSession, reminder: Reminder) -> str | None:
    if reminder.entity_type == ReminderEntityType.TASK.value:
        task = await session.get(Task, reminder.entity_id)
        if not task or task.deleted_at or task.status != "open":
            return None

        when_line = "Сегодня без точного времени"
        if task.due_date and task.due_time:
            when_line = f"Срок: {task.due_date.isoformat()} • {task.due_time.strftime('%H:%M')}"
        elif task.due_date:
            when_line = f"Срок: {task.due_date.isoformat()}"

        return "\n".join(
            [
                "⏰ Напоминание",
                "",
                task.title,
                "",
                when_line,
                "📲 Если нужно что-то поменять — открой Planner.",
            ]
        )

    event = await session.get(Event, reminder.entity_id)
    if not event or event.deleted_at or event.status != "planned":
        return None

    return "\n".join(
        [
            "📍 Скоро событие",
            "",
            event.title,
            "",
            f"Старт: {event.event_date.isoformat()} • {event.start_time.strftime('%H:%M')}",
            "📲 Если слот поменялся — открой Planner.",
        ]
    )


async def dispatch_morning_digests(
    session_factory: async_sessionmaker[AsyncSession],
    send_message,
    build_digest,
) -> None:
    async with session_factory() as session:
        result = await session.execute(
            select(User, UserSettings)
            .join(UserSettings, UserSettings.user_id == User.id)
            .where(UserSettings.morning_digest_enabled.is_(True))
        )
        now = utc_now()
        for user, user_settings in result.all():
            user_now = to_user_timezone(now, user_settings.timezone)
            target_time = user_settings.morning_digest_time
            already_sent = user_settings.last_morning_digest_at
            if user_now.hour != target_time.hour or user_now.minute != target_time.minute:
                continue
            if already_sent and to_user_timezone(already_sent, user_settings.timezone).date() == user_now.date():
                continue
            text = await build_digest(session, user.id, user_settings.timezone)
            await send_message(user.telegram_id, text)
            user_settings.last_morning_digest_at = now
        await session.commit()
