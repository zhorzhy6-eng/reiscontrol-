"""PostgreSQL authentication adapter."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from backend.application.auth import AuthUser
from backend.infrastructure.postgres import models as db


class PostgresAuthRepository:
    """Persist device-bound refresh tokens and load users for authentication."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def get_by_phone(self, phone: str) -> AuthUser | None:
        """Find an account without logging the phone number."""
        with self.sessions() as session:
            row = (
                session.execute(
                    select(db.users, db.driver_profiles.c.full_name)
                    .select_from(
                        db.users.outerjoin(
                            db.driver_profiles, db.users.c.id == db.driver_profiles.c.user_id
                        )
                    )
                    .where(db.users.c.phone == phone)
                )
                .mappings()
                .one_or_none()
            )
            return _auth_user(row) if row else None

    def get_by_id(self, user_id: UUID) -> AuthUser | None:
        """Find an account by stable ID."""
        with self.sessions() as session:
            row = (
                session.execute(
                    select(db.users, db.driver_profiles.c.full_name)
                    .select_from(
                        db.users.outerjoin(
                            db.driver_profiles, db.users.c.id == db.driver_profiles.c.user_id
                        )
                    )
                    .where(db.users.c.id == user_id)
                )
                .mappings()
                .one_or_none()
            )
            return _auth_user(row) if row else None

    def register_device(
        self, user_id: UUID, device_id: UUID, platform: str, app_version: str
    ) -> None:
        """Register or update a device without allowing a different owner."""
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            statement = pg_insert(db.devices).values(
                id=device_id,
                user_id=user_id,
                platform=platform,
                app_version=app_version,
                last_seen_at=now,
                created_at=now,
            )
            result = session.execute(
                statement.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "platform": platform,
                        "app_version": app_version,
                        "last_seen_at": now,
                    },
                    where=db.devices.c.user_id == user_id,
                )
            )
            if result.rowcount == 0:
                raise PermissionError("Device belongs to another user")

    def save_refresh(
        self, user_id: UUID, device_id: UUID, token_hash: str, expires_at: datetime
    ) -> None:
        """Store only a refresh-token hash."""
        with self.sessions.begin() as session:
            session.execute(
                insert(db.refresh_tokens).values(
                    id=uuid4(),
                    user_id=user_id,
                    device_id=device_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    revoked_at=None,
                )
            )

    def find_refresh_user(self, token_hash: str, now: datetime) -> tuple[UUID, UUID] | None:
        """Find the active owner and bound device of a live refresh token."""
        with self.sessions() as session:
            row = session.execute(
                select(db.refresh_tokens.c.user_id, db.refresh_tokens.c.device_id)
                .select_from(
                    db.refresh_tokens.join(
                        db.devices, db.refresh_tokens.c.device_id == db.devices.c.id
                    )
                )
                .where(
                    db.refresh_tokens.c.token_hash == token_hash,
                    db.refresh_tokens.c.expires_at > now,
                    db.refresh_tokens.c.revoked_at.is_(None),
                    db.devices.c.user_id == db.refresh_tokens.c.user_id,
                )
            ).one_or_none()
            return (row.user_id, row.device_id) if row else None


def _auth_user(row) -> AuthUser:
    return AuthUser(
        id=row["id"],
        phone=row["phone"],
        password_hash=row["password_hash"],
        role=row["role"],
        is_active=row["is_active"],
        full_name=row["full_name"],
    )
