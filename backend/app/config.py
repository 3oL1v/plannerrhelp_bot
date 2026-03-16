from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
STATIC_DIR = BACKEND_DIR / "app" / "static"
LOCAL_SQLITE_PATH = (BACKEND_DIR / "planner_local.db").resolve().as_posix()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    app_name: str = "Planner Help Bot"
    app_secret: str = "planner-help-dev-secret"
    app_base_url: str | None = None
    webapp_url: str | None = None
    database_url: str = f"sqlite+aiosqlite:///{LOCAL_SQLITE_PATH}"
    telegram_bot_token: str | None = None
    telegram_webhook_secret: str = "planner-help-webhook"
    telegram_use_polling: bool = True
    enable_scheduler: bool = True
    default_timezone: str = "Europe/Moscow"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @computed_field
    @property
    def static_dir(self) -> str:
        return str(STATIC_DIR)

    @computed_field
    @property
    def sync_database_url(self) -> str:
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("sqlite+aiosqlite:///"):
            return self.database_url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
        return self.database_url

    @computed_field
    @property
    def effective_webapp_url(self) -> str | None:
        if self.webapp_url:
            return self.webapp_url.rstrip("/")
        if self.app_base_url:
            return self.app_base_url.rstrip("/")
        return None

    @computed_field
    @property
    def webhook_path(self) -> str:
        return f"/api/v1/telegram/webhook/{self.telegram_webhook_secret}"

    @computed_field
    @property
    def webhook_url(self) -> str | None:
        if not self.app_base_url:
            return None
        return f"{self.app_base_url.rstrip('/')}{self.webhook_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
