from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.entities import User
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.common import CategoryOut
from app.services.categories import create_category, delete_category, get_category, list_categories, update_category


router = APIRouter()


@router.get("", response_model=list[CategoryOut])
async def get_categories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CategoryOut]:
    return await list_categories(session, user.id)


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def post_category(
    payload: CategoryCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CategoryOut:
    return await create_category(session, user.id, payload)


@router.patch("/{category_id}", response_model=CategoryOut)
async def patch_category(
    category_id: int,
    payload: CategoryUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CategoryOut:
    category = await get_category(session, user.id, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return await update_category(session, category, payload)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_category(
    category_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    category = await get_category(session, user.id, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    await delete_category(session, category)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
