"""FareWatch FastAPI application entry point.

Run with:  uvicorn app.main:app --reload --port 8000   (from the backend/ folder)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.encoders import ENCODERS_BY_TYPE
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__, scheduler
from .config import get_settings
from .db import SessionLocal, init_db
from .flights import seed_targets
from .routers import alerts, dashboard, extras, flights, observations, system

# Money must never pass through binary floats: FastAPI's default encoder turns a
# bare Decimal into a float for plain-dict responses. Serialize it as an exact
# string instead (Pydantic models already do this).
ENCODERS_BY_TYPE[Decimal] = str

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("farewatch")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_targets(db)
    finally:
        db.close()
    scheduler.start()
    log.info("FareWatch %s ready. SerpApi configured: %s", __version__, settings.serpapi_configured)
    yield
    scheduler.shutdown()


app = FastAPI(title="FareWatch API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg", "")}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Validation failed", "errors": errors})


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "type": type(exc).__name__})


for r in (dashboard.router, flights.router, observations.router, alerts.router, extras.router, system.router):
    app.include_router(r)
