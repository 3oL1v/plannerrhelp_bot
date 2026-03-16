from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.entities import User
from app.services.auth import AuthError, authenticate_token


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_app_settings() -> Settings:
    return get_settings()


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        return await authenticate_token(session, settings, token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
