from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel


class InboxCreate(BaseModel):
    text: str


class InboxUpdate(BaseModel):
    text: str | None = None
    status: str | None = None


class InboxConvertToTask(BaseModel):
    title: str | None = None
    description: str | None = None
    category_id: int | None = None
    priority: str = "medium"
    due_date: date | None = None
    due_time: time | None = None


class InboxConvertToEvent(BaseModel):
    title: str | None = None
    description: str | None = None
    category_id: int | None = None
    event_date: date
    start_time: time
    end_time: time | None = None
    duration_minutes: int | None = None
    location: str | None = None
