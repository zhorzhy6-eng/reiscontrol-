"""Trip transition use cases."""

from datetime import datetime
from uuid import UUID

from backend.application.errors import ForbiddenError, NotFoundError
from backend.application.ports import (
    ConfigSnapshotRepository,
    TripCompletionPolicy,
    TripRepository,
    UserRepository,
)
from backend.domain.errors import InvalidTransitionError
from backend.domain.trips import Trip, complete_trip, start_trip


def start_trip_for_user(
    trip_id: UUID,
    *,
    user_id: UUID,
    started_at: datetime,
    trips: TripRepository,
    users: UserRepository,
    snapshots: ConfigSnapshotRepository,
) -> Trip:
    """Start a trip after checking its participant or scope."""
    trip = _authorized_trip(trip_id, user_id, trips, users)
    if trip.status != "assigned":
        raise InvalidTransitionError("Only an assigned trip can start")
    snapshot_id = snapshots.freeze_for_trip(trip)
    started = start_trip(trip, started_at=started_at, config_snapshot_id=snapshot_id)
    trips.save(started)
    return started


def complete_trip_for_user(
    trip_id: UUID,
    *,
    user_id: UUID,
    track_number: str,
    trips: TripRepository,
    users: UserRepository,
    policy: TripCompletionPolicy,
) -> Trip:
    """Submit an authorized trip for logistician confirmation."""
    trip = _authorized_trip(trip_id, user_id, trips, users)
    completed = complete_trip(trip, track_number=track_number)
    policy.validate(completed)
    trips.save(completed)
    return completed


def _authorized_trip(
    trip_id: UUID, user_id: UUID, trips: TripRepository, users: UserRepository
) -> Trip:
    if not users.can_operate_trip(user_id, trip_id):
        raise ForbiddenError("Trip access denied")
    trip = trips.get(trip_id)
    if trip is None:
        raise NotFoundError("Trip not found")
    return trip
