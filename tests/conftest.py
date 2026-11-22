"""Test setup: isolated temporary SQLite DB, no API key, collector off."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="farewatch-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["SERPAPI_API_KEY"] = ""
os.environ["COLLECTOR_ENABLED"] = "false"
os.environ["DEMO_MODE"] = "false"
os.environ["ALERT_EMAIL_ENABLED"] = "false"
os.environ["MAX_QUERIES_PER_DAY"] = "6"
os.environ["HOME_AIRPORT"] = "SJJ"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.flights import seed_targets  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def db():
    from app import models  # noqa: F401

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    seed_targets(s)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(db):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def targets(db):
    from app.flights import target_flights

    out, ret = target_flights(db)
    return out, ret
