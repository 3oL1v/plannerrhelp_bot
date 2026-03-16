from __future__ import annotations

from datetime import datetime, time

from pydantic import BaseModel

from app.schemas.common import APIModel


class UserSettingsOut(APIModel):
    timezone: str
    morning_digest_enabled: bool
    morning_digest_time: time
    notifications_enabled: bool
    default_reminder_minutes: int
    week_starts_on: str
    last_morning_digest_at: datetime | None


class UserSettingsUpdate(BaseModel):
    timezone: str | None = None
    morning_digest_enabled: bool | None = None
    morning_digest_time: time | None = None
    notifications_enabled: bool | None = None
    default_reminder_minutes: int | None = None
    week_starts_on: str | None = None
