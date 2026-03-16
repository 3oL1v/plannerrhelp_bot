from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel


class EventCreate(BaseModel):
    title: str
    description: str | None = None
    category_id: int | None = None
    event_date: date
    start_time: time
    end_time: time | None = None
    duration_minutes: int | None = None
    location: str | None = None
    recurrence_rule: str | None = None


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category_id: int | None = None
    event_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = None
    location: str | None = None
    recurrence_rule: str | None = None
    status: str | None = None


class EventReschedule(BaseModel):
    event_date: date
    start_time: time
    end_time: time | None = None
    duration_minutes: int | None = None
