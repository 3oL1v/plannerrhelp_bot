from __future__ import annotations

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    color: str | None = None
    is_default: bool = False


class CategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    is_default: bool | None = None
