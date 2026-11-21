"""Pydantic request/response schemas. Money is ``Decimal`` (serialized as a string)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from .flights import normalize_flight_number
from .models import BaggageProfile, ClubStatus, FareProduct, TriState

FareProductT = Literal["basic", "wizz_go", "wizz_plus", "unknown"]
BaggageT = Literal["under_seat_only", "priority_trolley", "checked_bag", "unknown"]
TriT = Literal["yes", "no", "unknown"]
ClubT = Literal["public", "member", "unknown"]

MAX_PRICE = Decimal("20000")


class FlightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origin: str
    destination: str
    origin_tz: str
    destination_tz: str
    flight_date: date
    flight_number: str
    airline: str
    scheduled_departure_local: time | None
    scheduled_arrival_local: time | None
    schedule_status: str
    direction: str
    is_target: bool
    label: str | None


class FlightCreate(BaseModel):
    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)
    flight_date: date
    flight_number: str
    airline: str | None = None
    scheduled_departure_local: time | None = None
    scheduled_arrival_local: time | None = None

    @field_validator("origin", "destination")
    @classmethod
    def _iata(cls, v: str) -> str:
        v = v.upper()
        if not v.isalpha():
            raise ValueError("Airport must be a 3-letter IATA code")
        return v

    @field_validator("flight_number")
    @classmethod
    def _fn(cls, v: str) -> str:
        return normalize_flight_number(v)

    @model_validator(mode="after")
    def _distinct(self) -> FlightCreate:
        if self.origin == self.destination:
            raise ValueError("Origin and destination must differ")
        return self


class FareProfile(BaseModel):
    fare_product: FareProductT = FareProduct.UNKNOWN.value
    baggage_profile: BaggageT = BaggageProfile.UNKNOWN.value
    taxes_fees_included: TriT = TriState.UNKNOWN.value
    discount_club: ClubT = ClubStatus.UNKNOWN.value


class ManualObservationIn(FareProfile):
    """A fare I personally saw on a booking/search page."""

    flight_id: int
    price_total: Decimal = Field(gt=0, description="Total price for all passengers")
    currency: str = Field(min_length=3, max_length=3)
    captured_at_utc: datetime | None = None  # default: now
    passengers: int = Field(default=1, ge=1, le=9)
    source_url: HttpUrl | None = None
    booking_url: HttpUrl | None = None
    fx_rate_to_display: Decimal | None = Field(default=None, gt=0)
    fx_source: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("price_total")
    @classmethod
    def _bounded(cls, v: Decimal) -> Decimal:
        if v > MAX_PRICE:
            raise ValueError(f"Price above {MAX_PRICE} looks like a typo")
        if v.as_tuple().exponent < -2:  # type: ignore[operator]
            raise ValueError("At most 2 decimal places")
        return v

    @field_validator("currency")
    @classmethod
    def _cur(cls, v: str) -> str:
        return v.upper()

    @field_validator("captured_at_utc")
    @classmethod
    def _not_future(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("captured_at_utc must include a timezone (e.g. 2026-11-21T18:00:00Z)")
        if v > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("captured_at_utc cannot be in the future")
        return v


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    flight_id: int
    captured_at_utc: datetime
    currency: str
    price_total: Decimal
    original_currency: str
    original_price: Decimal
    fx_rate: str | None
    fx_source: str | None
    source: str
    source_url: str | None
    passengers: int
    fare_product: str
    baggage_profile: str
    taxes_fees_included: str
    discount_club: str
    verification: str
    profile_assumed: bool
    booking_url: str | None
    is_demo: bool
    notes: str | None
    flight_number: str
    origin: str
    destination: str
    flight_date: date
    lead_time_days: int


class ObservationCreated(BaseModel):
    observation: ObservationOut | None
    duplicate: bool
    alerts_triggered: int = 0
    message: str


class RoundTripQuoteIn(FareProfile):
    outbound_flight_id: int
    return_flight_id: int
    price_total: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    captured_at_utc: datetime | None = None
    passengers: int = Field(default=1, ge=1, le=9)
    source_url: HttpUrl | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("currency")
    @classmethod
    def _cur(cls, v: str) -> str:
        return v.upper()


class AlertRuleIn(BaseModel):
    flight_id: int
    kind: Literal["threshold", "pct_drop"]
    threshold: Decimal | None = Field(default=None, gt=0)
    pct_drop: Decimal | None = Field(default=None, gt=0, le=90)
    currency: str = "EUR"
    baggage_profile: BaggageT = "under_seat_only"
    discount_club: ClubT = "public"
    email: bool = False

    @model_validator(mode="after")
    def _check(self) -> AlertRuleIn:
        if self.kind == "threshold" and self.threshold is None:
            raise ValueError("threshold is required for a threshold alert")
        if self.kind == "pct_drop" and self.pct_drop is None:
            raise ValueError("pct_drop is required for a percentage-drop alert")
        self.currency = self.currency.upper()
        return self


class PromotionIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    airline: str = "Wizz Air"
    announced_date: date | None = None
    booking_deadline: date | None = None
    travel_start: date | None = None
    travel_end: date | None = None
    discount_description: str = Field(min_length=1, max_length=200)
    excluded_dates: str | None = Field(default=None, max_length=2000)
    member_only: bool = False
    source_url: HttpUrl | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _dates(self) -> PromotionIn:
        if self.travel_start and self.travel_end and self.travel_end < self.travel_start:
            raise ValueError("travel_end must be on/after travel_start")
        return self


class AncillaryFeeIn(BaseModel):
    flight_id: int | None = None
    item: Literal[
        "under_seat_bag",
        "priority_trolley",
        "checked_bag_10kg",
        "checked_bag_20kg",
        "checked_bag_32kg",
        "discount_club_membership",
    ]
    price: Decimal = Field(ge=0, le=Decimal("2000"))
    currency: str = Field(min_length=3, max_length=3)
    per: Literal["per_leg", "per_year", "per_booking"] = "per_leg"
    observed_at_utc: datetime | None = None
    source_url: HttpUrl | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("currency")
    @classmethod
    def _cur(cls, v: str) -> str:
        return v.upper()
