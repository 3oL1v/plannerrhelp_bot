from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.entities import User
from app.schemas.dashboard import TodayDashboard, WeekDashboard
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
