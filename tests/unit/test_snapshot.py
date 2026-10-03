"""Published config is copied into a trip-specific immutable payload."""

from uuid import uuid4

import pytest

from backend.domain.errors import DomainError
from backend.infrastructure.postgres.snapshots import build_snapshot


def test_snapshot_copies_steps_and_primitive_settings_by_event_type():
    trip_id, version_id = uuid4(), uuid4()
    snapshot = build_snapshot(
        trip_id=trip_id,
        version_id=version_id,
        configs={"LOADING": {"scope": "per_cargo_unit", "camera": {"allow_gallery": True}}},
        event_types=[
            {
                "code": "LOADING",
                "primitive": "photo_set",
                "title": "Погрузка",
                "min_app_version": 1,
            },
            {"code": "ARRIVAL", "primitive": "geo_only", "title": "Прибытие", "min_app_version": 1},
        ],
        steps=[
            {
                "event_type_code": "LOADING",
                "code": "front_3_4",
                "type": "photo",
                "title": "Спереди слева",
                "required": True,
                "order": 1,
                "scope": "per_cargo_unit",
                "hint_icon": None,
            }
        ],
    )
    assert snapshot["trip_id"] == str(trip_id)
    assert snapshot["version_id"] == str(version_id)
    assert snapshot["event_types"][0]["steps"][0]["code"] == "front_3_4"
    assert snapshot["event_types"][0]["camera"]["allow_gallery"]
    assert snapshot["event_types"][1]["steps"] == []


def test_photo_primitive_cannot_be_published_without_steps():
    with pytest.raises(DomainError):
        build_snapshot(
            trip_id=uuid4(),
            version_id=uuid4(),
            configs={},
            event_types=[
                {
                    "code": "LOADING",
                    "primitive": "photo_set",
                    "title": "Погрузка",
                    "min_app_version": 1,
                }
            ],
            steps=[],
        )
