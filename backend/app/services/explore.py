"""Explore: cheapest destinations from an origin (Google Travel Explore via SerpApi).

Results are cached as snapshots. A view (origin, trip type, month, duration) is
refreshed at most once per REFRESH_HOURS, and every refresh counts toward the
same SerpApi daily cap and monthly quota as everything else.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import runtime_settings
from ..config import Settings, get_settings
from ..db import utcnow
from ..flights import airport_info
from ..models import ExploreDestination, ExploreSnapshot, ProviderRun
from ..money import from_minor, to_minor
from ..providers.serpapi_google_flights import SerpApiGoogleFlightsProvider
from .quota import budget

REFRESH_HOURS = 6


def _key_filter(stmt, origin: str, trip_type: str, month: int, duration: int):
    stmt = stmt.where(
        ExploreSnapshot.origin == origin, ExploreSnapshot.trip_type == trip_type, ExploreSnapshot.month == month
    )
    if trip_type == "round_trip":
        stmt = stmt.where(ExploreSnapshot.travel_duration == duration)
    return stmt


def latest_snapshot(db: Session, origin: str, trip_type: str, month: int, duration: int) -> ExploreSnapshot | None:
    stmt = _key_filter(select(ExploreSnapshot), origin, trip_type, month, duration)
    return db.scalar(stmt.order_by(ExploreSnapshot.fetched_at_utc.desc()).limit(1))


def snapshot_view(snap: ExploreSnapshot | None, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    if snap is None:
        return {"snapshot": None, "destinations": [], "next_refresh_utc": None, "can_refresh": True}
    next_refresh = snap.fetched_at_utc + timedelta(hours=REFRESH_HOURS)
    dests = []
    for d in snap.destinations:
        info = airport_info(d.airport_code)
        dests.append({
            "name": d.name, "country": d.country, "airport_code": d.airport_code,
            "airport_name": info["name"] if info else None,
            "start_date": d.start_date, "end_date": d.end_date,
            "price": from_minor(d.price_minor), "currency": d.currency,
            "airline": d.airline, "airline_code": d.airline_code, "stops": d.stops,
            "duration_minutes": d.duration_minutes, "thumbnail": d.thumbnail,
        })
    return {
        "snapshot": {
            "id": snap.id, "origin": snap.origin, "trip_type": snap.trip_type, "month": snap.month,
            "travel_duration": snap.travel_duration, "currency": snap.currency, "passengers": snap.passengers,
            "fetched_at_utc": snap.fetched_at_utc,
        },
        "destinations": dests,
        "next_refresh_utc": next_refresh,
        "can_refresh": now >= next_refresh,
    }


def refresh(
    db: Session,
    *,
    origin: str,
    trip_type: str,
    month: int,
    duration: int,
    provider: SerpApiGoogleFlightsProvider | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    provider = provider or SerpApiGoogleFlightsProvider(settings)
    now = now or utcnow()
    prefs = runtime_settings.get_all(db)
    current = latest_snapshot(db, origin, trip_type, month, duration)

    def done(status: str, message: str) -> dict[str, Any]:
        return {"status": status, "message": message, **snapshot_view(latest_snapshot(db, origin, trip_type, month,
                                                                                         duration), now)}

    if not provider.configured:
        return done("skipped_unconfigured", "SERPAPI_API_KEY is not set")
    if current and now < current.fetched_at_utc + timedelta(hours=REFRESH_HOURS):
        return done("skipped_recent", f"These deals were refreshed less than {REFRESH_HOURS} hours ago.")
    b = budget(db, provider.name, int(prefs["max_queries_per_day"]), now, settings)
    if b.remaining < 1:
        return done("skipped_quota", f"Search budget used up (today {b.used_today}/{b.daily_cap}, "
                                     f"month {b.used_this_month}/{b.monthly_quota}).")

    run = ProviderRun(provider=provider.name, trigger="explore", started_at_utc=now, origin=origin,
                      status="running")
    db.add(run)
    db.commit()
    result = provider.explore(
        origin=origin, round_trip=trip_type == "round_trip", month=month, travel_duration=duration,
        currency=prefs["display_currency"], adults=int(prefs["passengers"]), max_attempts=b.remaining,
    )
    run.status = result.status
    run.queries_used = result.queries_used
    run.http_status = result.http_status
    run.message = f"Explore {trip_type} month={month}: {result.message}"
    run.finished_at_utc = utcnow()
    if result.status == "success":
        snap = ExploreSnapshot(
            origin=origin, trip_type=trip_type, month=month, travel_duration=duration,
            currency=prefs["display_currency"], passengers=int(prefs["passengers"]), fetched_at_utc=now,
            provider_run_id=run.id,
        )
        for d in result.destinations:
            snap.destinations.append(ExploreDestination(
                name=d.name[:120], country=(d.country or None), airport_code=d.airport_code,
                start_date=d.start_date, end_date=d.end_date, price_minor=to_minor(d.price), currency=d.currency,
                airline=d.airline, airline_code=d.airline_code, stops=d.stops,
                duration_minutes=d.duration_minutes, thumbnail=d.thumbnail,
            ))
        run.observations_created = len(result.destinations)
        db.add(snap)
    db.commit()
    return done(result.status, result.message)
