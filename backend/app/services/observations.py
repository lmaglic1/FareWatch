"""Persisting and querying price observations (with duplicate protection)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import FlightIdentity, PriceObservation, RoundTripQuote
from ..money import convert, from_minor, normalize_currency, to_minor
from ..schemas import ObservationOut
from .features import lead_time_days


@dataclass(frozen=True)
class ProfileKey:
    """Two observations are comparable only if all of these match."""

    currency: str
    passengers: int
    fare_product: str
    baggage_profile: str
    taxes_fees_included: str
    discount_club: str

    @classmethod
    def of(cls, o: PriceObservation | RoundTripQuote) -> ProfileKey:
        return cls(
            o.currency, o.passengers, o.fare_product, o.baggage_profile,
            o.taxes_fees_included, o.discount_club,
        )

    def label(self) -> str:
        club = {"member": "Discount Club member fare", "public": "public fare"}.get(
            self.discount_club, "club status unknown"
        )
        return (
            f"{self.currency}, {self.passengers} pax, {self.fare_product}, "
            f"{self.baggage_profile.replace('_', ' ')}, taxes incl.: {self.taxes_fees_included}, {club}"
        )


def _dedupe_key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


@dataclass
class RecordResult:
    observation: PriceObservation | None
    duplicate: bool


def record_observation(
    db: Session,
    *,
    flight: FlightIdentity,
    price_total: Decimal,
    currency: str,
    source: str,
    verification: str,
    display_currency: str,
    captured_at_utc: datetime | None = None,
    passengers: int = 1,
    fare_product: str = "unknown",
    baggage_profile: str = "unknown",
    taxes_fees_included: str = "unknown",
    discount_club: str = "unknown",
    profile_assumed: bool = False,
    source_url: str | None = None,
    booking_url: str | None = None,
    fx_rate: Decimal | None = None,
    fx_source: str | None = None,
    notes: str | None = None,
    is_demo: bool = False,
    provider_run_id: int | None = None,
    commit: bool = True,
) -> RecordResult:
    """Store one leg observation. Converts to ``display_currency`` only with a known/provided rate."""
    captured = captured_at_utc or utcnow()
    orig_cur = normalize_currency(currency)
    disp_cur = normalize_currency(display_currency)
    orig_minor = to_minor(price_total)
    if orig_minor <= 0:
        raise ValueError("Price must be positive")

    if orig_cur == disp_cur:
        stored_cur, stored_minor, rate_txt, rate_src = orig_cur, orig_minor, None, None
    else:
        converted, rate, provenance = convert(price_total, orig_cur, disp_cur, fx_rate, fx_source)
        stored_cur, stored_minor = disp_cur, to_minor(converted)
        rate_txt, rate_src = str(rate), provenance

    key = _dedupe_key(
        flight.id, captured.replace(second=0, microsecond=0).isoformat(), orig_minor, orig_cur,
        source, passengers, fare_product, baggage_profile, taxes_fees_included, discount_club, is_demo,
    )
    if db.scalar(select(PriceObservation.id).where(PriceObservation.dedupe_key == key)):
        return RecordResult(None, True)

    obs = PriceObservation(
        flight_id=flight.id,
        captured_at_utc=captured,
        currency=stored_cur,
        price_total_minor=stored_minor,
        original_currency=orig_cur,
        original_price_minor=orig_minor,
        fx_rate=rate_txt,
        fx_source=rate_src,
        source=source,
        source_url=source_url,
        passengers=passengers,
        fare_product=fare_product,
        baggage_profile=baggage_profile,
        taxes_fees_included=taxes_fees_included,
        discount_club=discount_club,
        verification=verification,
        profile_assumed=profile_assumed,
        booking_url=booking_url,
        is_demo=is_demo,
        notes=notes,
        provider_run_id=provider_run_id,
        dedupe_key=key,
    )
    db.add(obs)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return RecordResult(None, True)
    if commit:
        db.commit()
    return RecordResult(obs, False)


def record_round_trip(
    db: Session,
    *,
    outbound: FlightIdentity,
    inbound: FlightIdentity,
    price_total: Decimal,
    currency: str,
    source: str,
    verification: str,
    captured_at_utc: datetime | None = None,
    passengers: int = 1,
    fare_product: str = "unknown",
    baggage_profile: str = "unknown",
    taxes_fees_included: str = "unknown",
    discount_club: str = "unknown",
    source_url: str | None = None,
    notes: str | None = None,
    is_demo: bool = False,
) -> RecordResult:
    captured = captured_at_utc or utcnow()
    cur = normalize_currency(currency)
    minor = to_minor(price_total)
    key = _dedupe_key(
        "rt", outbound.id, inbound.id, captured.replace(second=0, microsecond=0).isoformat(), minor, cur,
        source, passengers, fare_product, baggage_profile, taxes_fees_included, discount_club, is_demo,
    )
    if db.scalar(select(RoundTripQuote.id).where(RoundTripQuote.dedupe_key == key)):
        return RecordResult(None, True)
    q = RoundTripQuote(
        outbound_flight_id=outbound.id, return_flight_id=inbound.id, captured_at_utc=captured,
        currency=cur, price_total_minor=minor, source=source, source_url=source_url,
        passengers=passengers, fare_product=fare_product, baggage_profile=baggage_profile,
        taxes_fees_included=taxes_fees_included, discount_club=discount_club,
        verification=verification, is_demo=is_demo, notes=notes, dedupe_key=key,
    )
    db.add(q)
    db.commit()
    return RecordResult(q, False)  # type: ignore[arg-type]


def observations_for(
    db: Session, *, flight_id: int | None = None, demo: bool = False
) -> list[PriceObservation]:
    stmt = select(PriceObservation).where(PriceObservation.is_demo.is_(demo))
    if flight_id is not None:
        stmt = stmt.where(PriceObservation.flight_id == flight_id)
    return list(db.scalars(stmt.order_by(PriceObservation.captured_at_utc, PriceObservation.id)))


def to_out(o: PriceObservation) -> ObservationOut:
    f = o.flight
    return ObservationOut(
        id=o.id, flight_id=o.flight_id, captured_at_utc=o.captured_at_utc, currency=o.currency,
        price_total=from_minor(o.price_total_minor), original_currency=o.original_currency,
        original_price=from_minor(o.original_price_minor), fx_rate=o.fx_rate, fx_source=o.fx_source,
        source=o.source, source_url=o.source_url, passengers=o.passengers, fare_product=o.fare_product,
        baggage_profile=o.baggage_profile, taxes_fees_included=o.taxes_fees_included,
        discount_club=o.discount_club, verification=o.verification, profile_assumed=o.profile_assumed,
        booking_url=o.booking_url, is_demo=o.is_demo, notes=o.notes, flight_number=f.flight_number,
        origin=f.origin, destination=f.destination, flight_date=f.flight_date,
        lead_time_days=lead_time_days(f.flight_date, o.captured_at_utc, f.origin_tz),
    )
