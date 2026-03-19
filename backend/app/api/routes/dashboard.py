from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bot_sync import refresh_bot_today_view
from app.api.deps import get_current_user, get_db_session
from app.models.entities import User
from app.schemas.dashboard import TodayDashboard, WeekDashboard
from app.services.settings import clear_today_completed_for_user
from app.services.dashboard import build_today_dashboard, build_week_dashboard


router = APIRouter()


@router.get("/today", response_model=TodayDashboard)
async def get_today_dashboard(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TodayDashboard:
    return await build_today_dashboard(session, user.id)


@router.get("/week", response_model=WeekDashboard)
async def get_week_dashboard(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> WeekDashboard:
    return await build_week_dashboard(session, user.id)


@router.post("/today/completed/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_today_completed(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await clear_today_completed_for_user(session, user.id)
    await refresh_bot_today_view(request, user.id)
