from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(APIModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


class CategoryOut(APIModel):
    id: int
    name: str
    color: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class InboxOut(APIModel):
    id: int
    text: str
    status: str
    created_at: datetime
    processed_at: datetime | None
    deleted_at: datetime | None


class TaskOut(APIModel):
    id: int
    source_inbox_item_id: int | None
    category_id: int | None
    title: str
    description: str | None
    status: str
    priority: str
    due_date: date | None
    due_time: time | None
    recurrence_rule: str | None
    completed_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EventOut(APIModel):
    id: int
    source_inbox_item_id: int | None
    category_id: int | None
    title: str
    description: str | None
    event_date: date
    start_time: time
    end_time: time | None
    duration_minutes: int | None
    location: str | None
    status: str
    recurrence_rule: str | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
