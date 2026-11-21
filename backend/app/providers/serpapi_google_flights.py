"""SerpApi Google Flights adapter (optional, real data).

Implemented against the official documentation at https://serpapi.com/google-flights-api:

* ``GET https://serpapi.com/search`` with ``engine=google_flights``
* ``type=2`` (one way) so outbound and return legs are separate observations
* ``departure_id`` / ``arrival_id`` IATA codes, ``outbound_date`` YYYY-MM-DD
* ``travel_class=1`` (economy), ``adults``, ``currency``, ``hl``, ``gl``
* ``stops=1`` (nonstop only)
* Results live in ``best_flights`` and ``other_flights``. Each item has
  ``flights[]`` segments with ``departure_airport{id,time}``,
  ``arrival_airport{id,time}``, ``airline`` and ``flight_number`` (e.g. "W4 6160"),
  and an item-level ``price`` (number, may be absent).
* Times are local airport times formatted ``YYYY-MM-DD HH:MM``.
* ``price_insights.price_history`` is a list of ``[unix_timestamp, price]``
  pairs: Google's recorded lowest price for this exact search on past days.
* Account API ``GET https://serpapi.com/account.json`` (free) reports usage.

This adapter never scrapes Wizz Air and never fabricates results: if the
flight is missing or unpriced the result says so explicitly.
"""

from __future__ import annotations

import logging
import re
import time as _time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from ..config import Settings
from ..flights import normalize_flight_number
from ..money import to_decimal
from .base import LegCandidate, SearchResult

log = logging.getLogger("farewatch.serpapi")

PROVIDER_NAME = "serpapi_google_flights"
_KEY_RE = re.compile(r"(api_key=)[^&\s]+")


def redact(text: str) -> str:
    return _KEY_RE.sub(r"\1***", text)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def parse_candidates(payload: dict[str, Any], currency: str) -> list[LegCandidate]:
    """Extract nonstop single-segment options. Multi-segment items are ignored."""
    out: list[LegCandidate] = []
    for group in ("best_flights", "other_flights"):
        for item in payload.get(group) or []:
            segments = item.get("flights") or []
            if len(segments) != 1:
                continue  # we only track direct flights
            seg = segments[0]
            raw_fn = str(seg.get("flight_number") or "")
            try:
                fn = normalize_flight_number(raw_fn)
            except ValueError:
                continue
            dep = seg.get("departure_airport") or {}
            arr = seg.get("arrival_airport") or {}
            dep_t, arr_t = _parse_time(dep.get("time")), _parse_time(arr.get("time"))
            if not dep_t or not arr_t or not dep.get("id") or not arr.get("id"):
                continue
            price_raw = item.get("price")
            price: Decimal | None
            try:
                price = to_decimal(price_raw) if price_raw not in (None, "") else None
                if price is not None and price <= 0:
                    price = None
            except ValueError:
                price = None
            out.append(
                LegCandidate(
                    flight_number=fn,
                    airline=str(seg.get("airline") or fn[:2]),
                    origin=str(dep["id"]).upper(),
                    destination=str(arr["id"]).upper(),
                    departure_local=dep_t,
                    arrival_local=arr_t,
                    price=price,
                    currency=currency,
                    stops=len(item.get("layovers") or []),
                    raw_flight_number=raw_fn,
                )
            )
    return out


def parse_price_history(payload: dict[str, Any]) -> list[tuple[datetime, Decimal]]:
    """Parse ``price_insights.price_history`` -> [(UTC datetime, price)]. Malformed entries are skipped."""
    raw = (payload.get("price_insights") or {}).get("price_history") or []
    out: list[tuple[datetime, Decimal]] = []
    for entry in raw:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        ts, price = entry[0], entry[1]
        try:
            when = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            value = to_decimal(price)
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if value > 0:
            out.append((when, value))
    out.sort(key=lambda p: p[0])
    return out


def match_flight(
    candidates: list[LegCandidate],
    *,
    origin: str,
    destination: str,
    travel_date: date,
    flight_number: str,
) -> list[LegCandidate]:
    """Candidates matching route, local departure date, nonstop and flight number."""
    fn = normalize_flight_number(flight_number)
    return [
        c
        for c in candidates
        if c.flight_number == fn
        and c.origin == origin.upper()
        and c.destination == destination.upper()
        and c.departure_local.date() == travel_date
        and c.stops == 0
    ]


def _interpret(
    payload: dict[str, Any],
    *,
    origin: str,
    destination: str,
    travel_date: date,
    currency: str,
    expected_flight_number: str | None,
    queries_used: int,
    http_status: int | None,
) -> SearchResult:
    err = payload.get("error")
    if err:
        msg = redact(str(err))
        no_results = "hasn't returned any results" in msg.lower() or "no results" in msg.lower()
        return SearchResult(
            status="not_found" if no_results else "error",
            queries_used=queries_used, http_status=http_status, message=msg,
        )
    candidates = [
        c for c in parse_candidates(payload, currency)
        if c.origin == origin.upper() and c.destination == destination.upper()
        and c.departure_local.date() == travel_date
    ]
    if expected_flight_number is None:
        priced = [c for c in candidates if c.price is not None]
        return SearchResult(
            status="success" if priced else ("no_price" if candidates else "not_found"),
            queries_used=queries_used, candidates=candidates, http_status=http_status,
            message=f"{len(priced)} priced nonstop option(s) found" if priced else "No priced nonstop options",
        )
    matches = match_flight(
        candidates, origin=origin, destination=destination, travel_date=travel_date,
        flight_number=expected_flight_number,
    )
    if not matches:
        seen = ", ".join(sorted({c.flight_number for c in candidates})) or "none"
        return SearchResult(
            status="not_found", queries_used=queries_used, candidates=candidates, http_status=http_status,
            message=(
                f"{expected_flight_number} on {travel_date} {origin}->{destination} was not in the results "
                f"(nonstop flights seen: {seen}). It may not be on sale, not listed by Google Flights, or "
                "the schedule may have changed."
            ),
        )
    priced = [m for m in matches if m.price is not None]
    if not priced:
        return SearchResult(
            status="no_price", queries_used=queries_used, candidates=candidates, matched=matches[0],
            http_status=http_status, message=f"{expected_flight_number} was listed without a price.",
        )
    best = min(priced, key=lambda c: c.price)  # type: ignore[arg-type,return-value]
    return SearchResult(
        status="success", queries_used=queries_used, candidates=candidates, matched=best,
        http_status=http_status, message=f"Matched {expected_flight_number} at {best.price} {currency}",
    )


