"""Application configuration loaded from environment variables / .env.

Secrets (API keys, SMTP passwords) are only ever read from the environment and
are never returned by any API endpoint.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Storage ---------------------------------------------------------
    database_url: str = Field(
        default=f"sqlite:///{(BACKEND_DIR / 'data' / 'farewatch.db').as_posix()}"
    )

    # --- General ---------------------------------------------------------
    app_timezone: str = "Europe/Sarajevo"
    home_airport: str = "SJJ"
    default_currency: str = "EUR"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"
    demo_mode: bool = False  # initial value; can be toggled at runtime in Settings

    # --- SerpApi (optional) ---------------------------------------------
    serpapi_api_key: str = ""
    serpapi_base_url: str = "https://serpapi.com"
    serpapi_hl: str = "en"
    serpapi_gl: str = ""
    serpapi_timeout_seconds: float = 25.0
    serpapi_max_retries: int = 2
    serpapi_monthly_quota: int = 250
    serpapi_deep_search: bool = False
    # Profile assumed for Google Flights fares. Google Flights generally shows
    # the cheapest public fare including taxes; for Wizz Air that is the basic
    # fare with one free under-seat bag. This is stored as an *assumption*.
    serpapi_assumed_fare_product: str = "basic"
    serpapi_assumed_baggage_profile: str = "under_seat_only"

    # --- Collector --------------------------------------------------------
    collector_enabled: bool = False
    collector_times: str = "08:00,20:00"  # local times in app_timezone
    max_queries_per_day: int = 15
    min_minutes_between_checks: int = 120
    collector_include_comparisons: bool = True
    comparison_window_start: str = "2026-11-01"
    comparison_window_end: str = "2027-01-31"

    # --- Analysis -----------------------------------------------------------
    median_threshold_pct: Decimal = Decimal("15")
    min_samples_for_status: int = 5
    drop_alert_pct: Decimal = Decimal("10")

    # --- Email alerts (optional) -----------------------------------------
    alert_email_enabled: bool = False
    alert_email_to: str = ""
    alert_email_from: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    @field_validator("default_currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 3 or not v.isalpha():
            raise ValueError("default_currency must be an ISO-4217 code like EUR")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def collector_time_list(self) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for part in self.collector_times.split(","):
            part = part.strip()
            if not part:
                continue
            hh, mm = part.split(":")
            out.append((int(hh), int(mm)))
        return out

    @property
    def serpapi_configured(self) -> bool:
        return bool(self.serpapi_api_key.strip())

    @property
    def email_configured(self) -> bool:
        return bool(
            self.alert_email_enabled
            and self.alert_email_to
            and self.alert_email_from
            and self.smtp_host
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
