from __future__ import annotations

from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services.users import ensure_user, get_user_by_id
from app.utils.telegram import validate_init_data


class AuthError(Exception):
    pass


def build_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.app_secret, salt="planner-help-token")


def issue_token(settings: Settings, user_id: int) -> str:
    return build_serializer(settings).dumps({"user_id": user_id})


def decode_token(settings: Settings, token: str) -> int:
    try:
        payload = build_serializer(settings).loads(token, max_age=60 * 60 * 24 * 30)
    except BadSignature as exc:
        raise AuthError("Invalid token") from exc
    return int(payload["user_id"])


async def bootstrap_telegram_user(
    session: AsyncSession,
    settings: Settings,
    init_data: str | None,
    telegram_id: int | None,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
):
    if init_data and settings.telegram_bot_token:
        telegram_user = validate_init_data(init_data, settings.telegram_bot_token)
        if not telegram_user:
            raise AuthError("Invalid Telegram init data")
        telegram_id = int(telegram_user["id"])
        username = telegram_user.get("username")
        first_name = telegram_user.get("first_name")
        last_name = telegram_user.get("last_name")

    if telegram_id is None:
        raise AuthError("telegram_id is required")

    user = await ensure_user(session, settings, telegram_id, username, first_name, last_name)
    return user, issue_token(settings, user.id)


async def authenticate_token(session: AsyncSession, settings: Settings, token: str):
    user_id = decode_token(settings, token)
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise AuthError("User not found")
    return user
