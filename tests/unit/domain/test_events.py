"""Event lifecycle tests based on ADR-0002, 0004 and 0005."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from backend.domain.errors import DomainError, InvalidTransitionError
from backend.domain.events import (
    accept_event,
    create_event,
    reject_event,
    transition_event,
)

CLIENT_ID = UUID("0199c6d4-33ef-7c45-9bd2-6d443f8142e1")
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def draft():
    return create_event(
        client_event_id=CLIENT_ID,
        device_id=uuid4(),
        trip_id=uuid4(),
        event_type_code="FROM_CONFIG",
        payload={"steps": []},
        payload_schema_version=1,
        device_time_utc=NOW,
        device_tz_offset_min=180,
        elapsed_realtime_ms=1234,
    )


def uploaded():
    event = draft()
    for state in ("complete", "queued", "uploaded"):
        event = transition_event(event, state)
    return event


def test_create_event_requires_uuidv7():
    with pytest.raises(DomainError, match="UUIDv7"):
        create_event(
            client_event_id=uuid4(),
            device_id=uuid4(),
            trip_id=uuid4(),
            event_type_code="FROM_CONFIG",
            payload={},
            payload_schema_version=1,
            device_time_utc=NOW,
            device_tz_offset_min=180,
            elapsed_realtime_ms=1,
        )


def test_event_lifecycle_keeps_prior_versions_unchanged():
    original = draft()
    accepted = accept_event(uploaded(), received_at_utc=NOW + timedelta(seconds=10))
    assert original.state == "draft"
    assert accepted.state == "accepted"
    assert accepted.time_trust == "high"
    assert accepted.clock_skew_ms == 10_000
    with pytest.raises(InvalidTransitionError):
        transition_event(accepted, "draft")


def test_reject_requires_reason_and_can_return_to_draft():
    with pytest.raises(DomainError, match="reason"):
        reject_event(uploaded(), reason=" ", received_at_utc=NOW)
    rejected = reject_event(uploaded(), reason="invalid_photo", received_at_utc=NOW)
    assert rejected.rejection_reason == "invalid_photo"
    assert transition_event(rejected, "draft").state == "draft"


def test_large_clock_skew_is_flagged():
    accepted = accept_event(uploaded(), received_at_utc=NOW + timedelta(minutes=6))
    assert accepted.time_trust == "skewed"
