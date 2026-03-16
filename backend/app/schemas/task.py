from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    category_id: int | None = None
    priority: str = "medium"
    due_date: date | None = None
    due_time: time | None = None
    recurrence_rule: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category_id: int | None = None
    priority: str | None = None
    due_date: date | None = None
    due_time: time | None = None
    recurrence_rule: str | None = None
    status: str | None = None


class TaskReschedule(BaseModel):
    due_date: date | None = None
    due_time: time | None = None
