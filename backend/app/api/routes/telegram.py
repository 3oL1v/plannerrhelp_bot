import logging

from aiogram.types import Update
from fastapi import APIRouter, HTTPException, Request, status


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request) -> dict[str, str]:
    bot_app = request.app.state.bot_app
    settings = request.app.state.settings
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if bot_app is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot disabled")
    payload = await request.json()
    update = Update.model_validate(payload)
    try:
        await bot_app.process_update(update)
    except Exception as exc:
        logger.exception("Telegram webhook update failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing failed") from exc
    return {"status": "accepted"}
