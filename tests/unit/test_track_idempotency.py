"""Track identity must be stable across retries."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects.postgresql import dialect, insert

from backend.application.errors import IdempotencyConflictError
from backend.infrastructure.postgres.models import location_tracks
from backend.infrastructure.postgres.tracks import _check_retry


def test_track_retry_accepts_same_fact_and_rejects_changed_fact():
    user_id = uuid4()
    fact = {
        "trip_id": uuid4(),
        "recorded_at": datetime.now(timezone.utc),
        "lat": 55.75,
        "lon": 37.62,
        "accuracy_m": 10,
        "speed_mps": None,
        "bearing_deg": None,
        "location_source": "platform",
    }
    stored = {
        **fact,
        "user_id": user_id,
        "lat": Decimal("55.750000"),
        "lon": Decimal("37.620000"),
    }
    _check_retry(stored, fact, user_id)
    with pytest.raises(IdempotencyConflictError):
        _check_retry(stored, {**fact, "lat": 55.76}, user_id)


def test_track_insert_uses_unique_client_device_conflict_key():
    assert any(
        index.unique
        and [column.name for column in index.columns] == ["client_track_id", "device_id"]
        for index in location_tracks.indexes
    )
    statement = insert(location_tracks).values(
        id=uuid4(), client_track_id=UUID(int=1), device_id=UUID(int=2)
    )
    sql = str(
        statement.on_conflict_do_nothing(index_elements=["client_track_id", "device_id"]).compile(
            dialect=dialect()
        )
    )
    assert "ON CONFLICT (client_track_id, device_id) DO NOTHING" in sql
