"""CSVImportProvider: import/export historical observations with validation."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from ..flights import get_or_create_flight, normalize_flight_number
from ..models import PriceObservation, Source, Verification
from ..money import MoneyError, from_minor, normalize_currency, to_decimal
from ..services.features import lead_time_days
from ..services.observations import record_observation

IMPORT_COLUMNS = [
    "flight_number", "origin", "destination", "flight_date", "captured_at_utc", "price_total", "currency",
    "passengers", "fare_product", "baggage_profile", "taxes_fees_included", "discount_club",
    "airline", "scheduled_departure_local", "scheduled_arrival_local", "source_url", "booking_url", "notes",
]
REQUIRED = ["flight_number", "origin", "destination", "flight_date", "captured_at_utc", "price_total", "currency"]
EXPORT_COLUMNS = ["id", *IMPORT_COLUMNS, "source", "verification", "original_price", "original_currency",
                  "fx_rate", "fx_source", "profile_assumed", "is_demo", "lead_time_days"]

ALLOWED = {
    "fare_product": {"basic", "wizz_go", "wizz_plus", "unknown"},
    "baggage_profile": {"under_seat_only", "priority_trolley", "checked_bag", "unknown"},
    "taxes_fees_included": {"yes", "no", "unknown"},
    "discount_club": {"public", "member", "unknown"},
}
MAX_ROWS = 5000


@dataclass
class ImportReport:
    total_rows: int = 0
    imported: int = 0
    duplicates: int = 0
    errors: list[dict] = field(default_factory=list)
    dry_run: bool = False


def _parse_dt(v: str) -> datetime:
    dt = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("captured_at_utc must include a timezone, e.g. 2026-11-20T08:00:00Z")
    return dt.astimezone(timezone.utc)


def _parse_time(v: str | None) -> time | None:
    if not v or not v.strip():
        return None
    return time.fromisoformat(v.strip())


def _validate_row(row: dict[str, str]) -> dict:
    missing = [c for c in REQUIRED if not (row.get(c) or "").strip()]
    if missing:
        raise ValueError(f"Missing required column value(s): {', '.join(missing)}")
    if (row.get("is_demo") or "").strip().lower() in {"true", "1", "yes"} or (
        (row.get("source") or "").strip() == Source.DEMO.value
    ):
        raise ValueError("Demo fixture rows cannot be imported as real observations")
    origin, dest = row["origin"].strip().upper(), row["destination"].strip().upper()
    if len(origin) != 3 or len(dest) != 3 or origin == dest:
        raise ValueError("origin/destination must be distinct 3-letter IATA codes")
    price = to_decimal(row["price_total"])
    if price <= 0 or price > Decimal("20000"):
        raise ValueError("price_total must be between 0 and 20000")
    captured = _parse_dt(row["captured_at_utc"])
    if captured > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("captured_at_utc is in the future")
    out = {
        "flight_number": normalize_flight_number(row["flight_number"]),
        "origin": origin,
        "destination": dest,
        "flight_date": date.fromisoformat(row["flight_date"].strip()),
        "captured_at_utc": captured,
        "price_total": price,
        "currency": normalize_currency(row["currency"]),
        "passengers": int((row.get("passengers") or "1").strip() or 1),
        "airline": (row.get("airline") or "").strip() or None,
        "dep": _parse_time(row.get("scheduled_departure_local")),
        "arr": _parse_time(row.get("scheduled_arrival_local")),
        "source_url": (row.get("source_url") or "").strip() or None,
        "booking_url": (row.get("booking_url") or "").strip() or None,
        "notes": (row.get("notes") or "").strip() or None,
    }
    if not 1 <= out["passengers"] <= 9:
        raise ValueError("passengers must be 1-9")
    for col, allowed in ALLOWED.items():
        v = (row.get(col) or "unknown").strip().lower() or "unknown"
        if v not in allowed:
            raise ValueError(f"{col} must be one of {sorted(allowed)}")
        out[col] = v
    for url_col in ("source_url", "booking_url"):
        if out[url_col] and not out[url_col].startswith(("http://", "https://")):
            raise ValueError(f"{url_col} must start with http:// or https://")
    return out


class CSVImportProvider:
    name = Source.CSV.value
    configured = True

    def import_csv(self, db: Session, text: str, display_currency: str, dry_run: bool = False) -> ImportReport:
        report = ImportReport(dry_run=dry_run)
        reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
        headers = set(reader.fieldnames or [])
        missing_headers = [c for c in REQUIRED if c not in headers]
        if missing_headers:
            report.errors.append({"row": 1, "error": f"Missing header column(s): {', '.join(missing_headers)}"})
            return report
        for idx, row in enumerate(reader, start=2):  # row 1 is the header
            report.total_rows += 1
            if report.total_rows > MAX_ROWS:
                report.errors.append({"row": idx, "error": f"File exceeds {MAX_ROWS} rows; split it"})
                break
            try:
                v = _validate_row(row)
            except (ValueError, MoneyError, KeyError) as exc:
                report.errors.append({"row": idx, "error": str(exc)})
                continue
            if dry_run:
                continue
            try:
                flight = get_or_create_flight(
                    db, origin=v["origin"], destination=v["destination"], flight_date=v["flight_date"],
                    flight_number=v["flight_number"], airline=v["airline"], dep=v["dep"], arr=v["arr"],
                )
                res = record_observation(
                    db, flight=flight, price_total=v["price_total"], currency=v["currency"],
                    source=self.name, verification=Verification.IMPORTED_UNVERIFIED.value,
                    display_currency=display_currency, captured_at_utc=v["captured_at_utc"],
                    passengers=v["passengers"], fare_product=v["fare_product"],
                    baggage_profile=v["baggage_profile"], taxes_fees_included=v["taxes_fees_included"],
                    discount_club=v["discount_club"], source_url=v["source_url"], booking_url=v["booking_url"],
                    notes=v["notes"], commit=False,
                )
            except (ValueError, MoneyError) as exc:
                db.rollback()
                report.errors.append({"row": idx, "error": str(exc)})
                continue
            if res.duplicate:
                report.duplicates += 1
            else:
                report.imported += 1
        if not dry_run:
            db.commit()
        return report


def export_csv(observations: list[PriceObservation]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
    w.writeheader()
    for o in observations:
        f = o.flight
        w.writerow({
            "id": o.id,
            "flight_number": f.flight_number,
            "origin": f.origin,
            "destination": f.destination,
            "flight_date": f.flight_date.isoformat(),
            "captured_at_utc": o.captured_at_utc.isoformat().replace("+00:00", "Z"),
            "price_total": str(from_minor(o.price_total_minor)),
            "currency": o.currency,
            "passengers": o.passengers,
            "fare_product": o.fare_product,
            "baggage_profile": o.baggage_profile,
            "taxes_fees_included": o.taxes_fees_included,
            "discount_club": o.discount_club,
            "airline": f.airline,
            "scheduled_departure_local": f.scheduled_departure_local.isoformat() if f.scheduled_departure_local else "",
            "scheduled_arrival_local": f.scheduled_arrival_local.isoformat() if f.scheduled_arrival_local else "",
            "source_url": o.source_url or "",
            "booking_url": o.booking_url or "",
            "notes": o.notes or "",
            "source": o.source,
            "verification": o.verification,
            "original_price": str(from_minor(o.original_price_minor)),
            "original_currency": o.original_currency,
            "fx_rate": o.fx_rate or "",
            "fx_source": o.fx_source or "",
            "profile_assumed": o.profile_assumed,
            "is_demo": o.is_demo,
            "lead_time_days": lead_time_days(f.flight_date, o.captured_at_utc, f.origin_tz),
        })
    return buf.getvalue()
