"""Collector: quota caps, minimum interval, failure logging, no mock substitution."""

import json
from datetime import datetime, timedelta, timezone

import httpx

from app.config import Settings
from app.models import PriceObservation, ProviderRun
from app.providers.serpapi_google_flights import SerpApiGoogleFlightsProvider
from app.services.collector import run_collection

from .conftest import FIXTURES

PAYLOAD = json.loads((FIXTURES / "serpapi_one_way_sjj_fco_TEST_FIXTURE.json").read_text())
NOW = datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc)


def _provider(handler, **kw):
    s = Settings(serpapi_api_key="k", serpapi_max_retries=0, **kw)
    return SerpApiGoogleFlightsProvider(s, client=httpx.Client(transport=httpx.MockTransport(handler)),
                                        sleep=lambda _: None), s


def test_unconfigured_logs_skip_and_creates_nothing(db, targets):
    res = run_collection(db, trigger="manual", settings=Settings(serpapi_api_key=""), now=NOW)
    assert res["ran"] is False
    assert db.query(PriceObservation).count() == 0
    assert {r.status for r in db.query(ProviderRun)} == {"skipped_unconfigured"}


def test_success_stores_matched_and_other_nonstop_flights(db, targets):
    calls = []

    def handler(req):
        calls.append(dict(req.url.params))
        if req.url.params["departure_id"] == "SJJ":
            return httpx.Response(200, json=PAYLOAD)
        return httpx.Response(200, json={"best_flights": [], "other_flights": []})

    p, s = _provider(handler)
    res = run_collection(db, trigger="manual", include_comparisons=False, provider=p, settings=s, now=NOW)
    statuses = [r["status"] for r in res["results"]]
    assert statuses == ["success", "not_found"]
    obs = db.query(PriceObservation).all()
    assert len(obs) == 1  # W46160 priced; AZ515 had no price; connection ignored
    o = obs[0]
    assert o.flight.flight_number == "W46160" and o.flight.is_target
    assert o.source == "serpapi_google_flights" and o.verification == "api_reported"
    assert o.profile_assumed and o.price_total_minor == 11100
    assert o.flight.schedule_status == "matches_provider"


def test_failure_creates_no_observation(db, targets):
    p, s = _provider(lambda req: httpx.Response(500))
    run_collection(db, trigger="manual", include_comparisons=False, provider=p, settings=s, now=NOW)
    assert db.query(PriceObservation).count() == 0
    runs = db.query(ProviderRun).all()
    assert all(r.status == "error" for r in runs) and len(runs) == 2


def test_min_interval_prevents_repeat_checks(db, targets):
    p, s = _provider(lambda req: httpx.Response(200, json=PAYLOAD))
    run_collection(db, trigger="manual", include_comparisons=False, provider=p, settings=s, now=NOW)
    res = run_collection(db, trigger="manual", include_comparisons=False, provider=p, settings=s,
                         now=NOW + timedelta(minutes=30))
    assert [r["status"] for r in res["results"]] == ["skipped_recent", "skipped_recent"]


def test_daily_cap_is_never_exceeded(db, targets):
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(200, json=PAYLOAD)

    p, s = _provider(handler)
    t = NOW
    for _ in range(6):  # many manual refreshes, spaced past the minimum interval
        run_collection(db, trigger="manual", include_comparisons=True, provider=p, settings=s, now=t)
        t += timedelta(hours=2, minutes=1)
        if t.astimezone(timezone(timedelta(hours=1))).date() != NOW.astimezone(timezone(timedelta(hours=1))).date():
            break
    assert calls["n"] == 6  # 2 targets + 1 comparison per run, then capped
    assert any(r.status == "skipped_quota" for r in db.query(ProviderRun))


def test_monthly_quota_respected(db, targets):
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(200, json=PAYLOAD)

    p, s = _provider(handler, serpapi_monthly_quota=1)
    run_collection(db, trigger="manual", include_comparisons=False, provider=p, settings=s, now=NOW)
    assert calls["n"] == 1
