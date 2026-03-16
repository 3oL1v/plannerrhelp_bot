from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import UserOut
from app.schemas.settings import UserSettingsOut


class TelegramInitRequest(BaseModel):
    init_data: str | None = None
    telegram_id: int | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramInitResponse(BaseModel):
    token: str
    user: UserOut
    settings: UserSettingsOut
