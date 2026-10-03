"""Stage 0 contract-file checks; endpoint behavior comes later."""

import json
from pathlib import Path

import yaml

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
