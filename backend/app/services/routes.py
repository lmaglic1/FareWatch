"""Route search (any origin -> destination on a date) and saved trips."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import runtime_settings
from ..config import Settings, get_settings
from ..db import utcnow
from ..flights import airport_info
from ..models import FlightIdentity, PriceObservation, SearchTarget
from ..money import from_minor
from ..providers.serpapi_google_flights import SerpApiGoogleFlightsProvider
from .analysis import analyze_flight
from .collector import _log_skip, _search_target
from .observations import observations_for, to_out
from .quota import budget, checked_recently


class RouteError(ValueError):
    pass


def _validate(origin: str, destination: str, travel_date: date, settings: Settings, now: datetime) -> tuple[str, str]:
    o, d = origin.upper().strip(), destination.upper().strip()
    if o == d:
        raise RouteError("Origin and destination must differ")
    for code in (o, d):
        if not airport_info(code):
            raise RouteError(f"Unknown airport code {code}")
    today = now.astimezone(ZoneInfo(settings.app_timezone)).date()
    if travel_date < today:
        raise RouteError("The travel date is in the past")
    return o, d


def get_or_create_trip(db: Session, origin: str, destination: str, travel_date: date) -> SearchTarget:
    t = db.scalar(select(SearchTarget).where(
        SearchTarget.origin == origin, SearchTarget.destination == destination,
        SearchTarget.search_date == travel_date,
    ))
    if t is None:
        t = SearchTarget(origin=origin, destination=destination, search_date=travel_date, kind="user")
        db.add(t)
        db.commit()
    elif t.kind == "comparison":
        t.kind = "user"  # promote a sampled date to a saved trip
        t.active = True
        db.commit()
    return t


def search_route(
    db: Session,
    *,
    origin: str,
    destination: str,
    travel_date: date,
    provider: SerpApiGoogleFlightsProvider | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One SerpApi Google Flights search for a route/date (stores nonstop prices + price history)."""
    settings = settings or get_settings()
    provider = provider or SerpApiGoogleFlightsProvider(settings)
    now = now or utcnow()
    o, d = _validate(origin, destination, travel_date, settings, now)
    trip = get_or_create_trip(db, o, d, travel_date)
    prefs = runtime_settings.get_all(db)
    if not provider.configured:
        return _log_skip(db, trip, "skipped_unconfigured", "SERPAPI_API_KEY is not set", "search", now)
    min_minutes = int(prefs["min_minutes_between_checks"])
    if checked_recently(trip, min_minutes, now):
        return _log_skip(db, trip, "skipped_recent",
                         f"This route was checked in the last {min_minutes} minutes; showing saved prices.",
                         "search", now)
    b = budget(db, provider.name, int(prefs["max_queries_per_day"]), now, settings)
    if b.remaining < 1:
        return _log_skip(db, trip, "skipped_quota",
                         f"Search budget used up (today {b.used_today}/{b.daily_cap}, "
                         f"month {b.used_this_month}/{b.monthly_quota}).", "search", now)
    return _search_target(db, provider, trip, settings, prefs, "search", b.remaining, now)


def route_view(db: Session, origin: str, destination: str, travel_date: date) -> dict[str, Any]:
    prefs = runtime_settings.get_all(db)
    demo = bool(prefs["demo_mode"])
    o, d = origin.upper(), destination.upper()
    flights = list(db.scalars(select(FlightIdentity).where(
        FlightIdentity.origin == o, FlightIdentity.destination == d, FlightIdentity.flight_date == travel_date,
    ).order_by(FlightIdentity.scheduled_departure_local)))
    trip = db.scalar(select(SearchTarget).where(
        SearchTarget.origin == o, SearchTarget.destination == d, SearchTarget.search_date == travel_date,
    ))
    items = []
    for f in flights:
        obs = observations_for(db, flight_id=f.id, demo=demo)
        if not obs:
            continue
        items.append({
            "flight": f,
            "analysis": analyze_flight(db, f, prefs, demo=demo),
            "observations": [to_out(x) for x in obs],
        })
    items.sort(key=lambda i: (i["analysis"]["primary"] is None,
                              (i["analysis"]["primary"] or {}).get("stats", {}).get("latest") or 0))
    return {
        "demo": demo,
        "origin": airport_info(o),
        "destination": airport_info(d),
        "date": travel_date,
        "trip": None if trip is None else {"id": trip.id, "kind": trip.kind, "last_checked_utc": trip.last_checked_utc},
        "flights": items,
    }


def list_trips(db: Session) -> list[dict[str, Any]]:
    prefs = runtime_settings.get_all(db)
    demo = bool(prefs["demo_mode"])
    out = []
    trips = db.scalars(select(SearchTarget).where(
        SearchTarget.kind.in_(["target", "user"]), SearchTarget.active.is_(True)
    ).order_by(SearchTarget.search_date))
    for t in trips:
        latest = db.scalar(
            select(PriceObservation).join(FlightIdentity).where(
                FlightIdentity.origin == t.origin, FlightIdentity.destination == t.destination,
                FlightIdentity.flight_date == t.search_date, PriceObservation.is_demo.is_(demo),
                PriceObservation.currency == prefs["display_currency"],
                PriceObservation.discount_club == "public",
            ).order_by(PriceObservation.captured_at_utc.desc(), PriceObservation.price_total_minor).limit(1)
        )
        out.append({
            "id": t.id, "kind": t.kind, "origin": airport_info(t.origin), "destination": airport_info(t.destination),
            "date": t.search_date, "last_checked_utc": t.last_checked_utc,
            "latest_price": from_minor(latest.price_total_minor) if latest else None,
            "latest_currency": latest.currency if latest else None,
            "latest_flight_number": latest.flight.flight_number if latest else None,
        })
    return out
