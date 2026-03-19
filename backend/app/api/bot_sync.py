from __future__ import annotations

from fastapi import Request


async def refresh_bot_today_view(request: Request, user_id: int) -> None:
    bot_app = getattr(request.app.state, "bot_app", None)
    if bot_app is None:
        return
    await bot_app.refresh_user_views(user_id)
