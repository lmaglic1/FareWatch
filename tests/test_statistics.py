from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.services.analysis import (
    ATTRACTIVE,
    EXPENSIVE,
    INSUFFICIENT,
    NORMAL,
    analyze_flight,
    combine_legs,
    compute_stats,
)
from app.services.features import feature_row, lead_time_days
from app.services.observations import record_observation

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
FD = date(2026, 12, 31)


def pts(*prices, step_hours=12):
    start = NOW - timedelta(hours=step_hours * len(prices))
    return [(start + timedelta(hours=step_hours * i), Decimal(p)) for i, p in enumerate(prices)]


def stats(points, **kw):
    return compute_stats(points, flight_date=FD, origin_tz="Europe/Sarajevo",
                         threshold_pct=Decimal("15"), min_samples=5, drop_pct=Decimal("10"), now=NOW, **kw)


def test_no_data():
    s = stats([])
    assert s["status"] == INSUFFICIENT and s["count"] == 0 and s["days_to_departure"] == 40


def test_insufficient_samples_explained():
    s = stats(pts("60", "62", "58"))
    assert s["status"] == INSUFFICIENT
    assert "3 comparable" in s["status_reason"] and "5" in s["status_reason"]
    assert s["min"] == Decimal("58") and s["max"] == Decimal("62")


def test_descriptive_stats():
    s = stats(pts("60", "70", "80", "90", "100"))
    assert s["median"] == Decimal("80.00")
    assert s["mean"] == Decimal("80.00")
    assert s["latest"] == Decimal("100") and s["previous"] == Decimal("90")
    assert s["pct_change_vs_previous"] == Decimal("11.11")
    assert s["latest_rank"] == 5 and s["latest_percentile"] == Decimal("80.00")
    assert s["volatility_stdev"] == Decimal("15.81")
    assert s["best"] == Decimal("60")


def test_attractive_normal_expensive():
    assert stats(pts("100", "100", "100", "100", "80"))["status"] == ATTRACTIVE
    assert stats(pts("100", "100", "100", "100", "95"))["status"] == NORMAL
    assert stats(pts("100", "100", "100", "100", "120"))["status"] == EXPENSIVE


def test_drop_detection():
    assert stats(pts("100", "100", "85"))["drop_detected"] is True
    assert stats(pts("100", "100", "95"))["drop_detected"] is False


def test_seven_day_median_requires_enough_data():
    old = [(NOW - timedelta(days=20 + i), Decimal("50")) for i in range(5)]
    s = stats(old + [(NOW - timedelta(days=1), Decimal("70"))])
    assert s["median_7d"] is None and "3 quotes" in s["median_7d_note"]
    s2 = stats(pts("60", "70", "80"))
    assert s2["median_7d"] == Decimal("70.00")


def test_lead_time_uses_local_date():
    # 23:30 UTC on Nov 20 is already Nov 21 in Sarajevo (UTC+1)
    t = datetime(2026, 11, 20, 23, 30, tzinfo=timezone.utc)
    assert lead_time_days(FD, t, "Europe/Sarajevo") == 40
    f = feature_row(FD, t, "Europe/Sarajevo")
    assert f["travel_is_holiday"] and f["travel_weekday"] == "Thu" and f["observation_weekday"] == "Sat"
    assert f["travel_festive_window"]


def _add(db, flight, price, hours_ago, club="public", bag="under_seat_only"):
    record_observation(db, flight=flight, price_total=Decimal(price), currency="EUR", source="manual",
                       verification="user_verified", display_currency="EUR",
                       captured_at_utc=NOW - timedelta(hours=hours_ago), baggage_profile=bag,
                       discount_club=club, taxes_fees_included="yes", fare_product="basic")


PREFS = {"display_currency": "EUR", "passengers": 1, "baggage_profile": "under_seat_only",
         "discount_club": "public", "median_threshold_pct": "15", "min_samples_for_status": 5,
         "drop_alert_pct": "10"}


def test_member_fares_are_kept_separate(db, targets):
    out, _ = targets
    for i, p in enumerate(["80", "82", "79", "81", "80"]):
        _add(db, out, p, 100 - i)
    _add(db, out, "40", 1, club="member")  # cheaper member fare must not distort public stats
    a = analyze_flight(db, out, PREFS, demo=False, now=NOW)
    assert a["primary"]["stats"]["count"] == 5
    assert a["primary"]["stats"]["min"] == Decimal("79")
    member = [p for p in a["profiles"] if p["is_member_fare"]]
    assert len(member) == 1 and not member[0]["matches_preferences"]


def test_combine_legs_requires_compatible_profiles(db, targets):
    out, ret = targets
    _add(db, out, "80", 5)
    _add(db, ret, "70", 5, bag="checked_bag")
    a = analyze_flight(db, out, PREFS, demo=False, now=NOW)["primary"]
    b_all = analyze_flight(db, ret, PREFS, demo=False, now=NOW)
    assert b_all["primary"] is None  # return only has checked-bag quotes
    assert combine_legs(a, b_all["profiles"][0])["available"] is False
    _add(db, ret, "65", 4)
    b = analyze_flight(db, ret, PREFS, demo=False, now=NOW)["primary"]
    c = combine_legs(a, b)
    assert c["available"] and c["latest_total"] == Decimal("145.00")
