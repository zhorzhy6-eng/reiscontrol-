"""Mandatory event coverage follows the frozen trip checklist."""

from uuid import uuid4

from backend.infrastructure.postgres.completion import missing_event_requirements


def test_each_cargo_unit_needs_each_mandatory_photo_event():
    first, second = uuid4(), uuid4()
    snapshot = {
        "event_types": [
            {
                "code": "LOADING",
                "scope": "per_cargo_unit",
                "steps": [{"code": "front_3_4", "required": True}],
            },
            {
                "code": "UNLOADING",
                "scope": "per_cargo_unit",
                "steps": [{"code": "rear_3_4", "required": True}],
            },
            {"code": "ARRIVAL", "steps": []},
        ]
    }
    accepted = {("LOADING", first), ("LOADING", second), ("UNLOADING", first)}
    assert missing_event_requirements(snapshot, [first, second], accepted) == (
        f"UNLOADING:{second}",
    )
