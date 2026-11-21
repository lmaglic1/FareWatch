"""ManualEntryProvider: fares I personally saw, with source URL and timestamp."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import FlightIdentity, Source, Verification
from ..schemas import ManualObservationIn
from ..services.observations import RecordResult, record_observation


class ManualEntryProvider:
    name = Source.MANUAL.value
    configured = True

    def record(self, db: Session, data: ManualObservationIn, display_currency: str) -> RecordResult:
        flight = db.get(FlightIdentity, data.flight_id)
        if flight is None:
            raise LookupError(f"Flight {data.flight_id} not found")
        return record_observation(
            db,
            flight=flight,
            price_total=data.price_total,
            currency=data.currency,
            source=self.name,
            verification=Verification.USER_VERIFIED.value,
            display_currency=display_currency,
            captured_at_utc=data.captured_at_utc,
            passengers=data.passengers,
            fare_product=data.fare_product,
            baggage_profile=data.baggage_profile,
            taxes_fees_included=data.taxes_fees_included,
            discount_club=data.discount_club,
            source_url=str(data.source_url) if data.source_url else None,
            booking_url=str(data.booking_url) if data.booking_url else None,
            fx_rate=data.fx_rate_to_display,
            fx_source=data.fx_source,
            notes=data.notes,
        )
