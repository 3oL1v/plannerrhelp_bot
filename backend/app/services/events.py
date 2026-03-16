from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Event
from app.schemas.event import EventCreate, EventReschedule, EventUpdate
from app.services.reminders import cancel_entity_reminders, sync_event_reminder
from app.services.settings import get_settings_for_user
from app.utils.datetime import utc_now


def base_event_query(user_id: int) -> Select[tuple[Event]]:
    return select(Event).where(Event.user_id == user_id, Event.deleted_at.is_(None))


async def list_events(session: AsyncSession, user_id: int) -> list[Event]:
    result = await session.execute(base_event_query(user_id).order_by(Event.event_date, Event.start_time))
    return list(result.scalars().all())


async def get_event(session: AsyncSession, user_id: int, event_id: int) -> Event | None:
    result = await session.execute(base_event_query(user_id).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def create_event(session: AsyncSession, user_id: int, payload: EventCreate, source_inbox_item_id: int | None = None) -> Event:
    event = Event(user_id=user_id, source_inbox_item_id=source_inbox_item_id, **payload.model_dump())
    session.add(event)
    await session.flush()
    user_settings = await get_settings_for_user(session, user_id)
    await sync_event_reminder(session, event, user_settings)
    await session.commit()
    await session.refresh(event)
    return event


async def update_event(session: AsyncSession, event: Event, payload: EventUpdate) -> Event:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    user_settings = await get_settings_for_user(session, event.user_id)
    await sync_event_reminder(session, event, user_settings)
    await session.commit()
    await session.refresh(event)
    return event


async def reschedule_event(session: AsyncSession, event: Event, payload: EventReschedule) -> Event:
    event.event_date = payload.event_date
    event.start_time = payload.start_time
    event.end_time = payload.end_time
    event.duration_minutes = payload.duration_minutes
    user_settings = await get_settings_for_user(session, event.user_id)
    await sync_event_reminder(session, event, user_settings)
    await session.commit()
    await session.refresh(event)
    return event


async def delete_event(session: AsyncSession, event: Event) -> None:
    event.deleted_at = utc_now()
    await cancel_entity_reminders(session, event.user_id, "event", event.id)
    await session.commit()
