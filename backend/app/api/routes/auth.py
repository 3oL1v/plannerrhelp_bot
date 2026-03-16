from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_db_session
from app.config import Settings
from app.schemas.auth import TelegramInitRequest, TelegramInitResponse
from app.schemas.settings import UserSettingsOut
from app.services.auth import AuthError, bootstrap_telegram_user
from app.services.settings import get_settings_for_user


router = APIRouter(prefix="/auth")


@router.post("/telegram/init", response_model=TelegramInitResponse)
async def telegram_init(
    payload: TelegramInitRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> TelegramInitResponse:
    try:
        user, token = await bootstrap_telegram_user(
            session=session,
            settings=settings,
            init_data=payload.init_data,
            telegram_id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    user_settings = await get_settings_for_user(session, user.id)
    return TelegramInitResponse(token=token, user=user, settings=UserSettingsOut.model_validate(user_settings))