def interpret(payload: dict[str, Any], **kw: Any) -> SearchResult:
    """Turn a SerpApi JSON payload into a SearchResult (pure function, unit-tested).

    Non-error results also carry Google's price history for this exact search.
    """
    result = _interpret(payload, **kw)
    if result.status != "error":
        result.price_history = parse_price_history(payload)
    return result


class SerpApiGoogleFlightsProvider:
    name = PROVIDER_NAME

    def __init__(self, settings: Settings, client: httpx.Client | None = None, sleep=_time.sleep):
        self.settings = settings
        self._client = client
        self._sleep = sleep

    @property
    def configured(self) -> bool:
        return self.settings.serpapi_configured

    def _client_or_new(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=self.settings.serpapi_timeout_seconds)

    def build_params(
        self, *, origin: str, destination: str, travel_date: date, currency: str, adults: int
    ) -> dict[str, str]:
        p = {
            "engine": "google_flights",
            "type": "2",
            "departure_id": origin.upper(),
            "arrival_id": destination.upper(),
            "outbound_date": travel_date.isoformat(),
            "travel_class": "1",
            "adults": str(adults),
            "currency": currency.upper(),
            "hl": self.settings.serpapi_hl,
            "stops": "1",
            "api_key": self.settings.serpapi_api_key,
        }
        if self.settings.serpapi_gl:
            p["gl"] = self.settings.serpapi_gl
        if self.settings.serpapi_deep_search:
            p["deep_search"] = "true"
        return p

    def search_one_way(
        self,
        *,
        origin: str,
        destination: str,
        travel_date: date,
        currency: str,
        adults: int,
        expected_flight_number: str | None,
        max_attempts: int | None = None,
    ) -> SearchResult:
        """One-way search. ``max_attempts`` caps retries so the query budget is never exceeded."""
        if not self.configured:
            return SearchResult(status="error", queries_used=0, message="SERPAPI_API_KEY is not set")
        params = self.build_params(
            origin=origin, destination=destination, travel_date=travel_date, currency=currency, adults=adults
        )
        attempts = 0
        last_error = ""
        last_status: int | None = None
        limit = self.settings.serpapi_max_retries + 1
        if max_attempts is not None:
            limit = max(1, min(limit, max_attempts))
        client = self._client_or_new()
        try:
            for attempt in range(limit):
                attempts += 1
                try:
                    resp = client.get(f"{self.settings.serpapi_base_url}/search", params=params)
                except httpx.TransportError as exc:
                    last_error = f"Network error: {type(exc).__name__}"
                    log.warning("SerpApi transport error (attempt %d): %s", attempts, type(exc).__name__)
                else:
                    last_status = resp.status_code
                    if resp.status_code in (429,) or resp.status_code >= 500:
                        last_error = f"HTTP {resp.status_code}"
                    else:
                        try:
                            payload = resp.json()
                        except ValueError:
                            return SearchResult(
                                status="error", queries_used=attempts, http_status=resp.status_code,
                                message="Response was not valid JSON",
                            )
                        if resp.status_code >= 400 and not payload.get("error"):
                            payload = {"error": f"HTTP {resp.status_code}"}
                        return interpret(
                            payload, origin=origin, destination=destination, travel_date=travel_date,
                            currency=currency.upper(), expected_flight_number=expected_flight_number,
                            queries_used=attempts, http_status=resp.status_code,
                        )
                if attempt < limit - 1:
                    self._sleep(1.5 * (attempt + 1))
        finally:
            if self._client is None:
                client.close()
        return SearchResult(
            status="error", queries_used=attempts, http_status=last_status,
            message=redact(f"Gave up after {attempts} attempt(s): {last_error}"),
        )

    def account(self) -> dict[str, Any]:
        """SerpApi Account API (free, does not consume searches)."""
        if not self.configured:
            return {"ok": False, "message": "SERPAPI_API_KEY is not set"}
        client = self._client_or_new()
        try:
            resp = client.get(
                f"{self.settings.serpapi_base_url}/account.json",
                params={"api_key": self.settings.serpapi_api_key},
            )
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {"ok": False, "message": redact(f"Account check failed: {type(exc).__name__}")}
        finally:
            if self._client is None:
                client.close()
        if resp.status_code >= 400 or data.get("error"):
            return {"ok": False, "message": redact(str(data.get("error") or f"HTTP {resp.status_code}"))}
        keep = (
            "plan_name", "searches_per_month", "plan_searches_left", "total_searches_left",
            "this_month_usage", "this_hour_searches", "account_rate_limit_per_hour", "plan_renewal_date",
        )
        return {"ok": True, **{k: data.get(k) for k in keep}}
