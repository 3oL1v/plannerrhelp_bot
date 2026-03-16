from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import UserSettings
from app.schemas.settings import UserSettingsUpdate


async def get_settings_for_user(session: AsyncSession, user_id: int) -> UserSettings:
    result = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    return result.scalar_one()


async def update_settings_for_user(session: AsyncSession, user_id: int, payload: UserSettingsUpdate) -> UserSettings:
    settings = await get_settings_for_user(session, user_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    await session.commit()
    await session.refresh(settings)
    return settings
