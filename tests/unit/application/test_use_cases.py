"""Application orchestration and idempotency tests."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from backend.application.errors import ForbiddenError, IdempotencyConflictError
from backend.application.events import submit_event
from backend.application.ports import StoredEvent
from backend.application.trips import complete_trip_for_user, start_trip_for_user
from backend.domain.events import create_event, transition_event
from backend.domain.trips import Trip

NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
CLIENT_ID = UUID("0199c6d4-33ef-7c45-9bd2-6d443f8142e1")


class FakeUsers:
    allowed = True

    def can_access_trip(self, user_id, trip_id):
        return self.allowed


class FakeTrips:
    def __init__(self, status="in_progress"):
        self.trip = Trip(uuid4(), uuid4(), uuid4(), status)

    def get(self, trip_id):
        return self.trip if trip_id == self.trip.id else None

    def save(self, trip):
        self.trip = trip


class FakeConfig:
    def __init__(self):
        self.snapshot_id = None

    def validate(self, event, config_snapshot_id):
        self.snapshot_id = config_snapshot_id


class FakePolicy:
    def validate(self, trip):
        return None


class FakeEvents:
    def __init__(self):
        self.saved = None
        self.insert_count = 0

    def get_by_client_key(self, client_event_id, device_id):
        return self.saved

    def save_once_with_notification(self, event):
        self.insert_count += 1
        self.saved = StoredEvent(uuid4(), event)
        return self.saved


def client_event(trip_id):
    draft = create_event(
        client_event_id=CLIENT_ID,
        device_id=uuid4(),
        trip_id=trip_id,
        event_type_code="FROM_SNAPSHOT",
        payload={"value": "arrived"},
        payload_schema_version=1,
        device_time_utc=NOW,
        device_tz_offset_min=180,
        elapsed_realtime_ms=1,
    )
    return transition_event(draft, "complete")


def test_submit_event_is_idempotent_and_uses_trip_snapshot():
    trips = FakeTrips()
    users = FakeUsers()
    config = FakeConfig()
    events = FakeEvents()
    event = client_event(trips.trip.id)
    args = {
        "user_id": uuid4(),
        "received_at_utc": NOW,
        "trace_id": str(CLIENT_ID),
        "events": events,
        "trips": trips,
        "users": users,
        "configuration": config,
    }
    first = submit_event(event, **args)
    again = submit_event(event, **args)
    assert first == again
    assert events.insert_count == 1
    assert first.event.state == "accepted"
    assert config.snapshot_id == trips.trip.config_snapshot_id


def test_reused_client_key_with_different_payload_fails():
    trips, users, config, events = FakeTrips(), FakeUsers(), FakeConfig(), FakeEvents()
    event = client_event(trips.trip.id)
    args = {
        "user_id": uuid4(),
        "received_at_utc": NOW,
        "trace_id": str(CLIENT_ID),
        "events": events,
        "trips": trips,
        "users": users,
        "configuration": config,
    }
    submit_event(event, **args)
    changed = create_event(
        client_event_id=event.client_event_id,
        device_id=event.device_id,
        trip_id=event.trip_id,
        event_type_code=event.event_type_code,
        payload={"value": "different"},
        payload_schema_version=1,
        device_time_utc=NOW,
        device_tz_offset_min=180,
        elapsed_realtime_ms=1,
    )
    with pytest.raises(IdempotencyConflictError):
        submit_event(transition_event(changed, "complete"), **args)


def test_unauthorized_trip_cannot_accept_event():
    trips, users = FakeTrips(), FakeUsers()
    users.allowed = False
    with pytest.raises(ForbiddenError):
        submit_event(
            client_event(trips.trip.id),
            user_id=uuid4(),
            received_at_utc=NOW,
            trace_id=str(CLIENT_ID),
            events=FakeEvents(),
            trips=trips,
            users=users,
            configuration=FakeConfig(),
        )


def test_trip_use_cases_require_access_and_persist_transition():
    trips, users = FakeTrips(status="assigned"), FakeUsers()
    user_id = uuid4()
    started = start_trip_for_user(
        trips.trip.id, user_id=user_id, started_at=NOW, trips=trips, users=users
    )
    assert started.status == "in_progress"
    completed = complete_trip_for_user(
        trips.trip.id,
        user_id=user_id,
        track_number="T-123",
        trips=trips,
        users=users,
        policy=FakePolicy(),
    )
    assert completed.status == "pending_logistician"
    users.allowed = False
    with pytest.raises(ForbiddenError):
        complete_trip_for_user(
            trips.trip.id,
            user_id=user_id,
            track_number="T-123",
            trips=trips,
            users=users,
            policy=FakePolicy(),
        )
