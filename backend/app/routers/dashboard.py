from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, utcnow
from ..flights import target_flights
from ..models import PriceObservation, ProviderRun, RoundTripQuote
from ..money import from_minor
from ..schemas import FlightOut
from ..services.analysis import analyze_flight, combine_legs, cross_flight_analysis
from ..services import forecast
from ..services.observations import ProfileKey, to_out
from .common import PRICE_DISCLAIMER, booking_links, prefs

router = APIRouter(prefix="/api", tags=["dashboard"])


def last_success(db: Session) -> ProviderRun | None:
    return db.scalar(
        select(ProviderRun).where(ProviderRun.status == "success")
        .order_by(ProviderRun.started_at_utc.desc()).limit(1)
    )


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    p = prefs(db)
    demo = bool(p["demo_mode"])
    s = get_settings()
    now = utcnow()
    legs = []
    for f in target_flights(db):
        a = analyze_flight(db, f, p, demo=demo, now=now)
        primary = a["primary"]
        latest_obs = best_obs = None
        if primary:
            key = ProfileKey(**primary["profile"])
            comparable = [
                o for o in db.scalars(
                    select(PriceObservation).where(PriceObservation.flight_id == f.id,
                                                   PriceObservation.is_demo.is_(demo))
                    .order_by(PriceObservation.captured_at_utc)
                ) if ProfileKey.of(o) == key
            ]
            if comparable:
                latest_obs = to_out(comparable[-1])
                best_obs = to_out(min(comparable, key=lambda o: (o.price_total_minor, o.captured_at_utc)))
        last = a["last_valid_quote_at"]
        legs.append({
            "flight": FlightOut.model_validate(f),
            "analysis": a,
            "latest_observation": latest_obs,
            "best_observation": best_obs,
            "freshness_hours": round((now - last).total_seconds() / 3600, 1) if last else None,
            "booking_links": booking_links(f.origin, f.destination, f.flight_date, int(p["passengers"])),
        })
    combined = combine_legs(
        legs[0]["analysis"]["primary"] if legs else None,
        legs[1]["analysis"]["primary"] if len(legs) > 1 else None,
    )
    rt = db.scalar(select(RoundTripQuote).where(RoundTripQuote.is_demo.is_(demo))
                   .order_by(RoundTripQuote.captured_at_utc.desc()).limit(1))
    ls = last_success(db)
    return {
        "demo": demo,
        "generated_at_utc": now,
        "preferences": p,
        "provider": {
            "serpapi_configured": s.serpapi_configured,
            "collector_enabled": s.collector_enabled,
            "last_successful_fetch_utc": ls.started_at_utc if ls else None,
        },
        "legs": legs,
        "combined_legs": combined,
        "latest_round_trip_quote": None if rt is None else {
            "price_total": from_minor(rt.price_total_minor), "currency": rt.currency,
            "captured_at_utc": rt.captured_at_utc, "source": rt.source, "baggage_profile": rt.baggage_profile,
            "discount_club": rt.discount_club, "verification": rt.verification,
        },
        "disclaimer": PRICE_DISCLAIMER,
    }


@router.get("/compare")
def compare(origin: str | None = None, destination: str | None = None, db: Session = Depends(get_db)):
    p = prefs(db)
    demo = bool(p["demo_mode"])
    return {"demo": demo, **cross_flight_analysis(db, p, demo=demo, origin=origin, destination=destination)}


@router.get("/forecast")
def forecast_eval(db: Session = Depends(get_db)):
    return forecast.evaluate(db)
