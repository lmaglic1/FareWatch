from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..flights import get_or_create_flight
from ..models import FlightIdentity, PriceObservation
from ..schemas import FlightCreate, FlightOut
from ..services.analysis import analyze_flight
from ..services.observations import observations_for, to_out
from .common import booking_links, demo_mode, get_flight_or_404, prefs

router = APIRouter(prefix="/api/flights", tags=["flights"])


@router.get("", response_model=list[FlightOut])
def list_flights(with_data_only: bool = False, db: Session = Depends(get_db)):
    flights = list(db.scalars(select(FlightIdentity).order_by(FlightIdentity.flight_date, FlightIdentity.origin)))
    demo = demo_mode(db)
    with_data = set(db.scalars(select(PriceObservation.flight_id).where(PriceObservation.is_demo.is_(demo))))
    if with_data_only:
        return [f for f in flights if f.id in with_data or f.is_target]
    # Hide demo-only comparison flights outside demo mode.
    return [f for f in flights if demo or f.label != "demo comparison"]


@router.post("", response_model=FlightOut, status_code=201)
def create_flight(body: FlightCreate, db: Session = Depends(get_db)):
    try:
        f = get_or_create_flight(
            db, origin=body.origin, destination=body.destination, flight_date=body.flight_date,
            flight_number=body.flight_number, airline=body.airline, dep=body.scheduled_departure_local,
            arr=body.scheduled_arrival_local,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return f


@router.get("/{flight_id}")
def flight_detail(flight_id: int, db: Session = Depends(get_db)):
    f = get_flight_or_404(db, flight_id)
    p = prefs(db)
    demo = bool(p["demo_mode"])
    return {
        "demo": demo,
        "flight": FlightOut.model_validate(f),
        "analysis": analyze_flight(db, f, p, demo=demo),
        "observations": [to_out(o) for o in observations_for(db, flight_id=f.id, demo=demo)],
        "booking_links": booking_links(f.origin, f.destination, f.flight_date, int(p["passengers"])),
    }
