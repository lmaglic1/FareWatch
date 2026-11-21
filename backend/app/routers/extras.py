"""Promotions log, ancillary fees (baggage, Discount Club) and fare-bundle comparison."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, utcnow
from ..flights import target_flights
from ..models import AncillaryFee, PriceObservation, Promotion
from ..money import from_minor, normalize_currency, quantize, to_minor
from ..schemas import AncillaryFeeIn, PromotionIn
from .common import demo_mode, prefs

router = APIRouter(prefix="/api", tags=["extras"])


def _promo_out(p: Promotion) -> dict:
    return {c.name: getattr(p, c.name) for c in Promotion.__table__.columns}


@router.get("/promotions")
def list_promotions(db: Session = Depends(get_db)):
    return [_promo_out(p) for p in db.scalars(select(Promotion).order_by(Promotion.created_at.desc()))]


@router.post("/promotions", status_code=201)
def create_promotion(body: PromotionIn, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["source_url"] = str(body.source_url) if body.source_url else None
    p = Promotion(**data)
    db.add(p)
    db.commit()
    return _promo_out(p)


@router.delete("/promotions/{promo_id}", status_code=204)
def delete_promotion(promo_id: int, db: Session = Depends(get_db)):
    p = db.get(Promotion, promo_id)
    if not p:
        raise HTTPException(status_code=404, detail="Promotion not found")
    db.delete(p)
    db.commit()
    return Response(status_code=204)


def _fee_out(f: AncillaryFee) -> dict:
    return {
        "id": f.id, "flight_id": f.flight_id, "item": f.item, "price": from_minor(f.price_minor),
        "currency": f.currency, "per": f.per, "observed_at_utc": f.observed_at_utc, "source": f.source,
        "source_url": f.source_url, "notes": f.notes,
    }


@router.get("/fees")
def list_fees(db: Session = Depends(get_db)):
    return [_fee_out(f) for f in db.scalars(select(AncillaryFee).order_by(AncillaryFee.observed_at_utc.desc()))]


@router.post("/fees", status_code=201)
def create_fee(body: AncillaryFeeIn, db: Session = Depends(get_db)):
    try:
        cur = normalize_currency(body.currency)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    f = AncillaryFee(
        flight_id=body.flight_id, item=body.item, price_minor=to_minor(body.price), currency=cur, per=body.per,
        observed_at_utc=body.observed_at_utc or utcnow(),
        source_url=str(body.source_url) if body.source_url else None, notes=body.notes,
    )
    db.add(f)
    db.commit()
    return _fee_out(f)


@router.delete("/fees/{fee_id}", status_code=204)
def delete_fee(fee_id: int, db: Session = Depends(get_db)):
    f = db.get(AncillaryFee, fee_id)
    if not f:
        raise HTTPException(status_code=404, detail="Fee not found")
    db.delete(f)
    db.commit()
    return Response(status_code=204)


BUNDLES = [
    ("under_seat_only", "Free under-seat bag only", None),
    ("priority_trolley", "+ Priority & cabin trolley", "priority_trolley"),
    ("checked_bag", "+ Checked bag (20 kg)", "checked_bag_20kg"),
]


def _latest_fee(db: Session, flight_id: int, item: str, currency: str) -> AncillaryFee | None:
    rows = list(db.scalars(
        select(AncillaryFee).where(AncillaryFee.item == item, AncillaryFee.currency == currency)
        .order_by(AncillaryFee.observed_at_utc.desc())
    ))
    specific = [r for r in rows if r.flight_id == flight_id]
    return (specific or [r for r in rows if r.flight_id is None] or [None])[0]


@router.get("/fees/comparison")
def baggage_comparison(db: Session = Depends(get_db)):
    """Per target leg: latest public base fare + recorded add-on fees. Unknown fees stay unknown."""
    p = prefs(db)
    demo = demo_mode(db)
    cur = p["display_currency"]
    legs = []
    for fl in target_flights(db):
        base = db.scalar(
            select(PriceObservation).where(
                PriceObservation.flight_id == fl.id, PriceObservation.is_demo.is_(demo),
                PriceObservation.baggage_profile == "under_seat_only", PriceObservation.discount_club == "public",
                PriceObservation.currency == cur, PriceObservation.passengers == int(p["passengers"]),
            ).order_by(PriceObservation.captured_at_utc.desc()).limit(1)
        )
        base_price = from_minor(base.price_total_minor) if base else None
        options = []
        for key, label, fee_item in BUNDLES:
            fee = _latest_fee(db, fl.id, fee_item, cur) if fee_item else None
            fee_price = from_minor(fee.price_minor) if fee else (None if fee_item else from_minor(0))
            total = quantize(base_price + fee_price) if base_price is not None and fee_price is not None else None
            options.append({
                "bundle": key, "label": label, "base_fare": base_price, "addon_fee": fee_price,
                "addon_known": fee_price is not None, "total": total,
                "addon_source": fee.source if fee else None, "addon_observed_at": fee.observed_at_utc if fee else None,
                "addon_source_url": fee.source_url if fee else None,
            })
        legs.append({
            "flight_id": fl.id, "flight": f"{fl.flight_number} {fl.origin}->{fl.destination} {fl.flight_date}",
            "base_observed_at": base.captured_at_utc if base else None,
            "base_source": base.source if base else None, "options": options,
        })
    club = db.scalar(select(AncillaryFee).where(AncillaryFee.item == "discount_club_membership")
                     .order_by(AncillaryFee.observed_at_utc.desc()).limit(1))
    return {
        "demo": demo, "currency": cur, "legs": legs,
        "discount_club_membership": _fee_out(club) if club else None,
        "note": (
            "Add-on fees are shown only when you have recorded them. Unknown fees are not estimated. Wizz "
            "Discount Club membership is a separate cost; member fares are not generally available prices."
        ),
    }
