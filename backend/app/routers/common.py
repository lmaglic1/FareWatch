"""Shared router helpers."""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import quote_plus

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import runtime_settings
from ..models import FlightIdentity


def prefs(db: Session) -> dict[str, Any]:
    return runtime_settings.get_all(db)


def demo_mode(db: Session) -> bool:
    return bool(runtime_settings.get(db, "demo_mode"))


def get_flight_or_404(db: Session, flight_id: int) -> FlightIdentity:
    f = db.get(FlightIdentity, flight_id)
    if f is None:
        raise HTTPException(status_code=404, detail=f"Flight {flight_id} not found")
    return f


def booking_links(origin: str, destination: str, d: date, passengers: int = 1) -> list[dict[str, str]]:
    """Official *search* pages only. No deep links to specific offers are fabricated."""
    q = f"Flights from {origin} to {destination} on {d.isoformat()} one way nonstop {passengers} adult"
    return [
        {
            "label": "Wizz Air (official site)",
            "url": "https://wizzair.com/",
            "note": "Opens the official Wizz Air homepage; enter route and date there.",
        },
        {
            "label": "Google Flights search",
            "url": f"https://www.google.com/travel/flights?q={quote_plus(q)}",
            "note": "Opens a Google Flights search for this route/date. Results may differ from FareWatch.",
        },
    ]


PRICE_DISCLAIMER = (
    "Displayed fares are past observations and may have changed. Verify the final price on the airline's "
    "official site, including baggage and fees, before buying. FareWatch never books or pays automatically."
)
