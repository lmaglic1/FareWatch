from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models import PriceObservation
from app.money import MoneyError, convert, from_minor, to_minor
from app.services.observations import record_observation


def test_minor_units_avoid_float_errors():
    assert to_minor("0.1") + to_minor("0.2") == to_minor("0.3")
    assert to_minor(0.1) == 10
    assert to_minor("49,99") == 4999
    assert from_minor(4999) == Decimal("49.99")
    assert to_minor("10.005") == 1001  # ROUND_HALF_UP


def test_bam_peg_conversion_and_provenance():
    eur, rate, src = convert(Decimal("195.58"), "BAM", "EUR")
    assert eur == Decimal("100.00")
    assert "1.95583" in src


def test_unknown_rate_requires_source():
    with pytest.raises(MoneyError):
        convert(Decimal("100"), "USD", "EUR")
    with pytest.raises(MoneyError):
        convert(Decimal("100"), "USD", "EUR", user_rate=Decimal("0.9"))
    v, rate, src = convert(Decimal("100"), "USD", "EUR", Decimal("0.9"), "ECB 2026-11-20")
    assert v == Decimal("90.00") and src == "ECB 2026-11-20"


def _rec(db, flight, price="59.99", when=None, **kw):
    return record_observation(
        db, flight=flight, price_total=Decimal(price), currency=kw.pop("currency", "EUR"), source="manual",
        verification="user_verified", display_currency="EUR",
        captured_at_utc=when or datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc),
        baggage_profile="under_seat_only", discount_club="public", **kw,
    )


def test_store_observation(db, targets):
    out, _ = targets
    r = _rec(db, out)
    assert not r.duplicate
    stored = db.get(PriceObservation, r.observation.id)
    assert stored.price_total_minor == 5999
    assert stored.currency == "EUR" and stored.original_currency == "EUR"
    assert stored.captured_at_utc.tzinfo is not None
    assert stored.is_demo is False


def test_duplicate_is_rejected(db, targets):
    out, _ = targets
    t = datetime(2026, 11, 20, 8, 0, 15, tzinfo=timezone.utc)
    assert not _rec(db, out, when=t).duplicate
    assert _rec(db, out, when=t + timedelta(seconds=20)).duplicate  # same minute, same quote
    assert not _rec(db, out, when=t + timedelta(hours=3)).duplicate  # later identical quote is a new observation
    assert db.query(PriceObservation).count() == 2


def test_different_profile_is_not_duplicate(db, targets):
    out, _ = targets
    assert not _rec(db, out).duplicate
    assert not record_observation(
        db, flight=out, price_total=Decimal("59.99"), currency="EUR", source="manual",
        verification="user_verified", display_currency="EUR",
        captured_at_utc=datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc),
        baggage_profile="checked_bag", discount_club="public",
    ).duplicate


def test_bam_input_is_converted_with_original_preserved(db, targets):
    out, _ = targets
    r = _rec(db, out, price="117.35", currency="BAM")
    o = r.observation
    assert o.currency == "EUR" and o.original_currency == "BAM"
    assert o.original_price_minor == 11735
    assert o.price_total_minor == to_minor(Decimal("117.35") / Decimal("1.95583"))
    assert o.fx_source and "peg" in o.fx_source.lower()


def test_naive_datetime_rejected(db, targets):
    out, _ = targets
    with pytest.raises(Exception):
        _rec(db, out, when=datetime(2026, 11, 20, 8, 0))
        db.commit()
