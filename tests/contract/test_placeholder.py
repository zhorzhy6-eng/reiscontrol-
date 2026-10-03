"""Stage 0 contract-file checks; endpoint behavior comes later."""

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def test_openapi_is_parseable() -> None:
    with (ROOT / "backend/contracts/openapi.yaml").open(encoding="utf-8") as stream:
        specification = yaml.safe_load(stream)
    assert specification["openapi"] == "3.0.3"
    assert specification["info"]["version"] == "1.1.0"
    assert specification["paths"]


def test_json_schemas_are_parseable() -> None:
    schema_dir = ROOT / "backend/contracts/schemas"
    schemas = sorted(schema_dir.glob("*.json"))
    assert len(schemas) == 8
    for path in schemas:
        with path.open(encoding="utf-8") as stream:
            schema = json.load(stream)
        assert schema["$schema"]
        assert schema["type"] == "object"


def test_working_openapi_copy_matches_backend_contract() -> None:
    """A mobile or web client must see the same contract as the backend."""
    assert (ROOT / "docs/05-api/openapi.yaml").read_bytes() == (
        ROOT / "backend/contracts/openapi.yaml"
    ).read_bytes()


def test_stage_one_attachment_requires_trip_scope() -> None:
    """The upload reservation needs the trip before an event exists."""
    contract = yaml.safe_load((ROOT / "docs/05-api/openapi.yaml").read_text(encoding="utf-8"))
    schema = contract["paths"]["/attachments:init"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert "trip_id" in schema["required"]


def test_approved_payload_schemas_are_valid_json_schema() -> None:
    for path in (ROOT / "docs/06-schemas/event-payload").glob("*-v1.json"):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))
