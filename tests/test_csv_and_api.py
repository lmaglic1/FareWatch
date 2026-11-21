"""CSV import/export and the end-to-end vertical slice through the HTTP API."""

from app.models import PriceObservation
from app.providers.csv_import import CSVImportProvider, export_csv

HEADER = "flight_number,origin,destination,flight_date,captured_at_utc,price_total,currency,baggage_profile,discount_club\n"


def test_csv_import_validates_rows(db, targets):
    text = HEADER + (
        "W4 6160,SJJ,FCO,2026-12-31,2026-11-10T08:00:00Z,64.99,EUR,under_seat_only,public\n"
        "W4 6160,SJJ,FCO,2026-12-31,2026-11-10T08:00:00Z,64.99,EUR,under_seat_only,public\n"  # duplicate
        "W4 6160,SJJ,FCO,2026-12-31,2026-11-10T08:00:00,64.99,EUR,under_seat_only,public\n"  # naive ts
        "W4 6160,SJJ,FCO,2026-12-31,2026-11-11T08:00:00Z,-5,EUR,under_seat_only,public\n"  # bad price
        "W4 6160,SJJ,FCO,2026-12-31,2026-11-11T08:00:00Z,70,XYZ,under_seat_only,public\n"  # bad currency
        "W4 6160,SJJ,FCO,2026-12-31,2026-11-11T08:00:00Z,70,EUR,suitcase,public\n"  # bad baggage
        "W4 6159,FCO,SJJ,2027-01-05,2026-11-12T08:00:00Z,58.50,EUR,under_seat_only,public\n"
    )
    rep = CSVImportProvider().import_csv(db, text, "EUR")
    assert rep.imported == 2 and rep.duplicates == 1 and len(rep.errors) == 4
    assert {e["row"] for e in rep.errors} == {4, 5, 6, 7}
    o = db.query(PriceObservation).first()
    assert o.source == "csv_import" and o.verification == "imported_unverified"


def test_csv_rejects_demo_rows_and_missing_headers(db, targets):
    rep = CSVImportProvider().import_csv(db, "flight_number,price_total\nW46160,10\n", "EUR")
    assert rep.imported == 0 and "Missing header" in rep.errors[0]["error"]
    text = HEADER.strip() + ",is_demo\n" + "W46160,SJJ,FCO,2026-12-31,2026-11-10T08:00:00Z,60,EUR,under_seat_only,public,true\n"
    rep2 = CSVImportProvider().import_csv(db, text, "EUR")
    assert rep2.imported == 0 and "Demo" in rep2.errors[0]["error"]


def test_csv_dry_run_writes_nothing(db, targets):
    text = HEADER + "W46160,SJJ,FCO,2026-12-31,2026-11-10T08:00:00Z,60,EUR,under_seat_only,public\n"
    rep = CSVImportProvider().import_csv(db, text, "EUR", dry_run=True)
    assert rep.errors == [] and rep.imported == 0 and db.query(PriceObservation).count() == 0


def test_csv_round_trip(db, targets):
    text = HEADER + "W46160,SJJ,FCO,2026-12-31,2026-11-10T08:00:00Z,60.10,EUR,under_seat_only,public\n"
    CSVImportProvider().import_csv(db, text, "EUR")
    exported = export_csv(db.query(PriceObservation).all())
    assert "60.10" in exported and "csv_import" in exported
    db.query(PriceObservation).delete()
    db.commit()
    rep = CSVImportProvider().import_csv(db, exported, "EUR")
    assert rep.imported == 1 and rep.errors == []


# --- Vertical slice: manual entry -> SQLite -> API -> dashboard/analysis ----

def _flights(client):
    fl = client.get("/api/flights").json()
    return [f for f in fl if f["is_target"]]


