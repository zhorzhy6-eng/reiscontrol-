"""Idempotently load approved stage-1 configuration as database rows."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml
from backend.infrastructure.postgres import models as db
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def load_seed_data(root: Path = REPOSITORY_ROOT) -> list[dict]:
    """Read approved event type records without embedding them in code."""
    path = root / "config" / "event-types" / "stage1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["event_types"]


def seed_stage1(database_url: str, root: Path = REPOSITORY_ROOT) -> None:
    """Add missing event types, payload schemas and the gallery feature flag."""
    engine = create_engine(database_url)
    with engine.begin() as connection:
        for record in load_seed_data(root):
            connection.execute(
                insert(db.event_types)
                .values(**record, is_active=True)
                .on_conflict_do_nothing(index_elements=["code"])
            )
            schema_path = (
                root / "docs" / "06-schemas" / "event-payload" / f"{record['primitive']}-v1.json"
            )
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            connection.execute(
                insert(db.event_payload_schemas)
                .values(
                    event_type_code=record["code"],
                    schema_version=1,
                    json_schema=schema,
                    created_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=["event_type_code", "schema_version"])
            )
        connection.execute(
            insert(db.feature_flags)
            .values(code="gallery_upload_enabled", enabled=True, rollout_percent=100)
            .on_conflict_do_nothing(index_elements=["code"])
        )
    engine.dispose()


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be set")
    seed_stage1(url)
