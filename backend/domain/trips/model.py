"""Trip state changes."""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal
from uuid import UUID

from backend.domain.errors import DomainError, InvalidTransitionError

TripStatus = Literal["assigned", "in_progress", "pending_logistician", "closed", "cancelled"]


@dataclass(frozen=True, slots=True)
class Trip:
    """A trip linked to its immutable configuration snapshot."""

    id: UUID
    order_id: UUID
    config_snapshot_id: UUID | None
    status: TripStatus
    started_at: datetime | None = None
    closed_at: datetime | None = None
    track_number: str | None = None


def start_trip(trip: Trip, *, started_at: datetime, config_snapshot_id: UUID) -> Trip:
    """Start an assigned trip and fix its configuration snapshot."""
    if trip.status != "assigned":
        raise InvalidTransitionError("Only an assigned trip can start")
    if trip.config_snapshot_id is not None:
        raise InvalidTransitionError("Assigned trip already has a configuration snapshot")
    return replace(
        trip, status="in_progress", started_at=started_at, config_snapshot_id=config_snapshot_id
    )


def complete_trip(trip: Trip, *, track_number: str) -> Trip:
    """Submit an in-progress trip for the logistician's confirmation."""
    if trip.status != "in_progress":
        raise InvalidTransitionError("Only an in-progress trip can be completed")
    if not track_number.strip():
        raise DomainError("track_number is required")
    return replace(trip, status="pending_logistician", track_number=track_number.strip())
