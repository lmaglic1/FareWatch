"""Local alert evaluation with deduplication and optional email delivery."""

from __future__ import annotations

import hashlib
import logging
import smtplib
from decimal import Decimal
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..models import AlertEvent, AlertRule, PriceObservation
from ..money import from_minor, quantize
from .observations import ProfileKey

log = logging.getLogger("farewatch.alerts")


def _key(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def _rule_matches(rule: AlertRule, o: PriceObservation) -> bool:
    return (
        rule.active
        and rule.flight_id == o.flight_id
        and rule.currency == o.currency
        and rule.baggage_profile == o.baggage_profile
        and rule.discount_club == o.discount_club
    )


def _previous_comparable(db: Session, o: PriceObservation) -> PriceObservation | None:
    key = ProfileKey.of(o)
    candidates = db.scalars(
        select(PriceObservation)
        .where(
            PriceObservation.flight_id == o.flight_id,
            PriceObservation.is_demo.is_(False),
            PriceObservation.id != o.id,
            PriceObservation.captured_at_utc <= o.captured_at_utc,
        )
        .order_by(PriceObservation.captured_at_utc.desc(), PriceObservation.id.desc())
    )
    for c in candidates:
        if ProfileKey.of(c) == key:
            return c
    return None


def send_email(settings: Settings, subject: str, body: str) -> str:
    """Send an email only when fully configured. Returns a status string."""
    if not settings.email_configured:
        return "not_configured"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.alert_email_from
    msg["To"] = settings.alert_email_to
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            if settings.smtp_use_tls:
                s.starttls()
            if settings.smtp_username:
                s.login(settings.smtp_username, settings.smtp_password)
            s.send_message(msg)
        return "sent"
    except (OSError, smtplib.SMTPException) as exc:
        log.warning("Alert email failed: %s", type(exc).__name__)
        return "failed"


def evaluate_alerts(
    db: Session, o: PriceObservation, settings: Settings | None = None
) -> list[AlertEvent]:
    """Create alert events for a new observation. Demo data never triggers alerts."""
    if o.is_demo:
        return []
    settings = settings or get_settings()
    f = o.flight
    price = from_minor(o.price_total_minor)
    ident = f"{f.flight_number} {f.origin}->{f.destination} on {f.flight_date.isoformat()}"
    profile = ProfileKey.of(o)
    created: list[AlertEvent] = []

    rules = db.scalars(select(AlertRule).where(AlertRule.flight_id == o.flight_id, AlertRule.active.is_(True)))
    for rule in rules:
        if not _rule_matches(rule, o):
            continue
        message: str | None = None
        dedupe: str | None = None
        if rule.kind == "threshold" and rule.threshold_minor is not None:
            if o.price_total_minor <= rule.threshold_minor:
                message = (
                    f"{ident}: {price} {o.currency} is at or below your threshold of "
                    f"{from_minor(rule.threshold_minor)} {rule.currency} ({profile.label()}). Source: {o.source}."
                )
                # Same rule + same price + same profile -> one alert only.
                dedupe = _key("thr", rule.id, o.price_total_minor, profile)
        elif rule.kind == "pct_drop" and rule.pct_drop:
            prev = _previous_comparable(db, o)
            if prev and prev.price_total_minor > 0:
                drop = quantize(
                    Decimal(prev.price_total_minor - o.price_total_minor) / Decimal(prev.price_total_minor) * 100
                )
                if drop >= Decimal(rule.pct_drop):
                    message = (
                        f"{ident}: price dropped {drop}% from {from_minor(prev.price_total_minor)} to "
                        f"{price} {o.currency} ({profile.label()}). Source: {o.source}."
                    )
                    dedupe = _key("drop", rule.id, prev.price_total_minor, o.price_total_minor, profile)
        if not message or not dedupe:
            continue
        if db.scalar(select(AlertEvent.id).where(AlertEvent.dedupe_key == dedupe)):
            continue
        ev = AlertEvent(
            rule_id=rule.id, flight_id=o.flight_id, observation_id=o.id, message=message, dedupe_key=dedupe,
            email_status="pending" if rule.email else "not_requested",
        )
        db.add(ev)
        db.flush()
        if rule.email:
            ev.email_status = send_email(settings, f"FareWatch alert: {ident}", message + (
                "\n\nPrices change frequently. Verify the final price, baggage and fees on the airline's "
                "official site before buying. FareWatch never books automatically."
            ))
        created.append(ev)
    db.commit()
    return created
