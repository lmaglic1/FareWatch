"""User-editable runtime preferences, persisted in the ``app_settings`` table.

Secrets and the master on/off switch for the collector stay in the environment.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from .config import get_settings
from .models import AppSetting


def _defaults() -> dict[str, Any]:
    s = get_settings()
    return {
        "demo_mode": s.demo_mode,
        "display_currency": s.default_currency,
        "baggage_profile": "under_seat_only",
        "discount_club": "public",
        "passengers": 1,
        "median_threshold_pct": str(s.median_threshold_pct),
        "min_samples_for_status": s.min_samples_for_status,
        "drop_alert_pct": str(s.drop_alert_pct),
        "collector_times": s.collector_times,
        "max_queries_per_day": s.max_queries_per_day,
        "min_minutes_between_checks": s.min_minutes_between_checks,
        "collector_include_comparisons": s.collector_include_comparisons,
    }


EDITABLE = set(_defaults().keys())


def get_all(db: Session) -> dict[str, Any]:
    values = _defaults()
    for row in db.query(AppSetting).all():
        if row.key in values:
            values[row.key] = json.loads(row.value)
    return values


def get(db: Session, key: str) -> Any:
    return get_all(db)[key]


def get_decimal(db: Session, key: str) -> Decimal:
    return Decimal(str(get(db, key)))


def update(db: Session, changes: dict[str, Any]) -> dict[str, Any]:
    for key, value in changes.items():
        if key not in EDITABLE:
            raise KeyError(key)
        row = db.get(AppSetting, key)
        encoded = json.dumps(value)
        if row:
            row.value = encoded
        else:
            db.add(AppSetting(key=key, value=encoded))
    db.commit()
    return get_all(db)
