from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.entities import User
from app.schemas.common import InboxOut
from app.schemas.inbox import InboxConvertToEvent, InboxConvertToTask, InboxCreate, InboxUpdate
from app.services.inbox import (
    convert_inbox_to_event,
    convert_inbox_to_task,
    create_inbox_item,
    delete_inbox_item,
    get_inbox_item,
    list_inbox,
    update_inbox_item,
)
from app.services.settings import get_settings_for_user


router = APIRouter()


@router.get("", response_model=list[InboxOut])
async def get_inbox(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[InboxOut]:
    return await list_inbox(session, user.id)


@router.post("", response_model=InboxOut, status_code=status.HTTP_201_CREATED)
async def post_inbox(
    payload: InboxCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> InboxOut:
    return await create_inbox_item(session, user.id, payload)


@router.patch("/{inbox_id}", response_model=InboxOut)
async def patch_inbox(
    inbox_id: int,
    payload: InboxUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> InboxOut:
    item = await get_inbox_item(session, user.id, inbox_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return await update_inbox_item(session, item, payload)


@router.delete("/{inbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_inbox(
    inbox_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    item = await get_inbox_item(session, user.id, inbox_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    await delete_inbox_item(session, item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{inbox_id}/convert-to-task", status_code=status.HTTP_204_NO_CONTENT)
async def inbox_to_task(
    inbox_id: int,
    payload: InboxConvertToTask,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    item = await get_inbox_item(session, user.id, inbox_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    await convert_inbox_to_task(session, user.id, item, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{inbox_id}/convert-to-event", status_code=status.HTTP_204_NO_CONTENT)
async def inbox_to_event_route(
    inbox_id: int,
    payload: InboxConvertToEvent,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    item = await get_inbox_item(session, user.id, inbox_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    user_settings = await get_settings_for_user(session, user.id)
    await convert_inbox_to_event(session, user.id, item, payload, user_settings.timezone)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
