"""Descriptive price statistics and a rule-based (heuristic) status.

Nothing here is a forecast. The status compares the latest comparable quote
with the median of previously recorded comparable quotes using a user-defined
threshold. It does not and cannot guarantee that a price will not fall later.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import FlightIdentity, PriceObservation
from ..money import from_minor, quantize
from .features import LEAD_BUCKETS, feature_row, lead_time_days
from .observations import ProfileKey, observations_for

INSUFFICIENT = "INSUFFICIENT DATA"
ATTRACTIVE = "ATTRACTIVE PRICE"
NORMAL = "NORMAL RANGE"
EXPENSIVE = "EXPENSIVE RELATIVE TO HISTORY"

HEURISTIC_NOTE = (
    "User-defined heuristic: compares the latest quote with the median of recorded comparable "
    "quotes. It is not a buy/wait forecast and cannot guarantee the lowest price."
)


def _pct(a: Decimal, b: Decimal) -> Decimal:
    return quantize((a - b) / b * 100)


def compute_stats(
    points: list[tuple[datetime, Decimal]],
    *,
    flight_date,
    origin_tz: str,
    threshold_pct: Decimal,
    min_samples: int,
    drop_pct: Decimal,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Statistics for one flight + one comparable fare profile.

    ``points`` are (captured_at_utc, price) pairs; they are sorted here.
    """
    now = now or utcnow()
    pts = sorted(points, key=lambda p: p[0])
    today_local = now.astimezone(ZoneInfo(origin_tz)).date()
    days_to_departure = (flight_date - today_local).days
    out: dict[str, Any] = {
        "count": len(pts),
        "days_to_departure": days_to_departure,
        "min": None, "max": None, "median": None, "mean": None,
        "latest": None, "latest_at": None, "previous": None,
        "pct_change_vs_previous": None,
        "median_7d": None, "median_7d_count": 0, "median_7d_note": None,
        "latest_rank": None, "latest_percentile": None,
        "volatility_stdev": None, "volatility_cv_pct": None,
        "drop_detected": False,
        "best": None, "best_at": None,
        "latest_vs_median_pct": None,
        "status": INSUFFICIENT,
        "status_reason": "",
        "threshold_pct": str(threshold_pct),
        "min_samples": min_samples,
        "heuristic_note": HEURISTIC_NOTE,
    }
    if not pts:
        out["status_reason"] = "No comparable quotes recorded yet."
        return out

    prices = [p for _, p in pts]
    latest_at, latest = pts[-1]
    best_at, best = min(pts, key=lambda p: (p[1], p[0]))
    out.update(
        min=min(prices), max=max(prices), median=quantize(statistics.median(prices)),
        mean=quantize(sum(prices, Decimal("0")) / len(prices)),
        latest=latest, latest_at=latest_at, best=best, best_at=best_at,
    )
    if len(pts) >= 2:
        prev = pts[-2][1]
        out["previous"] = prev
        out["pct_change_vs_previous"] = _pct(latest, prev)
        out["drop_detected"] = out["pct_change_vs_previous"] <= -drop_pct

    window = [p for t, p in pts if t >= now - timedelta(days=7)]
    out["median_7d_count"] = len(window)
    if len(window) >= 3:
        out["median_7d"] = quantize(statistics.median(window))
    else:
        out["median_7d_note"] = f"Needs at least 3 quotes in the last 7 days (have {len(window)})."

    cheaper = sum(1 for p in prices if p < latest)
    out["latest_rank"] = cheaper + 1  # 1 = cheapest recorded
    out["latest_percentile"] = quantize(Decimal(cheaper) / len(prices) * 100)

    if len(prices) >= 3:
        sd = statistics.stdev(prices)
        out["volatility_stdev"] = quantize(sd)
        mean = sum(prices, Decimal("0")) / len(prices)
        out["volatility_cv_pct"] = quantize(sd / mean * 100) if mean else None

    # Status: compare latest with median of the history *before* it, so the
    # latest quote does not pull the reference towards itself.
    history = prices[:-1]
    if len(prices) < min_samples:
        out["status_reason"] = (
            f"Only {len(prices)} comparable quote(s) recorded; at least {min_samples} are needed "
            "before comparing against history. Keep collecting before drawing conclusions."
        )
        return out
    ref = statistics.median(history)
    diff = _pct(latest, ref)
    out["latest_vs_median_pct"] = diff
    if diff <= -threshold_pct:
        out["status"] = ATTRACTIVE
        out["status_reason"] = (
            f"Latest quote is {abs(diff)}% below the median of {len(history)} earlier comparable quotes "
            f"(threshold {threshold_pct}%)."
        )
    elif diff >= threshold_pct:
        out["status"] = EXPENSIVE
        out["status_reason"] = (
            f"Latest quote is {diff}% above the median of {len(history)} earlier comparable quotes "
            f"(threshold {threshold_pct}%)."
        )
    else:
        out["status"] = NORMAL
        out["status_reason"] = (
            f"Latest quote is within ±{threshold_pct}% of the median of {len(history)} earlier "
            f"comparable quotes ({diff:+}%)."
        )
    return out


def _preferred(key: ProfileKey, prefs: dict[str, Any]) -> bool:
    return (
        key.currency == prefs["display_currency"]
        and key.passengers == int(prefs["passengers"])
        and key.baggage_profile == prefs["baggage_profile"]
        and key.discount_club == prefs["discount_club"]
    )


def group_by_profile(obs: list[PriceObservation]) -> dict[ProfileKey, list[PriceObservation]]:
    groups: dict[ProfileKey, list[PriceObservation]] = defaultdict(list)
    for o in obs:
        groups[ProfileKey.of(o)].append(o)
    return groups


