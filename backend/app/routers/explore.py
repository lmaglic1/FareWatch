from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..flights import search_airports
from ..models import ExploreDestination, SearchTarget
from ..schemas import FlightOut
from ..services import explore as explore_svc
from ..services.routes import RouteError, list_trips, route_view, search_route
from .common import booking_links, prefs

router = APIRouter(prefix="/api", tags=["explore"])

TripType = Literal["one_way", "round_trip"]


@router.get("/airports")
def airports(q: str = Query(min_length=2, max_length=60), db: Session = Depends(get_db)):
    # Destinations that appeared in Explore results are reachable from home: rank them first.
    known = set(db.scalars(select(ExploreDestination.airport_code).distinct()))
    return search_airports(q, boost=known)


def _origin(origin: str | None) -> str:
    return (origin or get_settings().home_airport).upper()


@router.get("/explore")
def explore(
    origin: str | None = None,
    trip_type: TripType = "one_way",
    month: int = Query(default=0, ge=0, le=12),
    duration: int = Query(default=2, ge=1, le=3),
    db: Session = Depends(get_db),
):
    o = _origin(origin)
    snap = explore_svc.latest_snapshot(db, o, trip_type, month, duration)
    return {"origin": o, **explore_svc.snapshot_view(snap)}


@router.post("/explore/refresh")
def explore_refresh(
    origin: str | None = None,
    trip_type: TripType = "one_way",
    month: int = Query(default=0, ge=0, le=12),
    duration: int = Query(default=2, ge=1, le=3),
    db: Session = Depends(get_db),
):
    o = _origin(origin)
    return {"origin": o, **explore_svc.refresh(db, origin=o, trip_type=trip_type, month=month, duration=duration)}


class RouteSearchIn(BaseModel):
    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)
    date: date


@router.post("/route/search")
def route_search(body: RouteSearchIn, db: Session = Depends(get_db)):
    try:
        return search_route(db, origin=body.origin, destination=body.destination, travel_date=body.date)
    except RouteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/route")
def route(origin: str, destination: str, date: date, db: Session = Depends(get_db)):
    view = route_view(db, origin, destination, date)
    p = prefs(db)
    for item in view["flights"]:
        item["flight"] = FlightOut.model_validate(item["flight"])
    view["booking_links"] = booking_links(origin.upper(), destination.upper(), date, int(p["passengers"]))
    return view


@router.get("/trips")
def trips(db: Session = Depends(get_db)):
    return list_trips(db)


@router.delete("/trips/{trip_id}")
def remove_trip(trip_id: int, db: Session = Depends(get_db)):
    t = db.get(SearchTarget, trip_id)
    if not t or t.kind not in ("user", "target"):
        raise HTTPException(status_code=404, detail="Trip not found")
    t.active = False  # observations are kept
    db.commit()
    return {"ok": True}
