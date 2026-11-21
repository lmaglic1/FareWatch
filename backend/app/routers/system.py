"""Settings, provider status, collector control and demo mode."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import runtime_settings, scheduler
from ..config import get_settings
from ..db import get_db, utcnow
from ..models import ProviderRun
from ..money import SUPPORTED_CURRENCIES
from ..providers.serpapi_google_flights import SerpApiGoogleFlightsProvider
from ..services import demo
from ..services.collector import run_collection
from ..services.quota import budget
from .dashboard import last_success

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return {"ok": True, "time_utc": utcnow()}


def _validate(changes: dict[str, Any]) -> None:
    if "display_currency" in changes and changes["display_currency"] not in SUPPORTED_CURRENCIES:
        raise ValueError("Unsupported currency")
    if "baggage_profile" in changes and changes["baggage_profile"] not in {
        "under_seat_only", "priority_trolley", "checked_bag"
    }:
        raise ValueError("Invalid baggage profile")
    if "discount_club" in changes and changes["discount_club"] not in {"public", "member"}:
        raise ValueError("Invalid Discount Club preference")
    for k, lo, hi in (("median_threshold_pct", 1, 60), ("drop_alert_pct", 1, 90)):
        if k in changes:
            try:
                v = Decimal(str(changes[k]))
            except InvalidOperation as exc:
                raise ValueError(f"{k} must be a number") from exc
            if not lo <= v <= hi:
                raise ValueError(f"{k} must be between {lo} and {hi}")
            changes[k] = str(v)
    for k, lo, hi in (("min_samples_for_status", 2, 100), ("max_queries_per_day", 0, 50),
                      ("min_minutes_between_checks", 10, 1440), ("passengers", 1, 9)):
        if k in changes:
            v = int(changes[k])
            if not lo <= v <= hi:
                raise ValueError(f"{k} must be between {lo} and {hi}")
            changes[k] = v
    if "collector_times" in changes:
        parts = [p.strip() for p in str(changes["collector_times"]).split(",") if p.strip()]
        if not parts or len(parts) > 6:
            raise ValueError("collector_times needs 1-6 HH:MM values")
        for p in parts:
            hh, mm = p.split(":")
            if not (0 <= int(hh) < 24 and 0 <= int(mm) < 60):
                raise ValueError(f"Invalid time {p}")
        changes["collector_times"] = ",".join(parts)


@router.get("/settings")
def get_settings_view(db: Session = Depends(get_db)):
    s = get_settings()
    p = runtime_settings.get_all(db)
    prov = SerpApiGoogleFlightsProvider(s)
    b = budget(db, prov.name, int(p["max_queries_per_day"]))
    ls = last_success(db)
    return {
        "preferences": p,
        "providers": [
            {"name": "manual", "label": "Manual entry", "connected": True,
             "description": "Fares you saw yourself, with source URL and timestamp."},
            {"name": "csv_import", "label": "CSV import", "connected": True,
             "description": "Historical observations imported from a validated CSV file."},
            {"name": prov.name, "label": "SerpApi Google Flights", "connected": prov.configured,
             "description": "Optional. Requires SERPAPI_API_KEY in .env. Reads Google Flights results; "
                            "does not contact Wizz Air.",
             "last_successful_fetch_utc": ls.started_at_utc if ls else None},
        ],
        "collector": {
            "enabled": s.collector_enabled,
            "scheduler_running": scheduler.running(),
            "next_runs": scheduler.next_runs(),
            "timezone": s.app_timezone,
            "budget": {**b.__dict__, "remaining_today": b.remaining_today, "remaining_month": b.remaining_month},
        },
        "email_configured": s.email_configured,
        "currencies": sorted(SUPPORTED_CURRENCIES),
    }


@router.put("/settings")
def update_settings(changes: dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    unknown = set(changes) - runtime_settings.EDITABLE
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown setting(s): {', '.join(sorted(unknown))}")
    try:
        _validate(changes)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    turning_demo_on = changes.get("demo_mode") is True and not runtime_settings.get(db, "demo_mode")
    result = runtime_settings.update(db, changes)
    if turning_demo_on:
        demo.load_demo(db)
    if "collector_times" in changes:
        scheduler.reschedule()
    return result


@router.get("/collector/runs")
def collector_runs(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(ProviderRun).order_by(ProviderRun.started_at_utc.desc()).limit(min(limit, 500)))
    return [{c.name: getattr(r, c.name) for c in ProviderRun.__table__.columns} for r in rows]


@router.post("/collector/run")
def collector_run_now(
    include_comparisons: bool = False,
    comparison_count: int = Query(default=1, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Manual refresh. Respects the daily cap, monthly quota and minimum interval.

    Every search also imports Google's price history for that route/date when it can be
    attributed to a single nonstop flight.
    """
    return run_collection(db, trigger="manual", include_comparisons=include_comparisons,
                          comparison_count=comparison_count)


@router.get("/provider/serpapi/account")
def serpapi_account():
    """Free SerpApi account check (does not consume searches)."""
    return SerpApiGoogleFlightsProvider(get_settings()).account()


@router.post("/demo/reload")
def demo_reload(db: Session = Depends(get_db)):
    if not runtime_settings.get(db, "demo_mode"):
        raise HTTPException(status_code=409, detail="Enable demo mode first")
    return {"created": demo.load_demo(db)}


@router.delete("/demo")
def demo_clear(db: Session = Depends(get_db)):
    demo.clear_demo(db)
    runtime_settings.update(db, {"demo_mode": False})
    return {"ok": True}

