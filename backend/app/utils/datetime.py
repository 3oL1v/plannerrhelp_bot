from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def combine_user_datetime(target_date: date, target_time: time | None, tz_name: str) -> datetime:
    zone = ZoneInfo(tz_name)
    local_dt = datetime.combine(target_date, target_time or time.min).replace(tzinfo=zone)
    return local_dt.astimezone(timezone.utc)


def to_user_timezone(value: datetime, tz_name: str) -> datetime:
    return value.astimezone(ZoneInfo(tz_name))


def today_in_timezone(tz_name: str) -> date:
    return utc_now().astimezone(ZoneInfo(tz_name)).date()


def week_bounds(target_date: date, week_starts_on: str) -> tuple[date, date]:
    weekday = target_date.weekday()
    if week_starts_on == "sunday":
        offset = (weekday + 1) % 7
    else:
        offset = weekday
    start = target_date - timedelta(days=offset)
    end = start + timedelta(days=6)
    return start, end
