"""Periodic location-track persistence with consent and trip checks."""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from backend.application.errors import IdempotencyConflictError
from backend.domain.errors import DomainError
from backend.infrastructure.postgres import models as db
from backend.infrastructure.postgres.repositories import _has_current_consent


class PostgresTrackRepository:
    """Append location points only for a live, consenting trip participant."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def append_batch(
        self, *, user_id: UUID, device_id: UUID, tracks: list[dict], can_operate_trip
    ) -> None:
        """Append new samples; acknowledge exact retries without creating rows."""
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            for track in tracks:
                key = (track["client_track_id"], device_id)
                existing = (
                    session.execute(
                        select(db.location_tracks).where(
                            db.location_tracks.c.client_track_id == key[0],
                            db.location_tracks.c.device_id == key[1],
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is not None:
                    _check_retry(existing, track, user_id)
                    continue
                if not _has_current_consent(session, user_id, "tracking"):
                    raise DomainError("Tracking consent is required")
                trip_id = track.get("trip_id")
                if trip_id is None or not can_operate_trip(user_id, trip_id):
                    raise DomainError("Tracking is allowed only during an assigned trip")
                trip_status = session.execute(
                    select(db.trips.c.status).where(db.trips.c.id == trip_id)
                ).scalar_one_or_none()
                if trip_status != "in_progress":
                    raise DomainError("Tracking is allowed only during an active trip")
                row = {
                    "id": uuid4(),
                    "client_track_id": key[0],
                    "device_id": device_id,
                    "user_id": user_id,
                    "trip_id": trip_id,
                    "lat": track["lat"],
                    "lon": track["lon"],
                    "accuracy_m": track["accuracy_m"],
                    "speed_mps": track.get("speed_mps"),
                    "bearing_deg": track.get("bearing_deg"),
                    "location_source": track["location_source"],
                    "recorded_at": track["recorded_at"],
                    "received_at": now,
                }
                inserted = session.execute(
                    insert(db.location_tracks)
                    .values(**row)
                    .on_conflict_do_nothing(index_elements=["client_track_id", "device_id"])
                    .returning(db.location_tracks.c.id)
                ).scalar_one_or_none()
                if inserted is None:
                    winner = (
                        session.execute(
                            select(db.location_tracks).where(
                                db.location_tracks.c.client_track_id == key[0],
                                db.location_tracks.c.device_id == key[1],
                            )
                        )
                        .mappings()
                        .one()
                    )
                    _check_retry(winner, track, user_id)

    def for_trip(
        self, trip_id: UUID, *, from_at: datetime | None = None, to_at: datetime | None = None
    ) -> list[dict]:
        """Return a trip's recorded track points ordered by event time."""
        query = select(db.location_tracks).where(db.location_tracks.c.trip_id == trip_id)
        if from_at is not None:
            query = query.where(db.location_tracks.c.recorded_at >= from_at)
        if to_at is not None:
            query = query.where(db.location_tracks.c.recorded_at <= to_at)
        with self.sessions() as session:
            rows = (
                session.execute(query.order_by(db.location_tracks.c.recorded_at)).mappings().all()
            )
            return [dict(row) for row in rows]


def _check_retry(existing: dict, track: dict, user_id: UUID) -> None:
    """Reject reuse of a client key for a different immutable location fact."""
    fields = ("trip_id", "recorded_at", "accuracy_m", "location_source")
    if existing["user_id"] != user_id or any(existing[field] != track[field] for field in fields):
        raise IdempotencyConflictError("client_track_id already belongs to another track")
    for field in ("lat", "lon", "speed_mps", "bearing_deg"):
        incoming = track.get(field)
        stored = existing[field]
        if incoming is None or stored is None:
            if incoming is not None or stored is not None:
                raise IdempotencyConflictError("client_track_id already belongs to another track")
        elif field in ("lat", "lon") and Decimal(str(incoming)).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        ) != Decimal(str(stored)):
            raise IdempotencyConflictError("client_track_id already belongs to another track")
        elif field in ("speed_mps", "bearing_deg") and Decimal(str(incoming)) != Decimal(
            str(stored)
        ):
            raise IdempotencyConflictError("client_track_id already belongs to another track")
