"""Flight identity helpers and the target itinerary seed."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Direction, FlightIdentity, SearchTarget

# Airport metadata needed to display local times correctly. Extend as needed.
AIRPORTS: dict[str, dict[str, str]] = {
    "SJJ": {"name": "Sarajevo International Airport", "city": "Sarajevo", "tz": "Europe/Sarajevo"},
    "FCO": {"name": "Rome Fiumicino", "city": "Rome", "tz": "Europe/Rome"},
    "CIA": {"name": "Rome Ciampino", "city": "Rome", "tz": "Europe/Rome"},
    "TZL": {"name": "Tuzla International Airport", "city": "Tuzla", "tz": "Europe/Sarajevo"},
    "BNX": {"name": "Banja Luka International Airport", "city": "Banja Luka", "tz": "Europe/Sarajevo"},
    "OMO": {"name": "Mostar Airport", "city": "Mostar", "tz": "Europe/Sarajevo"},
    "BEG": {"name": "Belgrade Nikola Tesla", "city": "Belgrade", "tz": "Europe/Belgrade"},
    "ZAG": {"name": "Zagreb Franjo Tuđman", "city": "Zagreb", "tz": "Europe/Zagreb"},
    "SPU": {"name": "Split Airport", "city": "Split", "tz": "Europe/Zagreb"},
    "DBV": {"name": "Dubrovnik Airport", "city": "Dubrovnik", "tz": "Europe/Zagreb"},
    "NAP": {"name": "Naples International", "city": "Naples", "tz": "Europe/Rome"},
    "MXP": {"name": "Milan Malpensa", "city": "Milan", "tz": "Europe/Rome"},
    "BGY": {"name": "Milan Bergamo", "city": "Milan", "tz": "Europe/Rome"},
    "VIE": {"name": "Vienna International", "city": "Vienna", "tz": "Europe/Vienna"},
    "BUD": {"name": "Budapest Ferenc Liszt", "city": "Budapest", "tz": "Europe/Budapest"},
}

AIRLINE_NAMES = {"W4": "Wizz Air Malta", "W6": "Wizz Air", "W9": "Wizz Air UK", "5W": "Wizz Air Abu Dhabi"}

_FN_RE = re.compile(r"^([A-Z0-9]{2})\s*-?\s*0*(\d{1,4})([A-Z]?)$")


def normalize_flight_number(raw: str) -> str:
    """'W4 6160' / 'w4-6160' / 'W406160' -> 'W46160'. Raises ValueError if malformed."""
    s = (raw or "").strip().upper()
    m = _FN_RE.match(s)
    if not m:
        raise ValueError(f"Unrecognised flight number: {raw!r}")
    return f"{m.group(1)}{m.group(2)}{m.group(3)}"


def airline_code(flight_number: str) -> str:
    return normalize_flight_number(flight_number)[:2]


def airport_tz(code: str) -> str:
    info = AIRPORTS.get(code.upper())
    if not info:
        raise ValueError(
            f"Unknown airport {code!r}; add it (with its IANA timezone) to AIRPORTS in backend/app/flights.py"
        )
    return info["tz"]


@dataclass(frozen=True)
class TargetLeg:
    origin: str
    destination: str
    flight_date: date
    flight_number: str
    airline: str
    dep: time
    arr: time
    direction: Direction
    label: str


TARGET_LEGS: tuple[TargetLeg, ...] = (
    TargetLeg("SJJ", "FCO", date(2026, 12, 31), "W46160", "Wizz Air Malta", time(21, 10), time(22, 35),
              Direction.OUTBOUND, "New Year outbound"),
    TargetLeg("FCO", "SJJ", date(2027, 1, 5), "W46159", "Wizz Air Malta", time(15, 5), time(16, 35),
              Direction.RETURN, "New Year return"),
)


def get_or_create_flight(
    db: Session,
    *,
    origin: str,
    destination: str,
    flight_date: date,
    flight_number: str,
    airline: str | None = None,
    dep: time | None = None,
    arr: time | None = None,
    direction: str | None = None,
    is_target: bool = False,
    label: str | None = None,
    schedule_status: str = "preliminary",
) -> FlightIdentity:
    origin, destination = origin.upper(), destination.upper()
    fn = normalize_flight_number(flight_number)
    existing = db.scalar(
        select(FlightIdentity).where(
            FlightIdentity.flight_number == fn,
            FlightIdentity.flight_date == flight_date,
            FlightIdentity.origin == origin,
            FlightIdentity.destination == destination,
        )
    )
    if existing:
        return existing
    if direction is None:
        direction = Direction.OUTBOUND if origin in {"SJJ", "TZL", "BNX", "OMO"} else Direction.RETURN
    f = FlightIdentity(
        origin=origin,
        destination=destination,
        origin_tz=airport_tz(origin),
        destination_tz=airport_tz(destination),
        flight_date=flight_date,
        flight_number=fn,
        airline=airline or AIRLINE_NAMES.get(fn[:2], fn[:2]),
        scheduled_departure_local=dep,
        scheduled_arrival_local=arr,
        direction=str(direction),
        is_target=is_target,
        label=label,
        schedule_status=schedule_status,
    )
    db.add(f)
    db.flush()
    return f


def seed_targets(db: Session) -> list[FlightIdentity]:
    out = []
    for leg in TARGET_LEGS:
        f = get_or_create_flight(
            db,
            origin=leg.origin,
            destination=leg.destination,
            flight_date=leg.flight_date,
            flight_number=leg.flight_number,
            airline=leg.airline,
            dep=leg.dep,
            arr=leg.arr,
            direction=leg.direction,
            is_target=True,
            label=leg.label,
        )
        out.append(f)
        st = db.scalar(
            select(SearchTarget).where(
                SearchTarget.origin == leg.origin,
                SearchTarget.destination == leg.destination,
                SearchTarget.search_date == leg.flight_date,
            )
        )
        if not st:
            db.add(
                SearchTarget(
                    origin=leg.origin,
                    destination=leg.destination,
                    search_date=leg.flight_date,
                    kind="target",
                    expected_flight_number=leg.flight_number,
                )
            )
    db.commit()
    return out


def target_flights(db: Session) -> list[FlightIdentity]:
    return list(
        db.scalars(
            select(FlightIdentity).where(FlightIdentity.is_target.is_(True)).order_by(FlightIdentity.flight_date)
        )
    )
