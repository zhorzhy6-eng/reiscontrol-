"""Trip state and completion rules tests."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.domain.checklists import missing_required_steps, validate_required_steps
from backend.domain.errors import (
    DomainError,
    IncompleteChecklistError,
    InvalidTransitionError,
)
from backend.domain.rules import unmet_completion_rules
from backend.domain.trips import Trip, complete_trip, start_trip


def assigned_trip():
    return Trip(
        id=uuid4(), order_id=uuid4(), config_snapshot_id=uuid4(), status="assigned"
    )


def test_trip_start_and_completion_keep_snapshot():
    original = assigned_trip()
    started = start_trip(original, started_at=datetime.now(timezone.utc))
    completed = complete_trip(started, track_number="  T-123  ")
    assert original.status == "assigned"
    assert completed.status == "pending_logistician"
    assert completed.track_number == "T-123"
    assert completed.config_snapshot_id == original.config_snapshot_id


def test_trip_cannot_complete_without_track_number():
    started = start_trip(assigned_trip(), started_at=datetime.now(timezone.utc))
    with pytest.raises(DomainError, match="track_number"):
        complete_trip(started, track_number=" ")
    with pytest.raises(InvalidTransitionError):
        start_trip(started, started_at=datetime.now(timezone.utc))


def test_required_steps_use_snapshot_order():
    steps = [
        {"code": "rear", "order": 2, "required": True},
        {"code": "optional", "order": 3, "required": False},
        {"code": "front", "order": 1, "required": True},
    ]
    assert missing_required_steps(steps, ["rear"]) == ("front",)
    with pytest.raises(IncompleteChecklistError) as error:
        validate_required_steps(steps, ["rear"])
    assert error.value.missing_steps == ("front",)


def test_completion_rules_follow_schema_values():
    rules = [
        {"rule": "all_required_steps_done"},
        {"rule": "min_photos", "count": 2},
        {"rule": "require_track_number"},
        {"rule": "require_signature"},
    ]
    assert unmet_completion_rules(
        rules,
        missing_steps=["front"],
        photo_count=1,
        track_number="",
        signature_present=False,
    ) == (
        "all_required_steps_done",
        "min_photos",
        "require_track_number",
        "require_signature",
    )
    assert not unmet_completion_rules(
        rules,
        missing_steps=[],
        photo_count=2,
        track_number="T-123",
        signature_present=True,
    )
