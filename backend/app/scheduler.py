"""In-process scheduler (APScheduler).

IMPORTANT: this scheduler only runs while the backend process is running. If
your laptop sleeps or the server is stopped, checks are skipped (not queued).
See README "Cloud deployment" for an always-on setup.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings
from .db import SessionLocal
from . import runtime_settings

log = logging.getLogger("farewatch.scheduler")

_scheduler: BackgroundScheduler | None = None


def _job() -> None:
    from .services.collector import run_collection

    db = SessionLocal()
    try:
        run_collection(db, trigger="scheduled")
    except Exception:  # never let a failure kill the scheduler thread
        log.exception("Scheduled collection failed")
    finally:
        db.close()


def _times() -> list[tuple[int, int]]:
    db = SessionLocal()
    try:
        raw = runtime_settings.get(db, "collector_times")
    finally:
        db.close()
    out = []
    for part in str(raw).split(","):
        if part.strip():
            hh, mm = part.strip().split(":")
            out.append((int(hh), int(mm)))
    return out


def start() -> None:
    global _scheduler
    s = get_settings()
    if not s.collector_enabled:
        log.info("Collector disabled (COLLECTOR_ENABLED=false); no scheduled checks.")
        return
    if not s.serpapi_configured:
        log.warning("COLLECTOR_ENABLED=true but SERPAPI_API_KEY is empty; scheduled runs will be logged as skipped.")
    _scheduler = BackgroundScheduler(timezone=s.app_timezone)
    reschedule()
    _scheduler.start()
    log.info("Collector scheduler started (%s, %s)", s.app_timezone, s.collector_times)


def reschedule() -> None:
    if _scheduler is None:
        return
    for job in _scheduler.get_jobs():
        job.remove()
    tz = get_settings().app_timezone
    for hh, mm in _times():
        _scheduler.add_job(_job, CronTrigger(hour=hh, minute=mm, timezone=tz), id=f"collect-{hh:02d}{mm:02d}",
                           max_instances=1, coalesce=True, misfire_grace_time=1800)


def next_runs() -> list[str]:
    if _scheduler is None:
        return []
    return sorted(j.next_run_time.isoformat() for j in _scheduler.get_jobs() if j.next_run_time)


def running() -> bool:
    return _scheduler is not None and _scheduler.running


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
