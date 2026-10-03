"""Immutable event facts and their local-to-server lifecycle."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from backend.domain.errors import DomainError, InvalidTransitionError

EventState = Literal["draft", "complete", "queued", "uploaded", "accepted", "rejected"]
TimeTrust = Literal["high", "skewed", "unknown"]


@dataclass(frozen=True, slots=True)
class Event:
    """One immutable version of an event; transitions return new values."""

    client_event_id: UUID
    device_id: UUID
    trip_id: UUID
    event_type_code: str
    payload: dict[str, Any]
    payload_schema_version: int
    device_time_utc: datetime | None
    device_tz_offset_min: int | None
    elapsed_realtime_ms: int | None
    point_id: UUID | None = None
    cargo_unit_id: UUID | None = None
    lat: float | None = None
    lon: float | None = None
    accuracy_m: int | None = None
    location_source: str | None = None
    state: EventState = "draft"
    server_time_utc: datetime | None = None
    received_at_utc: datetime | None = None
    clock_skew_ms: int | None = None
    time_trust: TimeTrust = "unknown"
    rejection_reason: str | None = None
    corrects_event_id: UUID | None = None


def create_event(
    *,
    client_event_id: UUID,
    device_id: UUID,
    trip_id: UUID,
    event_type_code: str,
    payload: dict[str, Any],
    payload_schema_version: int,
    device_time_utc: datetime | None,
    device_tz_offset_min: int | None,
    elapsed_realtime_ms: int | None,
    point_id: UUID | None = None,
    cargo_unit_id: UUID | None = None,
    lat: float | None = None,
    lon: float | None = None,
    accuracy_m: int | None = None,
    location_source: str | None = None,
    corrects_event_id: UUID | None = None,
) -> Event:
    """Create a recoverable local draft with a client-generated UUIDv7."""
    if client_event_id.version != 7:
        raise DomainError("client_event_id must be UUIDv7")
    if not event_type_code.strip():
        raise DomainError("event_type_code is required")
    if payload_schema_version < 1:
        raise DomainError("payload_schema_version must be positive")
    if device_time_utc is not None and device_time_utc.utcoffset() != timezone.utc.utcoffset(None):
        raise DomainError("device_time_utc must be UTC")
    if elapsed_realtime_ms is not None and elapsed_realtime_ms < 0:
        raise DomainError("elapsed_realtime_ms cannot be negative")
    if lat is not None and not -90 <= lat <= 90:
        raise DomainError("lat is out of range")
    if lon is not None and not -180 <= lon <= 180:
        raise DomainError("lon is out of range")
    if accuracy_m is not None and accuracy_m < 0:
        raise DomainError("accuracy_m cannot be negative")
    return Event(
        client_event_id=client_event_id,
        device_id=device_id,
        trip_id=trip_id,
        event_type_code=event_type_code,
        payload=dict(payload),
        payload_schema_version=payload_schema_version,
        device_time_utc=device_time_utc,
        device_tz_offset_min=device_tz_offset_min,
        elapsed_realtime_ms=elapsed_realtime_ms,
        point_id=point_id,
        cargo_unit_id=cargo_unit_id,
        lat=lat,
        lon=lon,
        accuracy_m=accuracy_m,
        location_source=location_source,
        corrects_event_id=corrects_event_id,
    )


def transition_event(event: Event, target: EventState) -> Event:
    """Advance the event through the states in ADR-0004."""
    next_states: dict[EventState, tuple[EventState, ...]] = {
        "draft": ("complete",),
        "complete": ("queued",),
        "queued": ("uploaded",),
        "uploaded": ("accepted", "rejected"),
        "accepted": (),
        "rejected": ("draft",),
    }
    if target not in next_states[event.state]:
        raise InvalidTransitionError(f"Cannot move event from {event.state} to {target}")
    return replace(event, state=target)


def accept_event(
    event: Event,
    *,
    received_at_utc: datetime,
    measured_clock_skew_ms: int | None = None,
) -> Event:
    """Accept a fact; trust remains unknown without an independent clock sample."""
    accepted = transition_event(event, "accepted")
    if received_at_utc.utcoffset() != timezone.utc.utcoffset(None):
        raise DomainError("received_at_utc must be UTC")
    trust: TimeTrust = "unknown"
    if measured_clock_skew_ms is not None:
        trust = "high" if abs(measured_clock_skew_ms) <= 300_000 else "skewed"
    return replace(
        accepted,
        server_time_utc=received_at_utc,
        received_at_utc=received_at_utc,
        clock_skew_ms=measured_clock_skew_ms,
        time_trust=trust,
    )


def reject_event(event: Event, *, reason: str, received_at_utc: datetime) -> Event:
    """Reject an uploaded fact with a reason suitable for the driver."""
    if not reason.strip():
        raise DomainError("rejection reason is required")
    rejected = transition_event(event, "rejected")
    return replace(rejected, rejection_reason=reason, received_at_utc=received_at_utc)
