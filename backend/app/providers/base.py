"""Provider abstraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass
class LegCandidate:
    """One nonstop flight option parsed from a provider response."""

    flight_number: str  # normalized, e.g. W46160
    airline: str
    origin: str
    destination: str
    departure_local: datetime  # naive local time at origin airport
    arrival_local: datetime  # naive local time at destination airport
    price: Decimal | None
    currency: str
    stops: int
    raw_flight_number: str = ""


@dataclass
class SearchResult:
    """Outcome of one provider search for one route + date."""

    # success | not_found | no_price | error
    status: str
    queries_used: int
    candidates: list[LegCandidate] = field(default_factory=list)
    matched: LegCandidate | None = None
    http_status: int | None = None
    message: str = ""
    # Google Flights "price history for this search": (UTC timestamp, lowest price) pairs
    price_history: list[tuple[datetime, Decimal]] = field(default_factory=list)


class FareSearchProvider(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    def search_one_way(
        self,
        *,
        origin: str,
        destination: str,
        travel_date: date,
        currency: str,
        adults: int,
        expected_flight_number: str | None,
    ) -> SearchResult: ...
