from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.bot.application import BotApplication
from app.config import STATIC_DIR, get_settings
from app.db.session import create_engine, create_session_factory
from app.scheduler.jobs import create_scheduler


settings = get_settings()
engine = create_engine(settings)
session_factory = create_session_factory(engine)
bot_app = BotApplication(settings=settings, session_factory=session_factory)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.bot_app = bot_app if bot_app.bot else None
    scheduler = None
    await bot_app.start()
    if settings.enable_scheduler:
        scheduler = create_scheduler(session_factory, bot_app.send_message)
        scheduler.start()
    app.state.scheduler = scheduler
    yield
    if scheduler:
        scheduler.shutdown(wait=False)
    await bot_app.stop()
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

static_dir = Path(STATIC_DIR)
assets_dir = static_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
async def root():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"service": settings.app_name, "status": "ok"})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path == "health":
        return JSONResponse({"detail": "Not found"}, status_code=404)
    target = static_dir / full_path
    if target.exists() and target.is_file():
        return FileResponse(target)
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"detail": "Not found"}, status_code=404)
