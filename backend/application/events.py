"""Event submission use cases."""

import logging
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from backend.application.errors import (
    ForbiddenError,
    IdempotencyConflictError,
    NotFoundError,
)
from backend.application.ports import (
    EventConfiguration,
    EventRepository,
    StoredEvent,
    TripRepository,
    UserRepository,
)
from backend.domain.events import Event, accept_event, transition_event

logger = logging.getLogger(__name__)


def submit_event(
    event: Event,
    *,
    user_id: UUID,
    received_at_utc: datetime,
    trace_id: str,
    events: EventRepository,
    trips: TripRepository,
    users: UserRepository,
    configuration: EventConfiguration,
) -> StoredEvent:
    """Accept a completed client fact exactly once and enqueue its notification atomically."""
    if not users.can_access_trip(user_id, event.trip_id):
        raise ForbiddenError("Trip access denied")
    trip = trips.get(event.trip_id)
    if trip is None:
        raise NotFoundError("Trip not found")
    if trip.status != "in_progress":
        raise ValueError("Trip is not in progress")
    configuration.validate(event, trip.config_snapshot_id)
    prior = events.get_by_client_key(event.client_event_id, event.device_id)
    if prior is not None:
        if _fingerprint(prior.event) != _fingerprint(event):
            raise IdempotencyConflictError("Client event key was reused")
        return prior
    if event.state != "complete":
        raise ValueError("Only complete client events can be submitted")
    queued = transition_event(event, "queued")
    uploaded = transition_event(queued, "uploaded")
    accepted = accept_event(uploaded, received_at_utc=received_at_utc)
    stored = events.save_once_with_notification(accepted)
    if _fingerprint(stored.event) != _fingerprint(event):
        raise IdempotencyConflictError("Client event key was reused")
    logger.info(
        "Event accepted",
        extra={
            "trace_id": trace_id,
            "user_id": str(user_id),
            "trip_id": str(event.trip_id),
            "event_id": str(stored.id),
            "context": {"event_type_code": event.event_type_code},
        },
    )
    return stored


def _fingerprint(event: Event) -> Event:
    """Compare client facts without transport and server-generated fields."""
    return replace(
        event,
        state="draft",
        server_time_utc=None,
        received_at_utc=None,
        clock_skew_ms=None,
        time_trust="unknown",
        rejection_reason=None,
    )
