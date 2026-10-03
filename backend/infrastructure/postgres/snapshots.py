"""Freeze published checklist data for a trip before its first event."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from backend.domain.errors import DomainError
from backend.domain.trips import Trip
from backend.infrastructure.postgres import models as db
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker


def build_snapshot(
    *,
    trip_id: UUID,
    version_id: UUID,
    configs: dict,
    event_types: list[dict],
    steps: list[dict],
) -> dict:
    """Copy event types, primitive settings and per-event steps into immutable JSON."""
    by_type: dict[str, list[dict]] = {}
    for step in steps:
        by_type.setdefault(step["event_type_code"], []).append(
            {
                key: step[key]
                for key in ("code", "type", "title", "required", "order", "scope", "hint_icon")
            }
        )
    types = []
    for event_type in event_types:
        code = event_type["code"]
        extra = dict(configs.get(code, {}))
        if event_type["primitive"] == "photo_set" and not by_type.get(code):
            raise DomainError("Published photo checklist has no steps")
        types.append(
            {
                "code": code,
                "primitive": event_type["primitive"],
                "title": event_type["title"],
                "min_app_version": event_type["min_app_version"],
                **extra,
                "steps": by_type.get(code, []),
            }
        )
    return {"trip_id": str(trip_id), "version_id": str(version_id), "event_types": types}


class PostgresConfigSnapshotRepository:
    """Select the latest matching published template and persist one trip snapshot."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def freeze_for_trip(self, trip: Trip) -> UUID:
        """Create once by trip ID; a retry reads the same immutable snapshot."""
        with self.sessions.begin() as session:
            existing = session.execute(
                select(db.config_snapshots.c.id).where(db.config_snapshots.c.trip_id == trip.id)
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            order = session.execute(
                select(
                    db.orders.c.client_id,
                    db.orders.c.cargo_type_code,
                    db.orders.c.trip_type_code,
                ).where(db.orders.c.id == trip.order_id)
            ).one_or_none()
            if order is None:
                raise DomainError("Trip order is unavailable")
            version = (
                session.execute(
                    select(db.checklist_versions)
                    .select_from(
                        db.checklist_versions.join(
                            db.checklist_templates,
                            db.checklist_versions.c.template_id == db.checklist_templates.c.id,
                        )
                    )
                    .where(
                        db.checklist_templates.c.client_id == order.client_id,
                        db.checklist_templates.c.cargo_type_code == order.cargo_type_code,
                        db.checklist_templates.c.trip_type_code == order.trip_type_code,
                        db.checklist_templates.c.is_active,
                        db.checklist_versions.c.status == "published",
                    )
                    .order_by(db.checklist_versions.c.version.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if version is None:
                raise DomainError("Published checklist is unavailable for this trip")
            type_rows = (
                session.execute(
                    select(db.event_types)
                    .where(db.event_types.c.is_active)
                    .order_by(db.event_types.c.order)
                )
                .mappings()
                .all()
            )
            step_rows = (
                session.execute(
                    select(db.checklist_steps)
                    .where(db.checklist_steps.c.version_id == version["id"])
                    .order_by(db.checklist_steps.c.event_type_code, db.checklist_steps.c.order)
                )
                .mappings()
                .all()
            )
            snapshot = build_snapshot(
                trip_id=trip.id,
                version_id=version["id"],
                configs=version["primitive_configs_jsonb"],
                event_types=[dict(row) for row in type_rows],
                steps=[dict(row) for row in step_rows],
            )
            snapshot_id = uuid4()
            result = session.execute(
                pg_insert(db.config_snapshots)
                .values(
                    id=snapshot_id,
                    trip_id=trip.id,
                    version_id=version["id"],
                    snapshot_json=snapshot,
                    created_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=["trip_id"])
                .returning(db.config_snapshots.c.id)
            ).scalar_one_or_none()
            if result is not None:
                return result
            return session.execute(
                select(db.config_snapshots.c.id).where(db.config_snapshots.c.trip_id == trip.id)
            ).scalar_one()
