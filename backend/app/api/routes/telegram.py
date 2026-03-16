from aiogram.types import Update
from fastapi import APIRouter, HTTPException, Request, status


router = APIRouter()


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
    await bot_app.process_update(update)
    return {"status": "accepted"}
