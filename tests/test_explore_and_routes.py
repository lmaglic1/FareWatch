"""Explore (Google Travel Explore) caching/throttling, route search and trips."""

import copy
import json
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from app.config import Settings
from app.models import ExploreSnapshot, PriceObservation, ProviderRun, SearchTarget
from app.providers.serpapi_google_flights import SerpApiGoogleFlightsProvider, parse_explore
from app.services import explore as explore_svc
from app.services.routes import RouteError, list_trips, route_view, search_route

from .conftest import FIXTURES

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc)
FLIGHTS = json.loads((FIXTURES / "serpapi_one_way_sjj_fco_TEST_FIXTURE.json").read_text())

# TEST FIXTURE ONLY - shaped like the documented Travel Explore response; not real prices.
EXPLORE = {
    "destinations": [
        {"destination_id": "/m/x1", "name": "Rome", "country": "Italy", "destination_airport": {"code": "FCO"},
         "start_date": "2026-12-03", "flight_price": 24, "flight_duration": 85, "number_of_stops": 0,
         "airline": "Wizz Air", "airline_code": "W4", "thumbnail": "https://example.org/rome.jpg"},
        {"destination_id": "/m/x2", "name": "Istanbul", "country": "Türkiye", "destination_airport": {"code": "IST"},
         "start_date": "2026-12-10", "flight_price": 61, "flight_duration": 110, "number_of_stops": 0,
         "airline": "Turkish Airlines", "airline_code": "TK", "thumbnail": "javascript:alert(1)"},
        {"name": "Broken", "destination_airport": {"code": ""}, "flight_price": 10},
        {"name": "No price", "destination_airport": {"code": "VIE"}},
    ]
}


def _provider(handler, **kw):
    s = Settings(serpapi_api_key="k", serpapi_max_retries=0, **kw)
    return SerpApiGoogleFlightsProvider(s, client=httpx.Client(transport=httpx.MockTransport(handler)),
                                        sleep=lambda _: None), s


def test_parse_explore_sorted_and_sanitized():
    d = parse_explore(EXPLORE, "EUR")
    assert [x.airport_code for x in d] == ["FCO", "IST"]
    assert str(d[0].price) == "24" and d[0].start_date == date(2026, 12, 3) and d[0].stops == 0
    assert d[1].thumbnail is None  # only https images are kept


def test_explore_refresh_params_cache_and_throttle(db):
    seen = []

    def handler(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json=EXPLORE)

    p, s = _provider(handler)
    r = explore_svc.refresh(db, origin="SJJ", trip_type="one_way", month=12, duration=2, provider=p, settings=s,
                            now=NOW)
    assert r["status"] == "success" and len(r["destinations"]) == 2
    assert seen[0]["engine"] == "google_travel_explore" and seen[0]["type"] == "2"
    assert seen[0]["departure_id"] == "SJJ" and seen[0]["month"] == "12" and seen[0]["travel_mode"] == "1"
    assert "travel_duration" not in seen[0]
    assert r["can_refresh"] is False
    # Second refresh within 6h is served from cache (no request)
    r2 = explore_svc.refresh(db, origin="SJJ", trip_type="one_way", month=12, duration=2, provider=p, settings=s,
                             now=NOW + timedelta(hours=2))
    assert r2["status"] == "skipped_recent" and len(seen) == 1 and len(r2["destinations"]) == 2
    # Round trip is a separate view with its own search
    explore_svc.refresh(db, origin="SJJ", trip_type="round_trip", month=12, duration=1, provider=p, settings=s,
                        now=NOW + timedelta(hours=2))
    assert seen[1]["type"] == "1" and seen[1]["travel_duration"] == "1"
    assert db.query(ExploreSnapshot).count() == 2
    assert db.query(ProviderRun).filter_by(trigger="explore").count() == 2


