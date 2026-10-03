"""Approved stage-1 configuration is data, not client code."""

from pathlib import Path

import yaml
from jsonschema import Draft7Validator

from backend.infrastructure.postgres.seed import load_seed_data


def test_approved_stage1_event_types_and_photo_steps():
    records = load_seed_data()
    assert {(record["code"], record["primitive"]) for record in records} == {
        ("LOADING", "photo_set"),
        ("UNLOADING", "photo_set"),
        ("ARRIVAL", "geo_only"),
        ("DEPARTURE", "geo_only"),
        ("PARKING", "geo_only"),
    }
    config = yaml.safe_load(Path("config/checklists/stage1.yaml").read_text(encoding="utf-8"))
    assert [step["code"] for step in config["event_types"]["LOADING"]["steps"]] == [
        "front_3_4",
        "rear_3_4",
        "vin_plate",
    ]
    assert [step["code"] for step in config["event_types"]["UNLOADING"]["steps"]] == [
        "front_3_4",
        "rear_3_4",
    ]


def test_versioned_payload_schemas_are_valid_json_schema():
    import json

    for path in Path("docs/06-schemas/event-payload").glob("*-v1.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
