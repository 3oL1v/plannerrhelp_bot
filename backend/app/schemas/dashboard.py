from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.common import EventOut, InboxOut, TaskOut


class TodayDashboard(BaseModel):
    date: date
    next_event: EventOut | None
    events: list[EventOut]
    tasks: list[TaskOut]
    completed_tasks: list[TaskOut]
    overdue_tasks: list[TaskOut]
    inbox_preview: list[InboxOut]


class WeekDaySummary(BaseModel):
    date: date
    tasks: list[TaskOut]
    events: list[EventOut]


class WeekDashboard(BaseModel):
    week_start: date
    week_end: date
    days: list[WeekDaySummary]
