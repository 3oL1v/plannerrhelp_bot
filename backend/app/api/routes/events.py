from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bot_sync import refresh_bot_today_view
from app.api.deps import get_current_user, get_db_session
from app.models.entities import User
from app.schemas.common import EventOut
from app.schemas.event import EventCreate, EventReschedule, EventUpdate
from app.services.events import create_event, delete_event, get_event, list_events, reschedule_event, update_event


router = APIRouter()


@router.get("", response_model=list[EventOut])
async def get_events(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[EventOut]:
    return await list_events(session, user.id)


@router.get("/{event_id}", response_model=EventOut)
async def get_event_detail(
    event_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EventOut:
    event = await get_event(session, user.id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def post_event(
    request: Request,
    payload: EventCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EventOut:
    event = await create_event(session, user.id, payload)
    await refresh_bot_today_view(request, user.id)
    return event


@router.patch("/{event_id}", response_model=EventOut)
async def patch_event(
    request: Request,
    event_id: int,
    payload: EventUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EventOut:
    event = await get_event(session, user.id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    updated = await update_event(session, event, payload)
    await refresh_bot_today_view(request, user.id)
    return updated


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_event(
    request: Request,
    event_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    event = await get_event(session, user.id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    await delete_event(session, event)
    await refresh_bot_today_view(request, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{event_id}/reschedule", response_model=EventOut)
async def reschedule_event_route(
    request: Request,
    event_id: int,
    payload: EventReschedule,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EventOut:
    event = await get_event(session, user.id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    updated = await reschedule_event(session, event, payload)
    await refresh_bot_today_view(request, user.id)
    return updated
