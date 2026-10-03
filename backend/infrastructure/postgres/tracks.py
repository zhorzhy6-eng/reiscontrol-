"""Periodic location-track persistence with consent and trip checks."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.orm import Session, sessionmaker

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
        """Persist a batch after checking tracking consent and each active trip."""
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            if not _has_current_consent(session, user_id, "tracking"):
                raise DomainError("Tracking consent is required")
            rows = []
            for track in tracks:
                trip_id = track.get("trip_id")
                if trip_id is None or not can_operate_trip(user_id, trip_id):
                    raise DomainError("Tracking is allowed only during an assigned trip")
                trip_status = session.execute(
                    select(db.trips.c.status).where(db.trips.c.id == trip_id)
                ).scalar_one_or_none()
                if trip_status != "in_progress":
                    raise DomainError("Tracking is allowed only during an active trip")
                rows.append(
                    {
                        "id": uuid4(),
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
                )
            if rows:
                session.execute(insert(db.location_tracks), rows)

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
