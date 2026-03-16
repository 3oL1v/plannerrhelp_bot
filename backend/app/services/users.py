from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.entities import Category, User, UserSettings
from app.utils.datetime import utc_now


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_latest_seen_user(session: AsyncSession) -> User | None:
    result = await session.execute(
        select(User)
        .order_by(User.last_seen_at.is_(None), desc(User.last_seen_at), desc(User.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_real_user(session: AsyncSession, bot_telegram_id: int | None) -> User | None:
    query = select(User).where(User.telegram_id != 1)
    if bot_telegram_id is not None:
        query = query.where(User.telegram_id != bot_telegram_id)
    result = await session.execute(
        query.order_by(User.last_seen_at.is_(None), desc(User.last_seen_at), desc(User.created_at)).limit(1)
    )
    return result.scalar_one_or_none()


async def ensure_user(
    session: AsyncSession,
    settings: Settings,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            last_seen_at=utc_now(),
        )
        user.settings = UserSettings(timezone=settings.default_timezone)
        session.add(user)
        await session.flush()
        session.add(
            Category(
                user_id=user.id,
                name="General",
                color="#6B7A8F",
                is_default=True,
            )
        )
    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.last_seen_at = utc_now()

    await session.commit()
    await session.refresh(user)
    return user
