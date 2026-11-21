"""SQLAlchemy ORM models.

Design rules encoded here:
* Every price observation belongs to exactly one flight identity (one leg).
* Outbound and return are separate flights; round-trip quotes live in their own table.
* Money is integer minor units + currency, plus original currency/FX provenance.
* Demo fixtures are flagged ``is_demo`` and never mixed with real data.
"""

from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow


class Direction(StrEnum):
    OUTBOUND = "outbound"  # SJJ -> FCO style (home -> destination)
    RETURN = "return"


class Source(StrEnum):
    MANUAL = "manual"
    SERPAPI = "serpapi_google_flights"
    SERPAPI_HISTORY = "serpapi_price_history"  # Google Flights price history via SerpApi
    CSV = "csv_import"
    DEMO = "demo_fixture"


class FareProduct(StrEnum):
    BASIC = "basic"
    WIZZ_GO = "wizz_go"
    WIZZ_PLUS = "wizz_plus"
    UNKNOWN = "unknown"


class BaggageProfile(StrEnum):
    UNDER_SEAT_ONLY = "under_seat_only"
    PRIORITY_TROLLEY = "priority_trolley"
    CHECKED_BAG = "checked_bag"
    UNKNOWN = "unknown"


class TriState(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class ClubStatus(StrEnum):
    PUBLIC = "public"  # generally available fare
    MEMBER = "member"  # Wizz Discount Club member fare
    UNKNOWN = "unknown"


class Verification(StrEnum):
    USER_VERIFIED = "user_verified"  # I saw this price myself
    API_REPORTED = "api_reported"  # returned by a provider, not re-checked
    API_PRICE_HISTORY = "api_price_history"  # provider's record of past daily lowest prices
    IMPORTED_UNVERIFIED = "imported_unverified"
    DEMO = "demo"  # fixture, not a real price


class FlightIdentity(Base):
    __tablename__ = "flights"
    __table_args__ = (
        UniqueConstraint("flight_number", "flight_date", "origin", "destination", name="uq_flight"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin: Mapped[str] = mapped_column(String(3), index=True)
    destination: Mapped[str] = mapped_column(String(3), index=True)
    origin_tz: Mapped[str] = mapped_column(String(64))
    destination_tz: Mapped[str] = mapped_column(String(64))
    flight_date: Mapped[date] = mapped_column(Date, index=True)  # local departure date
    flight_number: Mapped[str] = mapped_column(String(10), index=True)  # normalized e.g. W46160
    airline: Mapped[str] = mapped_column(String(80))
    scheduled_departure_local: Mapped[time | None] = mapped_column(Time, nullable=True)
    scheduled_arrival_local: Mapped[time | None] = mapped_column(Time, nullable=True)
    schedule_status: Mapped[str] = mapped_column(String(40), default="preliminary")
    direction: Mapped[str] = mapped_column(String(10))
    is_target: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    observations: Mapped[list[PriceObservation]] = relationship(back_populates="flight")


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id"), index=True)
    captured_at_utc: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    currency: Mapped[str] = mapped_column(String(3))
    price_total_minor: Mapped[int] = mapped_column(BigInteger)  # total for all passengers
    original_currency: Mapped[str] = mapped_column(String(3))
    original_price_minor: Mapped[int] = mapped_column(BigInteger)
    fx_rate: Mapped[str | None] = mapped_column(String(40), nullable=True)  # Decimal as text
    fx_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    passengers: Mapped[int] = mapped_column(Integer, default=1)
    fare_product: Mapped[str] = mapped_column(String(20), default=FareProduct.UNKNOWN)
    baggage_profile: Mapped[str] = mapped_column(String(30), default=BaggageProfile.UNKNOWN)
    taxes_fees_included: Mapped[str] = mapped_column(String(10), default=TriState.UNKNOWN)
    discount_club: Mapped[str] = mapped_column(String(10), default=ClubStatus.UNKNOWN)
    verification: Mapped[str] = mapped_column(String(30))
    profile_assumed: Mapped[bool] = mapped_column(Boolean, default=False)
    booking_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_run_id: Mapped[int | None] = mapped_column(ForeignKey("provider_runs.id"), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    flight: Mapped[FlightIdentity] = relationship(back_populates="observations")


class RoundTripQuote(Base):
    """A price quoted for both legs together (never computed by summing legs)."""

    __tablename__ = "round_trip_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outbound_flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id"))
    return_flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id"))
    captured_at_utc: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    currency: Mapped[str] = mapped_column(String(3))
    price_total_minor: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    passengers: Mapped[int] = mapped_column(Integer, default=1)
    fare_product: Mapped[str] = mapped_column(String(20), default=FareProduct.UNKNOWN)
    baggage_profile: Mapped[str] = mapped_column(String(30), default=BaggageProfile.UNKNOWN)
    taxes_fees_included: Mapped[str] = mapped_column(String(10), default=TriState.UNKNOWN)
    discount_club: Mapped[str] = mapped_column(String(10), default=ClubStatus.UNKNOWN)
    verification: Mapped[str] = mapped_column(String(30))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)


class SearchTarget(Base):
    """A route/date the collector may query (targets and comparison samples)."""

    __tablename__ = "search_targets"
    __table_args__ = (UniqueConstraint("origin", "destination", "search_date", name="uq_search"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    search_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(12))  # target | comparison
    expected_flight_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_utc: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class ProviderRun(Base):
    """Log of every provider query attempt (success, failure or skip)."""

    __tablename__ = "provider_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    trigger: Mapped[str] = mapped_column(String(20))  # scheduled | manual
    started_at_utc: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    finished_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    origin: Mapped[str | None] = mapped_column(String(3), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(3), nullable=True)
    search_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # success | not_found | no_price | error | skipped_quota | skipped_recent | skipped_unconfigured
    status: Mapped[str] = mapped_column(String(30))
    queries_used: Mapped[int] = mapped_column(Integer, default=0)
    observations_created: Mapped[int] = mapped_column(Integer, default=0)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id"))
    kind: Mapped[str] = mapped_column(String(20))  # threshold | pct_drop
    threshold_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pct_drop: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Decimal as text
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    baggage_profile: Mapped[str] = mapped_column(String(30), default=BaggageProfile.UNDER_SEAT_ONLY)
    discount_club: Mapped[str] = mapped_column(String(10), default=ClubStatus.PUBLIC)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    email: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    flight: Mapped[FlightIdentity] = relationship()


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id", ondelete="CASCADE"))
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id"))
    observation_id: Mapped[int] = mapped_column(ForeignKey("price_observations.id"))
    triggered_at_utc: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    message: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)
    email_status: Mapped[str] = mapped_column(String(30), default="not_requested")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    airline: Mapped[str] = mapped_column(String(80), default="Wizz Air")
    announced_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    booking_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    travel_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    travel_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    discount_description: Mapped[str] = mapped_column(String(200))
    excluded_dates: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_only: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AncillaryFee(Base):
    """Observed add-on prices (bags, Discount Club). Missing fee = unknown, never guessed."""

    __tablename__ = "ancillary_fees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flight_id: Mapped[int | None] = mapped_column(ForeignKey("flights.id"), nullable=True)
    # under_seat_bag | priority_trolley | checked_bag_10kg | checked_bag_20kg | checked_bag_32kg | discount_club_membership
    item: Mapped[str] = mapped_column(String(40))
    price_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    per: Mapped[str] = mapped_column(String(20), default="per_leg")  # per_leg | per_year | per_booking
    observed_at_utc: Mapped[datetime] = mapped_column(UTCDateTime)
    source: Mapped[str] = mapped_column(String(40), default=Source.MANUAL)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