def test_manual_entry_to_dashboard(client):
    out, ret = _flights(client)
    assert out["flight_number"] == "W46160" and out["scheduled_departure_local"] == "21:10:00"
    assert ret["flight_number"] == "W46159" and ret["origin_tz"] == "Europe/Rome"
    body = {"flight_id": out["id"], "price_total": "64.99", "currency": "EUR", "baggage_profile": "under_seat_only",
            "discount_club": "public", "fare_product": "basic", "taxes_fees_included": "yes",
            "source_url": "https://wizzair.com/", "captured_at_utc": "2026-11-20T18:00:00Z"}
    r = client.post("/api/observations", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["observation"]["source"] == "manual"
    assert client.post("/api/observations", json=body).json()["duplicate"] is True

    d = client.get("/api/dashboard").json()
    assert d["demo"] is False
    leg = d["legs"][0]
    assert leg["latest_observation"]["price_total"] == "64.99"
    assert leg["analysis"]["primary"]["stats"]["status"] == "INSUFFICIENT DATA"
    assert d["combined_legs"]["available"] is False

    detail = client.get(f"/api/flights/{out['id']}").json()
    assert len(detail["observations"]) == 1
    assert all("wizzair.com" in l["url"] or "google.com/travel/flights" in l["url"] for l in detail["booking_links"])


def test_manual_entry_validation(client):
    out, _ = _flights(client)
    bad = [
        {"flight_id": out["id"], "price_total": "-1", "currency": "EUR"},
        {"flight_id": out["id"], "price_total": "50", "currency": "EUR", "captured_at_utc": "2099-01-01T00:00:00Z"},
        {"flight_id": out["id"], "price_total": "50.123", "currency": "EUR"},
        {"flight_id": out["id"], "price_total": "50", "currency": "EUR", "source_url": "not a url"},
        {"flight_id": out["id"], "price_total": "50", "currency": "EUR", "baggage_profile": "suitcase"},
    ]
    for b in bad:
        assert client.post("/api/observations", json=b).status_code == 422, b
    assert client.post("/api/observations", json={"flight_id": 9999, "price_total": "50", "currency": "EUR"}).status_code == 404


def test_demo_mode_is_separate_and_not_exported(client):
    out, _ = _flights(client)
    client.post("/api/observations", json={"flight_id": out["id"], "price_total": "70", "currency": "EUR",
                                           "captured_at_utc": "2026-11-20T18:00:00Z"})
    assert client.put("/api/settings", json={"demo_mode": True}).status_code == 200
    d = client.get("/api/dashboard").json()
    assert d["demo"] is True
    items = client.get("/api/observations").json()["items"]
    assert items and all(i["is_demo"] and i["source"] == "demo_fixture" for i in items)
    csv_text = client.get("/api/observations/export.csv").text
    assert "demo_fixture" not in csv_text and "70.00" in csv_text
    client.delete("/api/demo")
    items = client.get("/api/observations").json()["items"]
    assert len(items) == 1 and not items[0]["is_demo"]


def test_settings_validation(client):
    assert client.put("/api/settings", json={"median_threshold_pct": 500}).status_code == 422
    assert client.put("/api/settings", json={"serpapi_api_key": "x"}).status_code == 422
    r = client.put("/api/settings", json={"median_threshold_pct": "18"})
    assert r.status_code == 200 and r.json()["median_threshold_pct"] == "18"
    s = client.get("/api/settings").json()
    serp = [p for p in s["providers"] if p["name"] == "serpapi_google_flights"][0]
    assert serp["connected"] is False
    assert "api_key" not in str(s).lower().replace("serpapi_api_key", "")


def test_manual_refresh_without_key_is_explicit(client):
    r = client.post("/api/collector/run").json()
    assert r["ran"] is False and "not configured" in r["reason"]


def test_alert_rule_via_api(client):
    out, _ = _flights(client)
    r = client.post("/api/alerts/rules", json={"flight_id": out["id"], "kind": "threshold", "threshold": "60"})
    assert r.status_code == 201
    assert client.post("/api/alerts/rules", json={"flight_id": out["id"], "kind": "threshold"}).status_code == 422
    assert client.post("/api/alerts/rules", json={"flight_id": out["id"], "kind": "threshold", "threshold": "60",
                                                  "email": True}).status_code == 422  # email not configured
    res = client.post("/api/observations", json={"flight_id": out["id"], "price_total": "55", "currency": "EUR",
                                                 "baggage_profile": "under_seat_only", "discount_club": "public"})
    assert res.json()["alerts_triggered"] == 1
    ev = client.get("/api/alerts/events").json()
    assert ev[0]["flight"].startswith("W46160 SJJ->FCO 2026-12-31")


def test_fee_comparison_shows_unknown(client):
    out, _ = _flights(client)
    client.post("/api/observations", json={"flight_id": out["id"], "price_total": "50", "currency": "EUR",
                                           "baggage_profile": "under_seat_only", "discount_club": "public"})
    client.post("/api/fees", json={"flight_id": out["id"], "item": "priority_trolley", "price": "25.50",
                                   "currency": "EUR"})
    c = client.get("/api/fees/comparison").json()
    opts = {o["bundle"]: o for o in c["legs"][0]["options"]}
    assert opts["under_seat_only"]["total"] == "50.00"
    assert opts["priority_trolley"]["total"] == "75.50"
    assert opts["checked_bag"]["addon_known"] is False and opts["checked_bag"]["total"] is None


def test_round_trip_quote_stored_separately(client):
    out, ret = _flights(client)
    r = client.post("/api/round-trips", json={"outbound_flight_id": out["id"], "return_flight_id": ret["id"],
                                              "price_total": "140", "currency": "EUR"})
    assert r.status_code == 201
    bad = client.post("/api/round-trips", json={"outbound_flight_id": out["id"], "return_flight_id": out["id"],
                                                "price_total": "140", "currency": "EUR"})
    assert bad.status_code == 422


def test_forecast_disabled_without_data(client):
    f = client.get("/api/forecast").json()
    assert f["status"] == "insufficient_data"
