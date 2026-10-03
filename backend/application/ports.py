"""Ports implemented by infrastructure adapters."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.domain.events import Event
from backend.domain.trips import Trip


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """Persisted event identity and accepted fact."""

    id: UUID
    event: Event


class EventRepository(Protocol):
    """Atomic event journal and notification outbox boundary."""

    def get_by_client_key(self, client_event_id: UUID, device_id: UUID) -> StoredEvent | None:
        """Find a prior submission by the documented compound key."""

    def save_once_with_notification(
        self, event: Event, *, user_id: UUID, app_version: str, platform: str
    ) -> StoredEvent:
        """Insert accepted event and outbox row in one transaction, returning a duplicate."""


class TripRepository(Protocol):
    """Trip projection boundary."""

    def get(self, trip_id: UUID) -> Trip | None:
        """Load a trip."""

    def save(self, trip: Trip) -> None:
        """Persist a valid trip transition."""


class ConfigSnapshotRepository(Protocol):
    """Freeze published configuration when a trip starts."""

    def freeze_for_trip(self, trip: Trip) -> UUID:
        """Create an immutable snapshot and return its ID."""


class UserRepository(Protocol):
    """User lookup and authorization boundary."""

    def can_access_trip(self, user_id: UUID, trip_id: UUID) -> bool:
        """Enforce participants, scoped logisticians, and administrators."""

    def can_operate_trip(self, user_id: UUID, trip_id: UUID) -> bool:
        """Allow active drivers with current personal-data and geo consents."""


class EventConfiguration(Protocol):
    """Snapshot-driven event validation boundary."""

    def validate(self, event: Event, config_snapshot_id: UUID) -> None:
        """Validate event type, payload and stored attachments against the trip snapshot."""


class TripCompletionPolicy(Protocol):
    """Snapshot-driven completion policy boundary."""

    def validate(self, trip: Trip) -> None:
        """Require all configured photos, documents and completion rules."""
