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
    corrects_event_id: UUID | None = None,
) -> Event:
    """Create a recoverable local draft with a client-generated UUIDv7."""
    if client_event_id.version != 7:
        raise DomainError("client_event_id must be UUIDv7")
    if not event_type_code.strip():
        raise DomainError("event_type_code is required")
    if payload_schema_version < 1:
        raise DomainError("payload_schema_version must be positive")
    if (
        device_time_utc is not None
        and device_time_utc.utcoffset() != timezone.utc.utcoffset(None)
    ):
        raise DomainError("device_time_utc must be UTC")
    if elapsed_realtime_ms is not None and elapsed_realtime_ms < 0:
        raise DomainError("elapsed_realtime_ms cannot be negative")
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
        raise InvalidTransitionError(
            f"Cannot move event from {event.state} to {target}"
        )
    return replace(event, state=target)


def accept_event(event: Event, *, received_at_utc: datetime) -> Event:
    """Accept an uploaded fact and record server and clock evidence."""
    accepted = transition_event(event, "accepted")
    if received_at_utc.utcoffset() != timezone.utc.utcoffset(None):
        raise DomainError("received_at_utc must be UTC")
    skew = None
    trust: TimeTrust = "unknown"
    if event.device_time_utc is not None:
        skew = round((received_at_utc - event.device_time_utc).total_seconds() * 1000)
        trust = "high" if abs(skew) <= 300_000 else "skewed"
    return replace(
        accepted,
        server_time_utc=received_at_utc,
        received_at_utc=received_at_utc,
        clock_skew_ms=skew,
        time_trust=trust,
    )


def reject_event(event: Event, *, reason: str, received_at_utc: datetime) -> Event:
    """Reject an uploaded fact with a reason suitable for the driver."""
    if not reason.strip():
        raise DomainError("rejection reason is required")
    rejected = transition_event(event, "rejected")
    return replace(rejected, rejection_reason=reason, received_at_utc=received_at_utc)
