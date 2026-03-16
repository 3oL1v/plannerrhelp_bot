from fastapi import APIRouter

from app.api.routes import auth, categories, dashboard, events, health, inbox, settings, tasks, telegram


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(inbox.router, prefix="/inbox", tags=["inbox"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
api_router.include_router(health.router, tags=["health"])
