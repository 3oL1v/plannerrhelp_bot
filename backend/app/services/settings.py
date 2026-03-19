from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import UserSettings
from app.schemas.settings import UserSettingsUpdate
from app.utils.datetime import utc_now


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


async def persist_bot_today_slots(
    session: AsyncSession,
    user_id: int,
    *,
    chat_id: int | None,
    summary_message_id: int | None,
    events_message_id: int | None,
    tasks_message_id: int | None,
) -> UserSettings:
    settings = await get_settings_for_user(session, user_id)
    settings.bot_chat_id = chat_id
    settings.bot_summary_message_id = summary_message_id
    settings.bot_events_message_id = events_message_id
    settings.bot_tasks_message_id = tasks_message_id
    await session.commit()
    await session.refresh(settings)
    return settings


async def clear_today_completed_for_user(session: AsyncSession, user_id: int) -> UserSettings:
    settings = await get_settings_for_user(session, user_id)
    settings.today_completed_hidden_before = utc_now()
    await session.commit()
    await session.refresh(settings)
    return settings
