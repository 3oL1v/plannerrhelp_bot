from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.entities import User
from app.schemas.settings import UserSettingsOut, UserSettingsUpdate
from app.services.settings import get_settings_for_user, update_settings_for_user


router = APIRouter()


@router.get("", response_model=UserSettingsOut)
async def get_settings_route(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserSettingsOut:
    return await get_settings_for_user(session, user.id)


@router.patch("", response_model=UserSettingsOut)
async def patch_settings_route(
    payload: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserSettingsOut:
    return await update_settings_for_user(session, user.id, payload)
