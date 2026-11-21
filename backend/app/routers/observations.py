from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import FlightIdentity, PriceObservation, RoundTripQuote, Source, Verification
from ..money import MoneyError, from_minor
from ..providers.csv_import import CSVImportProvider, export_csv
from ..providers.manual import ManualEntryProvider
from ..schemas import ManualObservationIn, ObservationCreated, RoundTripQuoteIn
from ..services.alerts import evaluate_alerts
from ..services.observations import record_round_trip, to_out
from .common import demo_mode, get_flight_or_404, prefs

router = APIRouter(prefix="/api", tags=["observations"])

MAX_UPLOAD_BYTES = 2_000_000


def _query(
    db: Session, demo: bool, flight_id: int | None, source: str | None, origin: str | None,
    destination: str | None, flight_date_from: date | None, flight_date_to: date | None,
):
    stmt = select(PriceObservation).join(FlightIdentity).where(PriceObservation.is_demo.is_(demo))
    if flight_id:
        stmt = stmt.where(PriceObservation.flight_id == flight_id)
    if source:
        stmt = stmt.where(PriceObservation.source == source)
    if origin:
        stmt = stmt.where(FlightIdentity.origin == origin.upper())
    if destination:
        stmt = stmt.where(FlightIdentity.destination == destination.upper())
    if flight_date_from:
        stmt = stmt.where(FlightIdentity.flight_date >= flight_date_from)
    if flight_date_to:
        stmt = stmt.where(FlightIdentity.flight_date <= flight_date_to)
    return stmt


SORTS = {
    "captured_at": PriceObservation.captured_at_utc,
    "price": PriceObservation.price_total_minor,
    "flight_date": FlightIdentity.flight_date,
}


@router.get("/observations")
def list_observations(
    flight_id: int | None = None,
    source: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    flight_date_from: date | None = None,
    flight_date_to: date | None = None,
    sort: Literal["captured_at", "price", "flight_date"] = "captured_at",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    demo = demo_mode(db)
    stmt = _query(db, demo, flight_id, source, origin, destination, flight_date_from, flight_date_to)
    col = SORTS[sort]
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc(), PriceObservation.id.desc()).limit(limit)
    return {"demo": demo, "items": [to_out(o) for o in db.scalars(stmt)]}


@router.post("/observations", response_model=ObservationCreated, status_code=201)
def create_manual_observation(body: ManualObservationIn, db: Session = Depends(get_db)):
    p = prefs(db)
    try:
        res = ManualEntryProvider().record(db, body, p["display_currency"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, MoneyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if res.duplicate or res.observation is None:
        return ObservationCreated(observation=None, duplicate=True,
                                  message="Identical observation already recorded; nothing added.")
    alerts = evaluate_alerts(db, res.observation)
    return ObservationCreated(observation=to_out(res.observation), duplicate=False,
                              alerts_triggered=len(alerts), message="Observation saved.")


@router.delete("/observations/{obs_id}", status_code=204)
def delete_observation(obs_id: int, db: Session = Depends(get_db)):
    o = db.get(PriceObservation, obs_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Observation not found")
    from ..models import AlertEvent

    for ev in db.scalars(select(AlertEvent).where(AlertEvent.observation_id == obs_id)):
        db.delete(ev)
    db.delete(o)
    db.commit()
    return Response(status_code=204)


@router.get("/observations/export.csv")
def export_observations(db: Session = Depends(get_db)):
    # Export only real observations; demo fixtures are never exported.
    obs = list(db.scalars(select(PriceObservation).where(PriceObservation.is_demo.is_(False))
                          .order_by(PriceObservation.captured_at_utc)))
    return Response(
        content=export_csv(obs), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="farewatch_observations.csv"'},
    )


@router.post("/observations/import")
async def import_observations(
    file: UploadFile = File(...), dry_run: bool = False, db: Session = Depends(get_db)
):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV larger than 2 MB")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded") from exc
    report = CSVImportProvider().import_csv(db, text, prefs(db)["display_currency"], dry_run=dry_run)
    return report.__dict__


# --- Round-trip quotes (stored separately; never computed from legs) -------

def _rt_out(q: RoundTripQuote) -> dict:
    return {
        "id": q.id, "outbound_flight_id": q.outbound_flight_id, "return_flight_id": q.return_flight_id,
        "captured_at_utc": q.captured_at_utc, "currency": q.currency,
        "price_total": from_minor(q.price_total_minor), "source": q.source, "source_url": q.source_url,
        "passengers": q.passengers, "fare_product": q.fare_product, "baggage_profile": q.baggage_profile,
        "taxes_fees_included": q.taxes_fees_included, "discount_club": q.discount_club,
        "verification": q.verification, "is_demo": q.is_demo, "notes": q.notes,
    }


@router.get("/round-trips")
def list_round_trips(db: Session = Depends(get_db)):
    demo = demo_mode(db)
    rows = db.scalars(select(RoundTripQuote).where(RoundTripQuote.is_demo.is_(demo))
                      .order_by(RoundTripQuote.captured_at_utc.desc()))
    return {"demo": demo, "items": [_rt_out(q) for q in rows]}


@router.post("/round-trips", status_code=201)
def create_round_trip(body: RoundTripQuoteIn, db: Session = Depends(get_db)):
    out_f = get_flight_or_404(db, body.outbound_flight_id)
    ret_f = get_flight_or_404(db, body.return_flight_id)
    if out_f.origin != ret_f.destination or out_f.destination != ret_f.origin:
        raise HTTPException(status_code=422, detail="Return flight must reverse the outbound route")
    if ret_f.flight_date < out_f.flight_date:
        raise HTTPException(status_code=422, detail="Return date is before outbound date")
    try:
        res = record_round_trip(
            db, outbound=out_f, inbound=ret_f, price_total=body.price_total, currency=body.currency,
            source=Source.MANUAL.value, verification=Verification.USER_VERIFIED.value,
            captured_at_utc=body.captured_at_utc, passengers=body.passengers, fare_product=body.fare_product,
            baggage_profile=body.baggage_profile, taxes_fees_included=body.taxes_fees_included,
            discount_club=body.discount_club, source_url=str(body.source_url) if body.source_url else None,
            notes=body.notes,
        )
    except (ValueError, MoneyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if res.duplicate:
        return {"duplicate": True, "item": None}
    return {"duplicate": False, "item": _rt_out(res.observation)}  # type: ignore[arg-type]
