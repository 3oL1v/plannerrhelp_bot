from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.dashboard import build_morning_digest_text
from app.services.reminders import dispatch_due_reminders, dispatch_morning_digests


def create_scheduler(
    session_factory: async_sessionmaker[AsyncSession],
    send_message,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        dispatch_due_reminders,
        "interval",
        seconds=60,
        kwargs={"session_factory": session_factory, "send_message": send_message},
    )
    scheduler.add_job(
        dispatch_morning_digests,
        "interval",
        seconds=60,
        kwargs={
            "session_factory": session_factory,
            "send_message": send_message,
            "build_digest": build_morning_digest_text,
        },
    )
    return scheduler