def analyze_flight(
    db: Session, flight: FlightIdentity, prefs: dict[str, Any], *, demo: bool, now: datetime | None = None
) -> dict[str, Any]:
    """Exact-flight analysis, split by comparable fare profile."""
    obs = observations_for(db, flight_id=flight.id, demo=demo)
    groups = group_by_profile(obs)
    threshold = Decimal(str(prefs["median_threshold_pct"]))
    min_samples = int(prefs["min_samples_for_status"])
    drop = Decimal(str(prefs["drop_alert_pct"]))

    profiles = []
    for key, items in groups.items():
        stats = compute_stats(
            [(o.captured_at_utc, from_minor(o.price_total_minor)) for o in items],
            flight_date=flight.flight_date, origin_tz=flight.origin_tz,
            threshold_pct=threshold, min_samples=min_samples, drop_pct=drop, now=now,
        )
        latest = items[-1]
        profiles.append({
            "profile": asdict(key),
            "profile_label": key.label(),
            "matches_preferences": _preferred(key, prefs),
            "is_member_fare": key.discount_club == "member",
            "stats": stats,
            "latest_source": latest.source,
            "latest_verification": latest.verification,
            "latest_profile_assumed": latest.profile_assumed,
            "sources": sorted({o.source for o in items}),
        })
    profiles.sort(key=lambda p: (not p["matches_preferences"], -p["stats"]["count"]))
    primary = profiles[0] if profiles and profiles[0]["matches_preferences"] else None
    last_any = max((o.captured_at_utc for o in obs), default=None)
    return {
        "flight_id": flight.id,
        "total_quotes": len(obs),
        "last_valid_quote_at": last_any,
        "primary": primary,
        "profiles": profiles,
        "note": (
            None if primary else
            "No quotes match your preferred comparison profile (currency, passengers, baggage, "
            "Discount Club status). Other profiles are shown separately and are not mixed."
        ),
    }


def combine_legs(out_profile: dict | None, ret_profile: dict | None) -> dict[str, Any]:
    """Sum of separately observed one-way legs, only when profiles are compatible."""
    if not out_profile or not ret_profile:
        return {"available": False, "reasons": ["Both legs need at least one quote in your preferred profile."]}
    a, b = out_profile["profile"], ret_profile["profile"]
    reasons = [
        f"{k.replace('_', ' ')} differs ({a[k]} vs {b[k]})" for k in a if a[k] != b[k]
    ]
    for side, p in (("outbound", a), ("return", b)):
        if p["baggage_profile"] == "unknown":
            reasons.append(f"{side} baggage profile is unknown")
        if p["taxes_fees_included"] == "no":
            reasons.append(f"{side} price excludes taxes/fees")
    if reasons:
        return {"available": False, "reasons": reasons}
    sa, sb = out_profile["stats"], ret_profile["stats"]
    return {
        "available": True,
        "reasons": [],
        "currency": a["currency"],
        "latest_total": quantize(sa["latest"] + sb["latest"]),
        "best_total": quantize(sa["best"] + sb["best"]),
        "outbound_latest_at": sa["latest_at"],
        "return_latest_at": sb["latest_at"],
        "note": (
            "Sum of two separately observed one-way quotes with identical fare assumptions, captured "
            "at different times. Not a bookable round-trip price; re-check both legs before buying."
        ),
    }


def cross_flight_analysis(
    db: Session, prefs: dict[str, Any], *, demo: bool, origin: str | None = None, destination: str | None = None
) -> dict[str, Any]:
    """Cross-flight comparison by lead time. Kept separate from exact-flight history."""
    rows = []
    for o in observations_for(db, demo=demo):
        f = o.flight
        if origin and f.origin != origin.upper():
            continue
        if destination and f.destination != destination.upper():
            continue
        key = ProfileKey.of(o)
        feat = feature_row(f.flight_date, o.captured_at_utc, f.origin_tz)
        rows.append({
            "observation_id": o.id,
            "flight_id": f.id,
            "flight_number": f.flight_number,
            "airline": f.airline,
            "origin": f.origin,
            "destination": f.destination,
            "flight_date": f.flight_date,
            "is_target": f.is_target,
            "captured_at_utc": o.captured_at_utc,
            "price_total": from_minor(o.price_total_minor),
            "currency": o.currency,
            "source": o.source,
            "verification": o.verification,
            "matches_preferences": _preferred(key, prefs),
            "profile_label": key.label(),
            "discount_club": o.discount_club,
            **feat,
        })
    comparable = [r for r in rows if r["matches_preferences"] and r["lead_time_days"] >= 0]
    buckets = []
    for b in LEAD_BUCKETS:
        vals = [r["price_total"] for r in comparable if r["lead_time_bucket"] == b]
        buckets.append({
            "bucket": b,
            "count": len(vals),
            "median": quantize(statistics.median(vals)) if vals else None,
            "flights": len({r["flight_id"] for r in comparable if r["lead_time_bucket"] == b}),
        })
    return {
        "rows": rows,
        "lead_time_buckets": buckets,
        "note": (
            "Cross-flight view. Different flights, dates and lead times are not directly comparable: a "
            "flight departing tomorrow is priced under different conditions than a holiday flight six weeks "
            "away. Bucket medians mix flights and only describe what was recorded."
        ),
    }


def lead_time_for(o: PriceObservation) -> int:
    return lead_time_days(o.flight.flight_date, o.captured_at_utc, o.flight.origin_tz)
