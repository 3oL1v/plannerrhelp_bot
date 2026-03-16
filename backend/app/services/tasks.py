from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskReschedule, TaskUpdate
from app.services.settings import get_settings_for_user
from app.services.reminders import cancel_entity_reminders, sync_task_reminder
from app.utils.datetime import utc_now


def base_task_query(user_id: int) -> Select[tuple[Task]]:
    return select(Task).where(Task.user_id == user_id, Task.deleted_at.is_(None))


async def list_tasks(session: AsyncSession, user_id: int) -> list[Task]:
    result = await session.execute(
        base_task_query(user_id).order_by(
            Task.due_date.is_(None),
            Task.due_date,
            Task.due_time.is_(None),
            Task.due_time,
            Task.created_at.desc(),
        )
    )
    return list(result.scalars().all())


async def get_task(session: AsyncSession, user_id: int, task_id: int) -> Task | None:
    result = await session.execute(base_task_query(user_id).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def create_task(session: AsyncSession, user_id: int, payload: TaskCreate, source_inbox_item_id: int | None = None) -> Task:
    task = Task(user_id=user_id, source_inbox_item_id=source_inbox_item_id, **payload.model_dump())
    session.add(task)
    await session.flush()
    user_settings = await get_settings_for_user(session, user_id)
    await sync_task_reminder(session, task, user_settings)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task(session: AsyncSession, task: Task, payload: TaskUpdate) -> Task:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    user_settings = await get_settings_for_user(session, task.user_id)
    await sync_task_reminder(session, task, user_settings)
    await session.commit()
    await session.refresh(task)
    return task


async def complete_task(session: AsyncSession, task: Task) -> Task:
    task.status = TaskStatus.COMPLETED.value
    task.completed_at = utc_now()
    await cancel_entity_reminders(session, task.user_id, "task", task.id)
    await session.commit()
    await session.refresh(task)
    return task


async def reschedule_task(session: AsyncSession, task: Task, payload: TaskReschedule) -> Task:
    task.due_date = payload.due_date
    task.due_time = payload.due_time
    task.status = TaskStatus.OPEN.value
    task.completed_at = None
    user_settings = await get_settings_for_user(session, task.user_id)
    await sync_task_reminder(session, task, user_settings)
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task: Task) -> None:
    task.deleted_at = utc_now()
    await cancel_entity_reminders(session, task.user_id, "task", task.id)
    await session.commit()
