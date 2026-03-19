from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Event, InboxItem, InboxStatus, Task
from app.schemas.event import EventCreate
from app.schemas.inbox import InboxConvertToEvent, InboxConvertToTask, InboxCreate, InboxUpdate
from app.schemas.task import TaskCreate
from app.services.events import create_event
from app.services.tasks import create_task
from app.utils.datetime import utc_now


async def list_inbox(session: AsyncSession, user_id: int) -> list[InboxItem]:
    result = await session.execute(
        select(InboxItem)
        .where(
            InboxItem.user_id == user_id,
            InboxItem.deleted_at.is_(None),
            InboxItem.status == InboxStatus.ACTIVE.value,
        )
        .order_by(InboxItem.created_at.desc())
    )
    return list(result.scalars().all())


async def get_inbox_item(session: AsyncSession, user_id: int, inbox_id: int) -> InboxItem | None:
    result = await session.execute(
        select(InboxItem).where(InboxItem.user_id == user_id, InboxItem.id == inbox_id, InboxItem.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def create_inbox_item(session: AsyncSession, user_id: int, payload: InboxCreate) -> InboxItem:
    item = InboxItem(user_id=user_id, **payload.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update_inbox_item(session: AsyncSession, item: InboxItem, payload: InboxUpdate) -> InboxItem:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    if item.status == InboxStatus.PROCESSED.value and item.processed_at is None:
        item.processed_at = utc_now()
    await session.commit()
    await session.refresh(item)
    return item


async def delete_inbox_item(session: AsyncSession, item: InboxItem) -> None:
    item.deleted_at = utc_now()
    item.status = InboxStatus.DELETED.value
    await session.commit()


async def convert_inbox_to_task(
    session: AsyncSession,
    user_id: int,
    item: InboxItem,
    payload: InboxConvertToTask,
) -> Task:
    task = TaskCreate(
        title=payload.title or item.text[:255],
        description=payload.description,
        category_id=payload.category_id,
        priority=payload.priority,
        due_date=payload.due_date,
        due_time=payload.due_time,
    )
    created_task = await create_task(session, user_id, task, source_inbox_item_id=item.id)
    item.status = InboxStatus.PROCESSED.value
    item.processed_at = utc_now()
    await session.commit()
    return created_task


async def convert_inbox_to_event(
    session: AsyncSession,
    user_id: int,
    item: InboxItem,
    payload: InboxConvertToEvent,
) -> Event:
    event = EventCreate(
        title=payload.title or item.text[:255],
        description=payload.description,
        category_id=payload.category_id,
        event_date=payload.event_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_minutes=payload.duration_minutes,
        location=payload.location,
    )
    created_event = await create_event(session, user_id, event, source_inbox_item_id=item.id)
    item.status = InboxStatus.PROCESSED.value
    item.processed_at = utc_now()
    await session.commit()
    return created_event
