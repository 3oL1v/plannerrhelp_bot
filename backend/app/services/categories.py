from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


async def list_categories(session: AsyncSession, user_id: int) -> list[Category]:
    result = await session.execute(select(Category).where(Category.user_id == user_id).order_by(Category.is_default.desc(), Category.name))
    return list(result.scalars().all())


async def get_category(session: AsyncSession, user_id: int, category_id: int) -> Category | None:
    result = await session.execute(
        select(Category).where(Category.user_id == user_id, Category.id == category_id)
    )
    return result.scalar_one_or_none()


async def create_category(session: AsyncSession, user_id: int, payload: CategoryCreate) -> Category:
    category = Category(user_id=user_id, **payload.model_dump())
    if payload.is_default:
        existing = await list_categories(session, user_id)
        for item in existing:
            item.is_default = False
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def update_category(session: AsyncSession, category: Category, payload: CategoryUpdate) -> Category:
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_default"):
        result = await session.execute(select(Category).where(Category.user_id == category.user_id))
        for item in result.scalars().all():
            item.is_default = False
    for key, value in data.items():
        setattr(category, key, value)
    await session.commit()
    await session.refresh(category)
    return category


async def delete_category(session: AsyncSession, category: Category) -> None:
    await session.delete(category)
    await session.commit()
