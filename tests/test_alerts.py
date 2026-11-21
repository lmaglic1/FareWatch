from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.config import Settings
from app.models import AlertEvent, AlertRule
from app.services.alerts import evaluate_alerts, send_email
from app.services.observations import record_observation

T0 = datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)


def _obs(db, flight, price, hours, demo=False, club="public"):
    r = record_observation(db, flight=flight, price_total=Decimal(price), currency="EUR",
                           source="demo_fixture" if demo else "manual",
                           verification="demo" if demo else "user_verified", display_currency="EUR",
                           captured_at_utc=T0 + timedelta(hours=hours), baggage_profile="under_seat_only",
                           discount_club=club, is_demo=demo)
    return r.observation


def _rule(db, flight, **kw):
    r = AlertRule(flight_id=flight.id, currency="EUR", baggage_profile="under_seat_only", discount_club="public", **kw)
    db.add(r)
    db.commit()
    return r


def test_threshold_alert_and_dedup(db, targets):
    out, _ = targets
    _rule(db, out, kind="threshold", threshold_minor=6000)
    assert evaluate_alerts(db, _obs(db, out, "75", 0)) == []
    evs = evaluate_alerts(db, _obs(db, out, "59.99", 1))
    assert len(evs) == 1 and "W46160" in evs[0].message and "2026-12-31" in evs[0].message
    # Same price seen again later -> no new alert
    assert evaluate_alerts(db, _obs(db, out, "59.99", 13)) == []
    # A new, different qualifying price -> new alert
    assert len(evaluate_alerts(db, _obs(db, out, "55", 25))) == 1
    assert db.query(AlertEvent).count() == 2


def test_pct_drop_alert(db, targets):
    out, _ = targets
    _rule(db, out, kind="pct_drop", pct_drop="10")
    evaluate_alerts(db, _obs(db, out, "100", 0))
    assert evaluate_alerts(db, _obs(db, out, "95", 1)) == []
    evs = evaluate_alerts(db, _obs(db, out, "80", 2))
    assert len(evs) == 1 and "15.79%" in evs[0].message


def test_member_fare_does_not_trigger_public_rule(db, targets):
    out, _ = targets
    _rule(db, out, kind="threshold", threshold_minor=6000)
    assert evaluate_alerts(db, _obs(db, out, "40", 0, club="member")) == []


def test_demo_never_triggers(db, targets):
    out, _ = targets
    _rule(db, out, kind="threshold", threshold_minor=10000)
    assert evaluate_alerts(db, _obs(db, out, "10", 0, demo=True)) == []


def test_email_not_sent_without_configuration():
    assert send_email(Settings(alert_email_enabled=False), "s", "b") == "not_configured"
    assert send_email(Settings(alert_email_enabled=True, smtp_host=""), "s", "b") == "not_configured"


def test_email_rule_without_config_records_status(db, targets):
    out, _ = targets
    _rule(db, out, kind="threshold", threshold_minor=6000, email=True)
    evs = evaluate_alerts(db, _obs(db, out, "50", 0), Settings(alert_email_enabled=False))
    assert evs[0].email_status == "not_configured"
