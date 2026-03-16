from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.entities import User
from app.schemas.common import TaskOut
from app.schemas.task import TaskCreate, TaskReschedule, TaskUpdate
from app.services.tasks import complete_task, create_task, delete_task, get_task, list_tasks, reschedule_task, update_task


router = APIRouter()


@router.get("", response_model=list[TaskOut])
async def get_tasks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TaskOut]:
    return await list_tasks(session, user.id)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task_detail(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskOut:
    task = await get_task(session, user.id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def post_task(
    payload: TaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskOut:
    return await create_task(session, user.id, payload)


@router.patch("/{task_id}", response_model=TaskOut)
async def patch_task(
    task_id: int,
    payload: TaskUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskOut:
    task = await get_task(session, user.id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return await update_task(session, task, payload)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    task = await get_task(session, user.id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await delete_task(session, task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/complete", response_model=TaskOut)
async def complete_task_route(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskOut:
    task = await get_task(session, user.id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return await complete_task(session, task)


@router.post("/{task_id}/reschedule", response_model=TaskOut)
async def reschedule_task_route(
    task_id: int,
    payload: TaskReschedule,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskOut:
    task = await get_task(session, user.id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return await reschedule_task(session, task, payload)