def test_explore_error_keeps_previous_snapshot(db):
    p, s = _provider(lambda req: httpx.Response(200, json=EXPLORE))
    explore_svc.refresh(db, origin="SJJ", trip_type="one_way", month=0, duration=2, provider=p, settings=s, now=NOW)
    bad, s2 = _provider(lambda req: httpx.Response(401, json={"error": "Invalid API key"}))
    r = explore_svc.refresh(db, origin="SJJ", trip_type="one_way", month=0, duration=2, provider=bad, settings=s2,
                            now=NOW + timedelta(hours=7))
    assert r["status"] == "error" and "Invalid API key" in r["message"]
    assert len(r["destinations"]) == 2  # old (real) results still shown, with their timestamp


def test_explore_unconfigured(db):
    r = explore_svc.refresh(db, origin="SJJ", trip_type="one_way", month=0, duration=2,
                            settings=Settings(serpapi_api_key=""), now=NOW)
    assert r["status"] == "skipped_unconfigured" and r["destinations"] == []


def test_route_search_any_destination_creates_trip(db):
    payload = copy.deepcopy(FLIGHTS)
    payload["other_flights"] = [payload["other_flights"][0]]  # single nonstop (W46160) + a connection
    payload["price_insights"]["price_history"] = [
        [int((NOW - timedelta(days=k)).timestamp()), 20 + k] for k in range(5, 0, -1)
    ]
    p, s = _provider(lambda req: httpx.Response(200, json=payload))
    r = search_route(db, origin="sjj", destination="fco", travel_date=date(2026, 12, 31), provider=p, settings=s,
                     now=NOW)
    assert r["status"] == "success" and r["observations_created"] == 6  # live + 5 history days
    view = route_view(db, "SJJ", "FCO", date(2026, 12, 31))
    assert view["destination"]["tz"] == "Europe/Rome"
    assert len(view["flights"]) == 1 and view["flights"][0]["analysis"]["primary"]["stats"]["count"] == 6
    # Repeat inside the minimum interval does not query again
    r2 = search_route(db, origin="SJJ", destination="FCO", travel_date=date(2026, 12, 31), provider=p, settings=s,
                      now=NOW + timedelta(minutes=10))
    assert r2["status"] == "skipped_recent"


def test_route_search_new_airport_uses_airport_database(db):
    p, s = _provider(lambda req: httpx.Response(200, json={"best_flights": [], "other_flights": []}))
    r = search_route(db, origin="SJJ", destination="IST", travel_date=date(2026, 12, 10), provider=p, settings=s,
                     now=NOW)
    assert r["status"] == "not_found"
    trips = list_trips(db)
    ist = [t for t in trips if t["destination"]["code"] == "IST"][0]
    assert ist["destination"]["tz"] == "Europe/Istanbul" and ist["latest_price"] is None
    assert db.query(PriceObservation).count() == 0


@pytest.mark.parametrize("o,d,dt,msg", [
    ("SJJ", "SJJ", date(2026, 12, 31), "differ"),
    ("SJJ", "ZZQ", date(2026, 12, 31), "Unknown airport"),
    ("SJJ", "FCO", date(2026, 1, 1), "past"),
])
def test_route_validation(db, o, d, dt, msg):
    with pytest.raises(RouteError, match=msg):
        search_route(db, origin=o, destination=d, travel_date=dt, settings=Settings(serpapi_api_key="k"), now=NOW)


def test_trips_api_includes_target_trip(client):
    trips = client.get("/api/trips").json()
    assert any(t["destination"]["code"] == "FCO" and t["kind"] == "target" for t in trips)
    assert client.get("/api/airports?q=sarajevo").json()[0]["code"] == "SJJ"
    e = client.get("/api/explore").json()
    assert e["origin"] == "SJJ" and e["snapshot"] is None and e["can_refresh"] is True
    t = [x for x in trips if x["destination"]["code"] == "FCO"][0]
    assert client.delete(f"/api/trips/{t['id']}").json()["ok"]
    assert not any(x["id"] == t["id"] for x in client.get("/api/trips").json())
