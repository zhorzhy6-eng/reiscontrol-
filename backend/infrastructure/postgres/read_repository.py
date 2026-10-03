"""Scoped read projections for the mobile and web clients."""

from datetime import datetime, timezone
from uuid import UUID

from backend.infrastructure.postgres import models as db
from backend.infrastructure.postgres.repositories import _has_current_consent
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker


class PostgresReadRepository:
    """Read orders, trip details and event timeline without N+1 queries."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def orders_for_user(self, user_id: UUID) -> list[dict]:
        """List driver trips or logistician-scoped client orders."""
        with self.sessions() as session:
            role = session.execute(
                select(db.users.c.role).where(db.users.c.id == user_id, db.users.c.is_active)
            ).scalar_one_or_none()
            base = (
                select(
                    db.orders.c.id,
                    db.orders.c.status,
                    db.orders.c.created_at,
                    db.orders.c.cargo_type_code,
                    db.clients.c.name.label("client_name"),
                    db.trips.c.id.label("trip_id"),
                )
                .select_from(
                    db.orders.join(db.clients, db.orders.c.client_id == db.clients.c.id).join(
                        db.trips, db.trips.c.order_id == db.orders.c.id
                    )
                )
                .order_by(db.orders.c.created_at.desc())
            )
            if role == "driver":
                if not _has_current_consent(session, user_id, "pd"):
                    return []
                now = datetime.now(timezone.utc)
                base = base.join(
                    db.trip_participants,
                    db.trip_participants.c.trip_id == db.trips.c.id,
                ).where(
                    db.trip_participants.c.user_id == user_id,
                    db.trip_participants.c.from_at <= now,
                    or_(
                        db.trip_participants.c.to_at.is_(None),
                        db.trip_participants.c.to_at > now,
                    ),
                )
            elif role == "logistician":
                base = base.join(
                    db.access_scopes,
                    and_(
                        db.access_scopes.c.user_id == user_id,
                        or_(
                            and_(
                                db.access_scopes.c.scope_type == "client",
                                db.access_scopes.c.scope_id
                                == db.orders.c.client_id.cast(db.access_scopes.c.scope_id.type),
                            ),
                            and_(
                                db.access_scopes.c.scope_type == "trip",
                                db.access_scopes.c.scope_id
                                == db.trips.c.id.cast(db.access_scopes.c.scope_id.type),
                            ),
                        ),
                    ),
                )
            elif role != "admin":
                return []
            rows = session.execute(base.distinct()).mappings().all()
            return [dict(row) for row in rows]

    def trip(self, trip_id: UUID) -> dict | None:
        """Read a trip and its points/cargo in three bounded queries."""
        with self.sessions() as session:
            row = (
                session.execute(select(db.trips).where(db.trips.c.id == trip_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            points = (
                session.execute(
                    select(db.trip_points)
                    .where(db.trip_points.c.trip_id == trip_id)
                    .order_by(db.trip_points.c.order_index)
                )
                .mappings()
                .all()
            )
            cargo = (
                session.execute(
                    select(db.cargo_units)
                    .where(db.cargo_units.c.trip_id == trip_id)
                    .order_by(db.cargo_units.c.order_index)
                )
                .mappings()
                .all()
            )
            return {
                **dict(row),
                "points": [dict(point) for point in points],
                "cargo_units": [dict(unit) for unit in cargo],
            }

    def trips_for_user(self, user_id: UUID) -> list[dict]:
        """Return current scoped trip projections in a bounded number of queries."""
        trip_ids = [order["trip_id"] for order in self.orders_for_user(user_id)]
        if not trip_ids:
            return []
        with self.sessions() as session:
            rows = (
                session.execute(select(db.trips).where(db.trips.c.id.in_(trip_ids)))
                .mappings()
                .all()
            )
            return [dict(row) for row in rows]

    def config_snapshot(self, snapshot_id: UUID) -> dict | None:
        """Read a frozen configuration document."""
        with self.sessions() as session:
            row = session.execute(
                select(db.config_snapshots.c.snapshot_json).where(
                    db.config_snapshots.c.id == snapshot_id
                )
            ).scalar_one_or_none()
            return row

    def events_for_trip(self, trip_id: UUID) -> list[dict]:
        """Read accepted facts and attachment metadata for a trip timeline."""
        with self.sessions() as session:
            events = (
                session.execute(
                    select(db.events)
                    .where(db.events.c.trip_id == trip_id, db.events.c.state == "accepted")
                    .order_by(db.events.c.created_at)
                )
                .mappings()
                .all()
            )
            client_ids = [row["client_event_id"] for row in events]
            attachments = (
                session.execute(
                    select(
                        db.attachments.c.id,
                        db.attachments.c.owner_id,
                        db.attachments.c.kind,
                        db.attachments.c.source,
                        db.attachments.c.state,
                    ).where(
                        db.attachments.c.owner_type == "event",
                        db.attachments.c.owner_id.in_(client_ids),
                    )
                )
                .mappings()
                .all()
                if client_ids
                else []
            )
            by_owner: dict[UUID, list[dict]] = {}
            for attachment in attachments:
                by_owner.setdefault(attachment["owner_id"], []).append(dict(attachment))
            timeline = []
            for row in events:
                fact = dict(row)
                fact["payload"] = fact.pop("payload_jsonb")
                fact["attachments"] = by_owner.get(row["client_event_id"], [])
                timeline.append(fact)
            return timeline

    def latest_release(self, platform: str, channel: str) -> dict | None:
        """Read the latest release for the requested platform and channel."""
        with self.sessions() as session:
            row = (
                session.execute(
                    select(db.app_releases)
                    .where(
                        db.app_releases.c.platform == platform,
                        db.app_releases.c.channel == channel,
                    )
                    .order_by(db.app_releases.c.version_code.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            return dict(row) if row else None
