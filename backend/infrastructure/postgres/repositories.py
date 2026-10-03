"""PostgreSQL adapters for event acceptance, trips, access and configuration."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from backend.application.ports import StoredEvent
from backend.domain.errors import DomainError, InvalidTransitionError
from backend.domain.events import Event, validate_payload_v1
from backend.domain.trips import Trip
from backend.infrastructure.postgres import models as db
from jsonschema import ValidationError, validate
from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker


class PostgresEventRepository:
    """Store accepted facts and notification jobs in a single transaction."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def get_by_client_key(self, client_event_id: UUID, device_id: UUID) -> StoredEvent | None:
        """Read an already accepted event by its idempotency key."""
        with self.sessions() as session:
            row = (
                session.execute(
                    select(db.events).where(
                        db.events.c.client_event_id == client_event_id,
                        db.events.c.device_id == device_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            return _stored_event(row) if row is not None else None

    def save_once_with_notification(
        self, event: Event, *, user_id: UUID, app_version: str, platform: str
    ) -> StoredEvent:
        """Insert the event and outbox row atomically; return a concurrent duplicate."""
        now = event.received_at_utc or datetime.now(timezone.utc)
        event_id = uuid4()
        values = {
            "id": event_id,
            "client_event_id": event.client_event_id,
            "device_id": event.device_id,
            "trip_id": event.trip_id,
            "point_id": event.point_id,
            "cargo_unit_id": event.cargo_unit_id,
            "event_type_code": event.event_type_code,
            "payload_jsonb": event.payload,
            "payload_schema_version": event.payload_schema_version,
            "device_time_utc": event.device_time_utc,
            "device_tz_offset_min": event.device_tz_offset_min,
            "elapsed_realtime_ms": event.elapsed_realtime_ms,
            "server_time_utc": event.server_time_utc or now,
            "clock_skew_ms": event.clock_skew_ms,
            "time_trust": event.time_trust,
            "lat": event.lat,
            "lon": event.lon,
            "accuracy_m": event.accuracy_m,
            "location_source": event.location_source,
            "state": event.state,
            "corrects_event_id": event.corrects_event_id,
            "created_by": user_id,
            "app_version": app_version,
            "platform": platform,
            "created_at": now,
        }
        with self.sessions.begin() as session:
            result = session.execute(
                pg_insert(db.events)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["client_event_id", "device_id"])
                .returning(db.events.c.id)
            ).scalar_one_or_none()
            if result is not None:
                session.execute(
                    insert(db.outbox).values(
                        id=uuid4(),
                        event_id=event_id,
                        payload={"event_id": str(event_id)},
                        status="pending",
                        retries=0,
                        next_attempt_at=now,
                        created_at=now,
                    )
                )
                return StoredEvent(event_id, event)
            row = (
                session.execute(
                    select(db.events).where(
                        db.events.c.client_event_id == event.client_event_id,
                        db.events.c.device_id == event.device_id,
                    )
                )
                .mappings()
                .one()
            )
            return _stored_event(row)


class PostgresTripRepository:
    """Read and update trip projections."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def get(self, trip_id: UUID) -> Trip | None:
        """Return one trip."""
        with self.sessions() as session:
            row = (
                session.execute(select(db.trips).where(db.trips.c.id == trip_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return Trip(
                id=row["id"],
                order_id=row["order_id"],
                config_snapshot_id=row["config_snapshot_id"],
                status=row["status"],
                started_at=row["started_at"],
                closed_at=row["closed_at"],
                track_number=row["track_number"],
            )

    def save(self, trip: Trip) -> None:
        """Persist an authorized trip state change."""
        previous_status = {
            "in_progress": "assigned",
            "pending_logistician": "in_progress",
        }.get(trip.status)
        if previous_status is None:
            raise InvalidTransitionError("Unsupported trip persistence transition")
        with self.sessions.begin() as session:
            result = session.execute(
                update(db.trips)
                .where(db.trips.c.id == trip.id, db.trips.c.status == previous_status)
                .values(
                    status=trip.status,
                    config_snapshot_id=trip.config_snapshot_id,
                    started_at=trip.started_at,
                    closed_at=trip.closed_at,
                    track_number=trip.track_number,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            if result.rowcount != 1:
                raise InvalidTransitionError("Trip changed concurrently")


class PostgresUserRepository:
    """Enforce participant and logistician client-scope access."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def can_access_trip(self, user_id: UUID, trip_id: UUID) -> bool:
        """Check active user, direct participation, and documented roles."""
        with self.sessions() as session:
            user = session.execute(
                select(db.users.c.role).where(db.users.c.id == user_id, db.users.c.is_active)
            ).scalar_one_or_none()
            if user is None:
                return False
            if user == "admin":
                return True
            if user == "driver":
                if not _has_current_consent(session, user_id, "pd"):
                    return False
                now = datetime.now(timezone.utc)
                return (
                    session.execute(
                        select(db.trip_participants.c.id).where(
                            db.trip_participants.c.user_id == user_id,
                            db.trip_participants.c.trip_id == trip_id,
                            db.trip_participants.c.from_at <= now,
                            or_(
                                db.trip_participants.c.to_at.is_(None),
                                db.trip_participants.c.to_at > now,
                            ),
                        )
                    )
                    .scalars()
                    .first()
                    is not None
                )
            if user == "logistician":
                client_id = session.execute(
                    select(db.orders.c.client_id)
                    .select_from(db.trips.join(db.orders, db.trips.c.order_id == db.orders.c.id))
                    .where(db.trips.c.id == trip_id)
                ).scalar_one_or_none()
                if client_id is None:
                    return False
                return (
                    session.execute(
                        select(db.access_scopes.c.id).where(
                            db.access_scopes.c.user_id == user_id,
                            (
                                and_(
                                    db.access_scopes.c.scope_type == "client",
                                    db.access_scopes.c.scope_id == str(client_id),
                                )
                                | and_(
                                    db.access_scopes.c.scope_type == "trip",
                                    db.access_scopes.c.scope_id == str(trip_id),
                                )
                            ),
                        )
                    )
                    .scalars()
                    .first()
                    is not None
                )
            return False

    def can_operate_trip(self, user_id: UUID, trip_id: UUID) -> bool:
        """Require driver role, trip participation, and current geo consent."""
        with self.sessions() as session:
            role = session.execute(
                select(db.users.c.role).where(db.users.c.id == user_id, db.users.c.is_active)
            ).scalar_one_or_none()
            return bool(
                role == "driver"
                and self.can_access_trip(user_id, trip_id)
                and _has_current_consent(session, user_id, "geo")
            )


class PostgresEventConfiguration:
    """Validate event facts against a fixed snapshot and attachment metadata."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def validate(self, event: Event, config_snapshot_id: UUID) -> None:
        """Reject unknown type, invalid payload or uncommitted/cross-event attachments."""
        with self.sessions() as session:
            snapshot = session.execute(
                select(db.config_snapshots.c.snapshot_json).where(
                    db.config_snapshots.c.id == config_snapshot_id
                )
            ).scalar_one_or_none()
            schema = session.execute(
                select(db.event_payload_schemas.c.json_schema).where(
                    db.event_payload_schemas.c.event_type_code == event.event_type_code,
                    db.event_payload_schemas.c.schema_version == event.payload_schema_version,
                )
            ).scalar_one_or_none()
            if snapshot is None or schema is None:
                raise DomainError("Event configuration is unavailable")
            event_config = next(
                (
                    entry
                    for entry in snapshot.get("event_types", [])
                    if entry.get("code") == event.event_type_code
                ),
                None,
            )
            if event_config is None:
                raise DomainError("Event type is not in the trip snapshot")
            event_type = event_config["primitive"]
            try:
                validate(instance=event.payload, schema=schema)
            except ValidationError as error:
                raise DomainError("Event payload does not match its versioned schema") from error
            config = dict(event_config)
            if event_type == "document_set" and "documents" not in config:
                config["documents"] = [
                    step for step in config.get("steps", []) if step.get("type") == "document"
                ]
            gallery_flag = session.execute(
                select(db.feature_flags.c.enabled).where(
                    db.feature_flags.c.code == "gallery_upload_enabled"
                )
            ).scalar_one_or_none()
            attachment_ids = validate_payload_v1(
                event_type,
                event.payload,
                config,
                gallery_enabled=gallery_flag is not False,
            )
            if event_config.get("scope") == "per_cargo_unit":
                if event.cargo_unit_id is None:
                    raise DomainError("Cargo unit is required for this event")
                cargo_trip_id = session.execute(
                    select(db.cargo_units.c.trip_id).where(
                        db.cargo_units.c.id == event.cargo_unit_id
                    )
                ).scalar_one_or_none()
                if cargo_trip_id != event.trip_id:
                    raise DomainError("Cargo unit does not belong to this trip")
            elif event_config.get("scope") == "per_trip" and event.cargo_unit_id is not None:
                raise DomainError("Cargo unit is not allowed for this event")
            if event_type == "geo_only":
                required_accuracy = event_config.get("require_accuracy_m")
                if required_accuracy is not None and (
                    event.accuracy_m is None or event.accuracy_m > int(required_accuracy)
                ):
                    raise DomainError("Location accuracy is insufficient")
                if str(event.point_id) != str(event.payload["point_id"]):
                    raise DomainError("Point ID does not match the event")
                point_trip_id = session.execute(
                    select(db.trip_points.c.trip_id).where(db.trip_points.c.id == event.point_id)
                ).scalar_one_or_none()
                if point_trip_id != event.trip_id:
                    raise DomainError("Point does not belong to this trip")
            if attachment_ids:
                rows = session.execute(
                    select(
                        db.attachments.c.id,
                        db.attachments.c.source,
                        db.attachments.c.kind,
                        db.attachments.c.watermark_meta,
                    ).where(
                        db.attachments.c.id.in_(attachment_ids),
                        db.attachments.c.owner_type == "event",
                        db.attachments.c.owner_id == event.client_event_id,
                        db.attachments.c.trip_id == event.trip_id,
                        db.attachments.c.state == "stored",
                    )
                ).all()
                if len(rows) != len(attachment_ids):
                    raise DomainError("Attachment is not stored for this event")
                sources = {row.id: row.source for row in rows}
                if event_type == "photo_set":
                    kinds = {row.id: row.kind for row in rows}
                    watermarks = {row.id: row.watermark_meta for row in rows}
                    for photo in event.payload["photos"]:
                        attachment_id = UUID(photo["attachment_id"])
                        if sources[attachment_id] != photo["source"]:
                            raise DomainError("Photo source does not match attachment")
                        if kinds[attachment_id] != "photo":
                            raise DomainError("Photo attachment has the wrong kind")
                        if event_config.get("camera", {}).get("watermark", True):
                            if not watermarks[attachment_id]:
                                raise DomainError("Photo watermark metadata is required")
                if event_type == "signature" and rows[0].kind != "signature":
                    raise DomainError("Signature attachment has the wrong kind")


def _has_current_consent(session: Session, user_id: UUID, consent_type: str) -> bool:
    """Check the latest consent version without exposing personal data to logs."""
    row = session.execute(
        select(db.user_consents.c.revoked_at, db.user_consents.c.id)
        .where(
            db.user_consents.c.user_id == user_id,
            db.user_consents.c.consent_type == consent_type,
        )
        .order_by(db.user_consents.c.accepted_at.desc())
        .limit(1)
    ).first()
    return row is not None and row.revoked_at is None


def _stored_event(row) -> StoredEvent:
    """Rebuild an accepted domain fact for idempotent replay."""
    return StoredEvent(
        id=row["id"],
        event=Event(
            client_event_id=row["client_event_id"],
            device_id=row["device_id"],
            trip_id=row["trip_id"],
            point_id=row["point_id"],
            cargo_unit_id=row["cargo_unit_id"],
            event_type_code=row["event_type_code"],
            payload=row["payload_jsonb"],
            payload_schema_version=row["payload_schema_version"],
            device_time_utc=row["device_time_utc"],
            device_tz_offset_min=row["device_tz_offset_min"],
            elapsed_realtime_ms=row["elapsed_realtime_ms"],
            lat=float(row["lat"]) if row["lat"] is not None else None,
            lon=float(row["lon"]) if row["lon"] is not None else None,
            accuracy_m=row["accuracy_m"],
            location_source=row["location_source"],
            state=row["state"],
            server_time_utc=row["server_time_utc"],
            received_at_utc=row["created_at"],
            clock_skew_ms=row["clock_skew_ms"],
            time_trust=row["time_trust"],
            corrects_event_id=row["corrects_event_id"],
        ),
    )
