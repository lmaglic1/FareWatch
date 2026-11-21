"""Google Flights price history (price_insights.price_history) import via SerpApi."""

import copy
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx

from app.config import Settings
from app.models import AlertEvent, AlertRule, PriceObservation, ProviderRun
from app.providers.serpapi_google_flights import SerpApiGoogleFlightsProvider, interpret, parse_price_history
from app.services.analysis import analyze_flight
from app.services.collector import run_collection

from .conftest import FIXTURES

BASE = json.loads((FIXTURES / "serpapi_one_way_sjj_fco_TEST_FIXTURE.json").read_text())
NOW = datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc)


def _ts(days_ago: int) -> int:
    return int((NOW - timedelta(days=days_ago)).replace(hour=0).timestamp())


def payload_with_history(only_wizz: bool = True, prices=(19, 20, 22, 24, 24, 27, 32)) -> dict:
    p = copy.deepcopy(BASE)
    if only_wizz:  # the real route has a single nonstop carrier
        p["other_flights"] = [p["other_flights"][0]]  # keep only the 2-segment connection
    n = len(prices)
    p["price_insights"]["price_history"] = [[_ts(n - 1 - i), v] for i, v in enumerate(prices)]
    return p


def test_parse_price_history_skips_malformed():
    p = {"price_insights": {"price_history": [[_ts(3), 21], [_ts(2)], ["x", 5], [_ts(1), 0], [_ts(0), 23.5]]}}
    h = parse_price_history(p)
    assert [str(v) for _, v in h] == ["21", "23.5"]
    assert all(t.tzinfo is not None for t, _ in h)
    assert parse_price_history({}) == []


def test_interpret_attaches_history_but_not_on_error():
    r = interpret(payload_with_history(), origin="SJJ", destination="FCO", travel_date=date(2026, 12, 31),
                  currency="EUR", expected_flight_number="W46160", queries_used=1, http_status=200)
    assert len(r.price_history) == 7
    e = interpret({"error": "Invalid API key", "price_insights": {"price_history": [[_ts(1), 5]]}}, origin="SJJ",
                  destination="FCO", travel_date=date(2026, 12, 31), currency="EUR",
                  expected_flight_number="W46160", queries_used=1, http_status=401)
    assert e.price_history == []


def _provider(handler):
    s = Settings(serpapi_api_key="k", serpapi_max_retries=0)
    return SerpApiGoogleFlightsProvider(s, client=httpx.Client(transport=httpx.MockTransport(handler)),
                                        sleep=lambda _: None), s


def test_history_imported_for_single_nonstop_flight(db, targets):
    out, _ = targets
    db.add(AlertRule(flight_id=out.id, kind="threshold", threshold_minor=20000, currency="EUR",
                     baggage_profile="under_seat_only", discount_club="public"))
    db.commit()

    def handler(req):
        if req.url.params["departure_id"] == "SJJ":
            return httpx.Response(200, json=payload_with_history())
        return httpx.Response(200, json={"best_flights": [], "other_flights": []})

    p, s = _provider(handler)
    run_collection(db, trigger="manual", include_comparisons=False, provider=p, settings=s, now=NOW)
    hist = db.query(PriceObservation).filter_by(source="serpapi_price_history").all()
    assert len(hist) == 7
    assert all(o.flight_id == out.id and o.verification == "api_price_history" and o.profile_assumed for o in hist)
    assert sorted(o.price_total_minor for o in hist)[0] == 1900
    # live quote stored as well; only that one can alert (history never alerts)
    live = db.query(PriceObservation).filter_by(source="serpapi_google_flights").all()
    assert len(live) == 1
    assert db.query(AlertEvent).count() == 1 and db.query(AlertEvent).one().observation_id == live[0].id
    msg = db.query(ProviderRun).filter_by(origin="SJJ").one().message
    assert "7 new day(s)" in msg

    # History + live quote now give enough comparable data for a status
    prefs = {"display_currency": "EUR", "passengers": 1, "baggage_profile": "under_seat_only",
             "discount_club": "public", "median_threshold_pct": "15", "min_samples_for_status": 5,
             "drop_alert_pct": "10"}
    a = analyze_flight(db, out, prefs, demo=False, now=NOW)
    assert a["primary"]["stats"]["count"] == 8
    assert a["primary"]["stats"]["status"] != "INSUFFICIENT DATA"


def test_history_reimport_is_deduplicated(db, targets):
    p, s = _provider(lambda req: httpx.Response(200, json=payload_with_history()))
    run_collection(db, trigger="manual", include_comparisons=False, provider=p, settings=s, now=NOW)
    first = db.query(PriceObservation).filter_by(source="serpapi_price_history").count()
    run_collection(db, trigger="manual", include_comparisons=False, provider=p, settings=s,
                   now=NOW + timedelta(hours=3))
    assert db.query(PriceObservation).filter_by(source="serpapi_price_history").count() == first


def test_history_not_attributed_when_several_nonstop_flights(db, targets):
    p, s = _provider(lambda req: httpx.Response(200, json=payload_with_history(only_wizz=False)))
    run_collection(db, trigger="manual", include_comparisons=False, provider=p, settings=s, now=NOW)
    assert db.query(PriceObservation).filter_by(source="serpapi_price_history").count() == 0
    msg = db.query(ProviderRun).filter_by(origin="SJJ").one().message
    assert "not imported" in msg and "2 nonstop flights" in msg


def test_backfill_several_comparison_dates_within_cap(db, targets):
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(200, json={"best_flights": [], "other_flights": []})

    p, s = _provider(handler)
    run_collection(db, trigger="manual", include_comparisons=True, comparison_count=10, provider=p,
                   settings=s, now=NOW)
    assert calls["n"] == 6  # 2 targets + 4 comparison dates = daily cap


def test_history_price_decimal_exact():
    h = parse_price_history({"price_insights": {"price_history": [[_ts(1), 24.1]]}})
    assert h[0][1] == Decimal("24.1")
