"""EXPERIMENTAL forecasting evaluation. Disabled until enough genuine data exists.

This module does not produce buy/wait advice. It evaluates whether a very
simple lead-time model beats a naive baseline on a *chronological* hold-out,
and reports MAE plus an error band. It never claims knowledge of airline
inventory or exact future prices.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from ..money import from_minor, quantize
from .features import lead_time_bucket, lead_time_days
from .observations import ProfileKey, observations_for

MIN_OBSERVATIONS = 40
MIN_SPAN_DAYS = 21
MIN_FLIGHTS = 2
TEST_FRACTION = Decimal("0.2")


def _quantile(sorted_vals: list[Decimal], q: float) -> Decimal:
    if not sorted_vals:
        return Decimal("0")
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def evaluate(db: Session) -> dict[str, Any]:
    obs = observations_for(db, demo=False)  # never train on demo fixtures
    # Use the most common comparable profile only.
    groups: dict[ProfileKey, list] = defaultdict(list)
    for o in obs:
        groups[ProfileKey.of(o)].append(o)
    if not groups:
        return _insufficient(0, 0, 0)
    key, rows = max(groups.items(), key=lambda kv: len(kv[1]))
    rows.sort(key=lambda o: o.captured_at_utc)
    span = (rows[-1].captured_at_utc - rows[0].captured_at_utc).days if rows else 0
    n_flights = len({o.flight_id for o in rows})
    if len(rows) < MIN_OBSERVATIONS or span < MIN_SPAN_DAYS or n_flights < MIN_FLIGHTS:
        return _insufficient(len(rows), span, n_flights)

    split = int(len(rows) * (1 - float(TEST_FRACTION)))
    train, test = rows[:split], rows[split:]
    cutoff = train[-1].captured_at_utc

    def lt(o) -> int:
        return lead_time_days(o.flight.flight_date, o.captured_at_utc, o.flight.origin_tz)

    bucket_prices: dict[tuple[str, str, str], list[Decimal]] = defaultdict(list)
    last_by_flight: dict[int, Decimal] = {}
    all_train = []
    for o in train:
        p = from_minor(o.price_total_minor)
        bucket_prices[(o.flight.origin, o.flight.destination, lead_time_bucket(lt(o)))].append(p)
        last_by_flight[o.flight_id] = p
        all_train.append(p)
    global_median = statistics.median(all_train)

    model_err, base_err = [], []
    for o in test:
        actual = from_minor(o.price_total_minor)
        bp = bucket_prices.get((o.flight.origin, o.flight.destination, lead_time_bucket(lt(o))))
        pred = statistics.median(bp) if bp else global_median
        base = last_by_flight.get(o.flight_id, global_median)  # naive: last known price before cutoff
        model_err.append(abs(actual - pred))
        base_err.append(abs(actual - base))
    mae_model = quantize(sum(model_err, Decimal(0)) / len(model_err))
    mae_base = quantize(sum(base_err, Decimal(0)) / len(base_err))
    errs = sorted(model_err)
    return {
        "status": "evaluated",
        "experimental": True,
        "profile": key.label(),
        "n_train": len(train),
        "n_test": len(test),
        "train_until_utc": cutoff,
        "test_from_utc": test[0].captured_at_utc,
        "mae_model": mae_model,
        "mae_baseline_last_price": mae_base,
        "model_beats_baseline": mae_model < mae_base,
        "abs_error_p10": quantize(_quantile(errs, 0.1)),
        "abs_error_p90": quantize(_quantile(errs, 0.9)),
        "method": (
            "Chronological split (first 80% train, last 20% test, no shuffling). Model: median train price "
            "for the same route and lead-time bucket. Baseline: last known train price of the same flight."
        ),
        "caveat": (
            "Experimental and descriptive. Errors on past data do not guarantee future accuracy. FareWatch "
            "cannot observe airline inventory, demand or pricing rules."
        ),
    }


def _insufficient(n: int, span: int, flights: int) -> dict[str, Any]:
    return {
        "status": "insufficient_data",
        "experimental": True,
        "requirements": {
            "observations": f"{n}/{MIN_OBSERVATIONS}",
            "span_days": f"{span}/{MIN_SPAN_DAYS}",
            "distinct_flights": f"{flights}/{MIN_FLIGHTS}",
        },
        "message": (
            "Forecast evaluation is disabled until enough genuine (non-demo) comparable observations exist. "
            "Use the descriptive statistics in the meantime."
        ),
    }
