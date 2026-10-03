"""Idempotently load approved stage-1 configuration as database rows."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from backend.infrastructure.postgres import models as db
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def load_seed_data(root: Path = REPOSITORY_ROOT) -> list[dict]:
    """Read approved event type records without embedding them in code."""
    path = root / "config" / "event-types" / "stage1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["event_types"]


def seed_stage1(database_url: str, root: Path = REPOSITORY_ROOT) -> None:
    """Add approved event and attachment reference data idempotently."""
    engine = create_engine(database_url)
    with engine.begin() as connection:
        kind_data = yaml.safe_load(
            (root / "config" / "attachment-kinds" / "stage1.yaml").read_text(encoding="utf-8")
        )
        for kind in kind_data["kinds"]:
            connection.execute(
                insert(db.attachment_kinds)
                .values(**kind)
                .on_conflict_do_nothing(index_elements=["code"])
            )
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
        checklist_data = yaml.safe_load(
            (root / "config" / "checklists" / "stage1.yaml").read_text(encoding="utf-8")
        )["event_types"]
        primitive_configs = {
            event_code: {
                key: value for key, value in config.items() if key not in ("primitive", "steps")
            }
            for event_code, config in checklist_data.items()
        }
        order_contexts = connection.execute(
            select(
                db.orders.c.client_id,
                db.orders.c.cargo_type_code,
                db.orders.c.trip_type_code,
            ).distinct()
        ).all()
        for client_id, cargo_type_code, trip_type_code in order_contexts:
            existing = connection.execute(
                select(db.checklist_templates.c.id)
                .where(
                    db.checklist_templates.c.client_id == client_id,
                    db.checklist_templates.c.cargo_type_code == cargo_type_code,
                    db.checklist_templates.c.trip_type_code == trip_type_code,
                    db.checklist_templates.c.is_active,
                )
                .limit(1)
            ).scalar_one_or_none()
            if existing is not None:
                continue
            template_id, version_id = uuid4(), uuid4()
            now = datetime.now(timezone.utc)
            connection.execute(
                insert(db.checklist_templates).values(
                    id=template_id,
                    name="Этап 1",
                    cargo_type_code=cargo_type_code,
                    trip_type_code=trip_type_code,
                    client_id=client_id,
                    is_active=True,
                    created_at=now,
                )
            )
            connection.execute(
                insert(db.checklist_versions).values(
                    id=version_id,
                    template_id=template_id,
                    version=1,
                    status="published",
                    primitive_configs_jsonb=primitive_configs,
                    published_at=now,
                    published_by=None,
                )
            )
            for event_code, config in checklist_data.items():
                for step in config.get("steps", []):
                    connection.execute(
                        insert(db.checklist_steps).values(
                            id=uuid4(),
                            version_id=version_id,
                            event_type_code=event_code,
                            code=step["code"],
                            type=step["type"],
                            title=step["title"],
                            required=step["required"],
                            order=step["order"],
                            scope=step["scope"],
                            hint_icon=step.get("hint_icon"),
                        )
                    )
    engine.dispose()


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be set")
    seed_stage1(url)
