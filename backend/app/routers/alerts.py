from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import AlertEvent, AlertRule
from ..money import from_minor, normalize_currency, to_minor
from ..schemas import AlertRuleIn
from .common import get_flight_or_404

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _rule_out(r: AlertRule) -> dict:
    f = r.flight
    return {
        "id": r.id, "flight_id": r.flight_id, "kind": r.kind,
        "threshold": from_minor(r.threshold_minor), "pct_drop": r.pct_drop, "currency": r.currency,
        "baggage_profile": r.baggage_profile, "discount_club": r.discount_club, "active": r.active,
        "email": r.email, "created_at": r.created_at,
        "flight": f"{f.flight_number} {f.origin}->{f.destination} {f.flight_date.isoformat()}",
    }


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    return [_rule_out(r) for r in db.scalars(select(AlertRule).order_by(AlertRule.id))]


@router.post("/rules", status_code=201)
def create_rule(body: AlertRuleIn, db: Session = Depends(get_db)):
    get_flight_or_404(db, body.flight_id)
    try:
        cur = normalize_currency(body.currency)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.email and not get_settings().email_configured:
        raise HTTPException(status_code=422, detail="Email alerts are not configured (see .env.example)")
    r = AlertRule(
        flight_id=body.flight_id, kind=body.kind,
        threshold_minor=to_minor(body.threshold) if body.threshold is not None else None,
        pct_drop=str(body.pct_drop) if body.pct_drop is not None else None,
        currency=cur, baggage_profile=body.baggage_profile, discount_club=body.discount_club, email=body.email,
    )
    db.add(r)
    db.commit()
    return _rule_out(r)


@router.patch("/rules/{rule_id}")
def toggle_rule(rule_id: int, active: bool, db: Session = Depends(get_db)):
    r = db.get(AlertRule, rule_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rule not found")
    r.active = active
    db.commit()
    return _rule_out(r)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    r = db.get(AlertRule, rule_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rule not found")
    for ev in db.scalars(select(AlertEvent).where(AlertEvent.rule_id == rule_id)):
        db.delete(ev)
    db.delete(r)
    db.commit()
    return Response(status_code=204)


@router.get("/events")
def list_events(db: Session = Depends(get_db)):
    from ..models import FlightIdentity

    out = []
    for e in db.scalars(select(AlertEvent).order_by(AlertEvent.triggered_at_utc.desc()).limit(500)):
        f = db.get(FlightIdentity, e.flight_id)
        out.append({
            "id": e.id, "rule_id": e.rule_id, "flight_id": e.flight_id, "observation_id": e.observation_id,
            "triggered_at_utc": e.triggered_at_utc, "message": e.message, "email_status": e.email_status,
            "acknowledged": e.acknowledged,
            "flight": f"{f.flight_number} {f.origin}->{f.destination} {f.flight_date.isoformat()}" if f else None,
        })
    return out


@router.post("/events/{event_id}/ack")
def ack_event(event_id: int, db: Session = Depends(get_db)):
    e = db.get(AlertEvent, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    e.acknowledged = True
    db.commit()
    return {"ok": True}
