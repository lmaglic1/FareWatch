"""Automated / manual collection via the SerpApi provider.

Rules:
* Runs only when a provider key is configured (scheduled runs additionally need COLLECTOR_ENABLED=true).
* Never exceeds the daily cap (local Europe/Sarajevo day) or the monthly quota.
* Skips a route/date checked within ``min_minutes_between_checks``.
* Every attempt, success or failure, is logged in ``provider_runs``.
* A failed query produces *no* observation. Mock data is never substituted.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import utcnow
from ..flights import get_or_create_flight
from ..models import FlightIdentity, ProviderRun, SearchTarget, Source, Verification
from ..providers.base import LegCandidate, SearchResult
from ..providers.serpapi_google_flights import SerpApiGoogleFlightsProvider
from .. import runtime_settings
from .alerts import evaluate_alerts
from .observations import record_observation
from .quota import budget, checked_recently

log = logging.getLogger("farewatch.collector")

COMPARISON_ROUTES = (("SJJ", "FCO"), ("FCO", "SJJ"))


def ensure_comparison_targets(db: Session, settings: Settings | None = None) -> int:
    """Create comparison search targets (Nov 2026 - Jan 2027, both directions)."""
    settings = settings or get_settings()
    start = date.fromisoformat(settings.comparison_window_start)
    end = date.fromisoformat(settings.comparison_window_end)
    existing = {
        (t.origin, t.destination, t.search_date) for t in db.scalars(select(SearchTarget))
    }
    created = 0
    d = start
    while d <= end:
        for o, de in COMPARISON_ROUTES:
            if (o, de, d) not in existing:
                db.add(SearchTarget(origin=o, destination=de, search_date=d, kind="comparison"))
                created += 1
        d += timedelta(days=1)
    db.commit()
    return created


def _target_dates(db: Session) -> list[date]:
    return [t.search_date for t in db.scalars(select(SearchTarget).where(SearchTarget.kind == "target"))]


def pick_comparison(db: Session, today: date) -> SearchTarget | None:
    """Least-recently-checked comparison date; never-checked dates closest to the trip first."""
    targets = _target_dates(db) or [today]
    cands = [
        t for t in db.scalars(
            select(SearchTarget).where(SearchTarget.kind == "comparison", SearchTarget.active.is_(True))
        )
        if t.search_date > today
    ]
    if not cands:
        return None

    def sort_key(t: SearchTarget):
        dist = min(abs((t.search_date - td).days) for td in targets)
        checked = t.last_checked_utc.timestamp() if t.last_checked_utc else -1.0
        return (checked, dist, t.search_date)

    return sorted(cands, key=sort_key)[0]


def _remaining_scheduled_runs_today(times: list[tuple[int, int]], now_local: datetime) -> int:
    return sum(1 for hh, mm in times if time(hh, mm) > now_local.time())


def _store_candidates(
    db: Session,
    result: SearchResult,
    settings: Settings,
    prefs: dict[str, Any],
    run: ProviderRun,
    target: SearchTarget,
) -> int:
    created = 0
    for c in result.candidates:
        if c.price is None:
            continue
        is_target_flight = (
            target.kind == "target" and target.expected_flight_number == c.flight_number
        )
        flight = get_or_create_flight(
            db, origin=c.origin, destination=c.destination, flight_date=c.departure_local.date(),
            flight_number=c.flight_number, airline=c.airline,
            dep=c.departure_local.time(), arr=c.arrival_local.time(),
            schedule_status="provider_reported",
        )
        if is_target_flight:
            _update_schedule_status(flight, c)
        res = record_observation(
            db, flight=flight, price_total=c.price, currency=c.currency, source=Source.SERPAPI.value,
            verification=Verification.API_REPORTED.value, display_currency=prefs["display_currency"],
            captured_at_utc=run.started_at_utc, passengers=int(prefs["passengers"]),
            fare_product=settings.serpapi_assumed_fare_product,
            baggage_profile=settings.serpapi_assumed_baggage_profile,
            taxes_fees_included="yes", discount_club="public", profile_assumed=True,
            notes=(
                "Google Flights via SerpApi. Fare product/baggage are assumed "
                f"({settings.serpapi_assumed_fare_product}, {settings.serpapi_assumed_baggage_profile}); "
                "verify on the airline site."
            ),
            provider_run_id=run.id,
        )
        if res.observation is not None:
            created += 1
            evaluate_alerts(db, res.observation, settings)
    return created


def _store_history(
    db: Session,
    result: SearchResult,
    settings: Settings,
    prefs: dict[str, Any],
    run: ProviderRun,
    target: SearchTarget,
) -> tuple[int, str]:
    """Store Google's price history for this search as dated observations.

    The history is the lowest price *for the search* (route, date, nonstop), not for a
    named flight. It is attributed to a flight only when exactly one nonstop flight
    number appears in the results (and it equals the expected one, if any).
    History points never trigger alerts: they describe the past.
    """
    numbers = {c.flight_number for c in result.candidates if c.stops == 0}
    if len(numbers) != 1:
        return 0, (
            f"Price history not imported: {len(numbers)} nonstop flights in results, so the daily "
            "lowest price cannot be attributed to a single flight."
        )
    fn = next(iter(numbers))
    if target.expected_flight_number and fn != target.expected_flight_number:
        return 0, f"Price history not imported: only nonstop flight is {fn}, expected {target.expected_flight_number}."
    c = next(c for c in result.candidates if c.flight_number == fn)
    flight = get_or_create_flight(
        db, origin=c.origin, destination=c.destination, flight_date=c.departure_local.date(),
        flight_number=fn, airline=c.airline, dep=c.departure_local.time(), arr=c.arrival_local.time(),
        schedule_status="provider_reported",
    )
    added = dup = 0
    for when, price in result.price_history:
        if when > run.started_at_utc:
            continue
        res = record_observation(
            db, flight=flight, price_total=price, currency=c.currency, source=Source.SERPAPI_HISTORY.value,
            verification=Verification.API_PRICE_HISTORY.value, display_currency=prefs["display_currency"],
            captured_at_utc=when, passengers=int(prefs["passengers"]),
            fare_product=settings.serpapi_assumed_fare_product,
            baggage_profile=settings.serpapi_assumed_baggage_profile,
            taxes_fees_included="yes", discount_club="public", profile_assumed=True,
            notes=(
                "Google Flights price history (via SerpApi): lowest nonstop price recorded for this search on "
                f"that day, attributed to {fn} as the only nonstop flight listed."
            ),
            provider_run_id=run.id, commit=False,
        )
        if res.duplicate:
            dup += 1
        else:
            added += 1
    db.commit()
    return added, f"Price history: {added} new day(s) imported for {fn}, {dup} already stored."


def _update_schedule_status(flight: FlightIdentity, c: LegCandidate) -> None:
    dep, arr = c.departure_local.time(), c.arrival_local.time()
    if flight.scheduled_departure_local in (None, dep) and flight.scheduled_arrival_local in (None, arr):
        flight.schedule_status = "matches_provider"
    else:
        flight.schedule_status = f"provider_shows_{dep.strftime('%H:%M')}-{arr.strftime('%H:%M')}"


def _log_skip(db: Session, target: SearchTarget, status: str, msg: str, trigger: str, now: datetime) -> dict:
    db.add(ProviderRun(
        provider=SerpApiGoogleFlightsProvider.name, trigger=trigger, started_at_utc=now, finished_at_utc=now,
        origin=target.origin, destination=target.destination, search_date=target.search_date,
        status=status, queries_used=0, message=msg,
    ))
    db.commit()
    return {"route": f"{target.origin}-{target.destination}", "date": target.search_date, "status": status,
            "message": msg}


def _search_target(
    db: Session,
    provider: SerpApiGoogleFlightsProvider,
    target: SearchTarget,
    settings: Settings,
    prefs: dict[str, Any],
    trigger: str,
    max_attempts: int,
    now: datetime,
) -> dict:
    run = ProviderRun(
        provider=provider.name, trigger=trigger, started_at_utc=now, origin=target.origin,
        destination=target.destination, search_date=target.search_date, status="running",
    )
    db.add(run)
    db.commit()
    try:
        result = provider.search_one_way(
            origin=target.origin, destination=target.destination, travel_date=target.search_date,
            currency=prefs["display_currency"], adults=int(prefs["passengers"]),
            expected_flight_number=target.expected_flight_number, max_attempts=max_attempts,
        )
    except Exception as exc:  # defensive: never crash the scheduler
        log.exception("Provider crashed")
        result = SearchResult(status="error", queries_used=1, message=f"Unexpected error: {type(exc).__name__}")
    created = 0
    history_msg = ""
    if result.status in ("success", "no_price", "not_found") and result.candidates:
        created = _store_candidates(db, result, settings, prefs, run, target)
    if result.status != "error" and result.price_history:
        n_hist, history_msg = _store_history(db, result, settings, prefs, run, target)
        created += n_hist
    run.status = result.status
    run.queries_used = result.queries_used
    run.http_status = result.http_status
    run.message = (result.message + (" | " + history_msg if history_msg else ""))
    run.observations_created = created
    run.finished_at_utc = utcnow()
    target.last_checked_utc = run.started_at_utc
    db.commit()
    log.info("Collector %s %s-%s %s: %s", trigger, target.origin, target.destination, target.search_date,
             result.status)
    return {"route": f"{target.origin}-{target.destination}", "date": target.search_date,
            "status": result.status, "message": run.message, "observations_created": created,
            "queries_used": result.queries_used}


def run_collection(
    db: Session,
    *,
    trigger: str,
    include_comparisons: bool | None = None,
    comparison_count: int = 1,
    provider: SerpApiGoogleFlightsProvider | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    provider = provider or SerpApiGoogleFlightsProvider(settings)
    prefs = runtime_settings.get_all(db)
    now = now or utcnow()
    tz = ZoneInfo(settings.app_timezone)
    today = now.astimezone(tz).date()
    results: list[dict] = []

    targets = [
        t for t in db.scalars(select(SearchTarget).where(SearchTarget.kind == "target", SearchTarget.active.is_(True)))
        if t.search_date >= today
    ]
    if not provider.configured:
        for t in targets:
            results.append(_log_skip(db, t, "skipped_unconfigured", "SERPAPI_API_KEY is not set", trigger, now))
        return {"ran": False, "reason": "Provider not configured", "results": results}

    daily_cap = int(prefs["max_queries_per_day"])
    min_minutes = int(prefs["min_minutes_between_checks"])

    for t in targets:
        b = budget(db, provider.name, daily_cap, now, settings)
        if checked_recently(t, min_minutes, now):
            results.append(_log_skip(db, t, "skipped_recent", f"Checked within the last {min_minutes} minutes", trigger, now))
        elif b.remaining < 1:
            results.append(_log_skip(db, t, "skipped_quota",
                                     f"Budget exhausted (today {b.used_today}/{b.daily_cap}, "
                                     f"month {b.used_this_month}/{b.monthly_quota})", trigger, now))
        else:
            results.append(_search_target(db, provider, t, settings, prefs, trigger, b.remaining, now))

    if include_comparisons is None:
        include_comparisons = bool(prefs["collector_include_comparisons"])
    if include_comparisons:
        b = budget(db, provider.name, daily_cap, now, settings)
        # Keep enough budget for the target checks still scheduled later today.
        reserve = 0
        if settings.collector_enabled:
            later_runs = _remaining_scheduled_runs_today(_parse_times(prefs["collector_times"]), now.astimezone(tz))
            reserve = len(targets) * later_runs
        spare = b.remaining - reserve
        if spare >= 1:
            ensure_comparison_targets(db, settings)
            for _ in range(max(1, min(comparison_count, spare))):
                b = budget(db, provider.name, daily_cap, now, settings)
                if b.remaining - reserve < 1:
                    break
                c = pick_comparison(db, today)
                if not c or checked_recently(c, min_minutes, now):
                    break
                results.append(_search_target(db, provider, c, settings, prefs, trigger, 1, now))
        else:
            results.append({"route": "comparison", "date": None, "status": "skipped_quota",
                            "message": f"No spare budget for comparison sampling (reserved {reserve} for later "
                                       "target checks today)"})
    return {"ran": True, "results": results}


def _parse_times(raw: str) -> list[tuple[int, int]]:
    out = []
    for part in str(raw).split(","):
        part = part.strip()
        if part:
            hh, mm = part.split(":")
            out.append((int(hh), int(mm)))
    return out
