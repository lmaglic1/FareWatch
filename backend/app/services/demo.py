"""Demo fixtures: synthetic, clearly flagged data for exploring the UI.

Every row is ``is_demo=True``, ``source=demo_fixture``, ``verification=demo``.
Demo data is only displayed when demo mode is on (with a watermark), never
mixed into real analysis, never triggers alerts and cannot be exported as real.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..flights import get_or_create_flight, target_flights
from ..models import FlightIdentity, PriceObservation, RoundTripQuote, Source, Verification
from .observations import record_observation

DEMO_NOTE = "DEMO FIXTURE - synthetic value, not a real fare"


def _series(rng: random.Random, start: datetime, days: int, base: float) -> list[tuple[datetime, Decimal]]:
    out = []
    price = base
    for d in range(days):
        for hour in (7, 19):
            price = max(19.99, price + rng.uniform(-6, 7) + (0.35 if d > days * 0.6 else 0))
            ts = start + timedelta(days=d, hours=hour)
            out.append((ts, Decimal(f"{price:.2f}")))
    return out


def load_demo(db: Session, now: datetime | None = None) -> int:
    clear_demo(db)
    rng = random.Random(20261231)
    now = now or datetime.now(timezone.utc)
    start = (now - timedelta(days=21)).replace(hour=0, minute=0, second=0, microsecond=0)
    created = 0
    flights = target_flights(db)
    comp_specs = [
        ("SJJ", "FCO", date(2026, 12, 28), "W46160"),
        ("SJJ", "FCO", date(2026, 12, 3), "W46160"),
        ("FCO", "SJJ", date(2027, 1, 8), "W46159"),
        ("FCO", "SJJ", date(2026, 12, 10), "W46159"),
    ]
    for o, d, fd, fn in comp_specs:
        flights.append(get_or_create_flight(db, origin=o, destination=d, flight_date=fd, flight_number=fn,
                                            label="demo comparison"))
    for i, f in enumerate(flights):
        base = 55 + i * 9 + (25 if f.flight_date.month in (12, 1) and f.flight_date.day in range(20, 32) else 0)
        for ts, price in _series(rng, start, 21, base):
            if ts > now:
                continue
            r = record_observation(
                db, flight=f, price_total=price, currency="EUR", source=Source.DEMO.value,
                verification=Verification.DEMO.value, display_currency="EUR", captured_at_utc=ts,
                fare_product="basic", baggage_profile="under_seat_only", taxes_fees_included="yes",
                discount_club="public", notes=DEMO_NOTE, is_demo=True, commit=False,
            )
            created += 0 if r.duplicate else 1
    db.commit()
    return created


def clear_demo(db: Session) -> None:
    db.execute(delete(PriceObservation).where(PriceObservation.is_demo.is_(True)))
    db.execute(delete(RoundTripQuote).where(RoundTripQuote.is_demo.is_(True)))
    orphan = db.scalars(
        select(FlightIdentity).where(FlightIdentity.label == "demo comparison", FlightIdentity.is_target.is_(False))
    )
    for f in orphan:
        if not db.scalar(select(PriceObservation.id).where(PriceObservation.flight_id == f.id).limit(1)):
            db.delete(f)
    db.commit()
