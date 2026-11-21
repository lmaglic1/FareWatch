"""Provider query budget: daily cap (local day), monthly quota, minimum interval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import utcnow
from ..models import ProviderRun, SearchTarget


def _local_day_bounds(now: datetime, tz: str) -> tuple[datetime, datetime]:
    local = now.astimezone(ZoneInfo(tz))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(ZoneInfo("UTC")), (start + timedelta(days=1)).astimezone(ZoneInfo("UTC"))


def _local_month_start(now: datetime, tz: str) -> datetime:
    local = now.astimezone(ZoneInfo(tz))
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(ZoneInfo("UTC"))


def queries_used(db: Session, provider: str, since: datetime, until: datetime | None = None) -> int:
    stmt = select(func.coalesce(func.sum(ProviderRun.queries_used), 0)).where(
        ProviderRun.provider == provider, ProviderRun.started_at_utc >= since
    )
    if until is not None:
        stmt = stmt.where(ProviderRun.started_at_utc < until)
    return int(db.scalar(stmt) or 0)


@dataclass
class Budget:
    used_today: int
    daily_cap: int
    used_this_month: int
    monthly_quota: int

    @property
    def remaining_today(self) -> int:
        return max(0, self.daily_cap - self.used_today)

    @property
    def remaining_month(self) -> int:
        return max(0, self.monthly_quota - self.used_this_month)

    @property
    def remaining(self) -> int:
        return min(self.remaining_today, self.remaining_month)


def budget(
    db: Session, provider: str, daily_cap: int, now: datetime | None = None, settings: Settings | None = None
) -> Budget:
    s = settings or get_settings()
    now = now or utcnow()
    start, end = _local_day_bounds(now, s.app_timezone)
    return Budget(
        used_today=queries_used(db, provider, start, end),
        daily_cap=daily_cap,
        used_this_month=queries_used(db, provider, _local_month_start(now, s.app_timezone)),
        monthly_quota=s.serpapi_monthly_quota,
    )


def checked_recently(target: SearchTarget, min_minutes: int, now: datetime | None = None) -> bool:
    if target.last_checked_utc is None:
        return False
    return (now or utcnow()) - target.last_checked_utc < timedelta(minutes=min_minutes)
