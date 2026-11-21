"""Flight matching and SerpApi response parsing, using a labelled TEST FIXTURE."""

import json
from datetime import date

import httpx
import pytest

from app.config import Settings
from app.flights import normalize_flight_number
from app.providers.serpapi_google_flights import (
    SerpApiGoogleFlightsProvider,
    interpret,
    parse_candidates,
    redact,
)

from .conftest import FIXTURES

PAYLOAD = json.loads((FIXTURES / "serpapi_one_way_sjj_fco_TEST_FIXTURE.json").read_text())
D = date(2026, 12, 31)


@pytest.mark.parametrize("raw", ["W4 6160", "w4-6160", "W46160", "W4 06160"])
def test_normalize_flight_number(raw):
    assert normalize_flight_number(raw) == "W46160"


def test_normalize_rejects_garbage():
    with pytest.raises(ValueError):
        normalize_flight_number("Wizz")


def test_parse_ignores_connections():
    cands = parse_candidates(PAYLOAD, "EUR")
    assert {c.flight_number for c in cands} == {"W46160", "AZ515"}  # OS 770+501 has 2 segments


def test_match_target_flight():
    r = interpret(PAYLOAD, origin="SJJ", destination="FCO", travel_date=D, currency="EUR",
                  expected_flight_number="W46160", queries_used=1, http_status=200)
    assert r.status == "success"
    assert r.matched.flight_number == "W46160"
    assert str(r.matched.price) == "111"
    assert r.matched.departure_local.strftime("%H:%M") == "21:10"
    assert r.matched.arrival_local.strftime("%H:%M") == "22:35"


def test_wrong_date_does_not_match():
    r = interpret(PAYLOAD, origin="SJJ", destination="FCO", travel_date=date(2027, 1, 1), currency="EUR",
                  expected_flight_number="W46160", queries_used=1, http_status=200)
    assert r.status == "not_found"


def test_wrong_direction_does_not_match():
    r = interpret(PAYLOAD, origin="FCO", destination="SJJ", travel_date=D, currency="EUR",
                  expected_flight_number="W46160", queries_used=1, http_status=200)
    assert r.status == "not_found" and r.matched is None


def test_missing_wizz_flight_is_not_found():
    r = interpret(PAYLOAD, origin="SJJ", destination="FCO", travel_date=D, currency="EUR",
                  expected_flight_number="W46162", queries_used=1, http_status=200)
    assert r.status == "not_found"
    assert "W46160" in r.message  # explains what was seen


def test_listed_without_price():
    r = interpret(PAYLOAD, origin="SJJ", destination="FCO", travel_date=D, currency="EUR",
                  expected_flight_number="AZ515", queries_used=1, http_status=200)
    assert r.status == "no_price" and r.matched.price is None


def test_error_payload():
    r = interpret({"error": "Invalid API key."}, origin="SJJ", destination="FCO", travel_date=D,
                  currency="EUR", expected_flight_number="W46160", queries_used=1, http_status=401)
    assert r.status == "error" and r.candidates == []
    r2 = interpret({"error": "Google Flights hasn't returned any results for this query."}, origin="SJJ",
                   destination="FCO", travel_date=D, currency="EUR", expected_flight_number="W46160",
                   queries_used=1, http_status=200)
    assert r2.status == "not_found"


def test_empty_results():
    r = interpret({}, origin="SJJ", destination="FCO", travel_date=D, currency="EUR",
                  expected_flight_number="W46160", queries_used=1, http_status=200)
    assert r.status == "not_found"


def test_redact_api_key():
    assert redact("https://serpapi.com/search?api_key=SECRET123&x=1") == "https://serpapi.com/search?api_key=***&x=1"


def _provider(handler, **kw):
    s = Settings(serpapi_api_key="test-key", serpapi_max_retries=2, **kw)
    return SerpApiGoogleFlightsProvider(s, client=httpx.Client(transport=httpx.MockTransport(handler)),
                                        sleep=lambda _: None)


def test_request_parameters_follow_docs():
    seen = {}

    def handler(req: httpx.Request):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json=PAYLOAD)

    r = _provider(handler).search_one_way(origin="SJJ", destination="FCO", travel_date=D, currency="EUR",
                                          adults=1, expected_flight_number="W46160")
    assert r.status == "success"
    assert seen["engine"] == "google_flights" and seen["type"] == "2" and seen["stops"] == "1"
    assert seen["departure_id"] == "SJJ" and seen["arrival_id"] == "FCO"
    assert seen["outbound_date"] == "2026-12-31" and seen["currency"] == "EUR" and seen["travel_class"] == "1"


def test_retries_on_5xx_then_succeeds():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] == 1 else httpx.Response(200, json=PAYLOAD)

    r = _provider(handler).search_one_way(origin="SJJ", destination="FCO", travel_date=D, currency="EUR",
                                          adults=1, expected_flight_number="W46160")
    assert r.status == "success" and r.queries_used == 2


def test_retries_are_capped_by_budget():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(500)

    r = _provider(handler).search_one_way(origin="SJJ", destination="FCO", travel_date=D, currency="EUR",
                                          adults=1, expected_flight_number="W46160", max_attempts=1)
    assert r.status == "error" and calls["n"] == 1 and r.queries_used == 1


def test_no_retry_on_4xx_and_key_not_leaked():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(401, json={"error": "Invalid API key. api_key=test-key"})

    r = _provider(handler).search_one_way(origin="SJJ", destination="FCO", travel_date=D, currency="EUR",
                                          adults=1, expected_flight_number="W46160")
    assert r.status == "error" and calls["n"] == 1
    assert "test-key" not in r.message


def test_network_failure_reports_error():
    def handler(req):
        raise httpx.ConnectTimeout("timeout")

    r = _provider(handler).search_one_way(origin="SJJ", destination="FCO", travel_date=D, currency="EUR",
                                          adults=1, expected_flight_number="W46160")
    assert r.status == "error" and r.queries_used == 3 and r.candidates == []


def test_unconfigured_provider_makes_no_request():
    p = SerpApiGoogleFlightsProvider(Settings(serpapi_api_key=""))
    r = p.search_one_way(origin="SJJ", destination="FCO", travel_date=D, currency="EUR", adults=1,
                         expected_flight_number="W46160")
    assert r.status == "error" and r.queries_used == 0
