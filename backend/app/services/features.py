"""Observation features: lead time, weekdays and holiday indicators.

These are *descriptive* attributes. They do not reveal passenger searches,
remaining seats or airline demand, which FareWatch cannot know.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Public holidays relevant to SJJ <-> Rome travel (fixed-date ones only; Easter
# is irrelevant for the Nov-Jan window). BiH has entity-level variations; the
# list below covers the dates that matter for this trip window.
_FIXED_HOLIDAYS: dict[tuple[int, int], str] = {
    (11, 1): "All Saints' Day (IT)",
    (11, 25): "Statehood Day (BiH, FBiH)",
    (12, 8): "Immaculate Conception (IT)",
    (12, 24): "Christmas Eve",
    (12, 25): "Christmas Day",
    (12, 26): "St. Stephen's Day (IT)",
    (12, 31): "New Year's Eve",
    (1, 1): "New Year's Day",
    (1, 2): "New Year holiday (BiH)",
    (1, 6): "Epiphany (IT)",
    (1, 7): "Orthodox Christmas",
}

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def holiday_name(d: date) -> str | None:
    return _FIXED_HOLIDAYS.get((d.month, d.day))


def is_holiday(d: date) -> bool:
    return holiday_name(d) is not None


def in_festive_window(d: date) -> bool:
    """Dec 20 - Jan 7: peak Christmas/New Year travel period."""
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 7)


def near_holiday(d: date, days: int = 2) -> bool:
    return any(is_holiday(d + timedelta(days=k)) for k in range(-days, days + 1))


def lead_time_days(flight_date: date, captured_at_utc: datetime, origin_tz: str) -> int:
    """Whole days between the observation (in origin local time) and departure date."""
    local = captured_at_utc.astimezone(ZoneInfo(origin_tz)).date()
    return (flight_date - local).days


def lead_time_bucket(days: int) -> str:
    if days < 0:
        return "departed"
    if days <= 7:
        return "0-7"
    if days <= 14:
        return "8-14"
    if days <= 30:
        return "15-30"
    if days <= 60:
        return "31-60"
    return "61+"


LEAD_BUCKETS = ["0-7", "8-14", "15-30", "31-60", "61+"]


def feature_row(flight_date: date, captured_at_utc: datetime, origin_tz: str) -> dict:
    lt = lead_time_days(flight_date, captured_at_utc, origin_tz)
    obs_local = captured_at_utc.astimezone(ZoneInfo(origin_tz))
    return {
        "lead_time_days": lt,
        "lead_time_bucket": lead_time_bucket(lt),
        "travel_weekday": WEEKDAYS[flight_date.weekday()],
        "observation_weekday": WEEKDAYS[obs_local.weekday()],
        "travel_is_holiday": is_holiday(flight_date),
        "travel_holiday_name": holiday_name(flight_date),
        "travel_near_holiday": near_holiday(flight_date),
        "travel_festive_window": in_festive_window(flight_date),
    }
