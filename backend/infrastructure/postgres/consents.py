"""Current user consent records and idempotent acceptance."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from backend.infrastructure.postgres import models as db
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker


class PostgresConsentRepository:
    """Read and accept explicit personal-data, geo and tracking consents."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def list_for_user(self, user_id: UUID) -> list[dict]:
        """Return recorded consents without exposing IP addresses to clients."""
        with self.sessions() as session:
            rows = (
                session.execute(
                    select(
                        db.user_consents.c.consent_type,
                        db.user_consents.c.policy_version,
                        db.user_consents.c.accepted_at,
                        db.user_consents.c.revoked_at,
                    )
                    .where(db.user_consents.c.user_id == user_id)
                    .order_by(db.user_consents.c.accepted_at.desc())
                )
                .mappings()
                .all()
            )
            return [dict(row) for row in rows]

    def accept(
        self,
        *,
        user_id: UUID,
        consent_type: str,
        policy_version: str,
        platform: str,
        ip: str,
    ) -> dict:
        """Accept a policy version once, allowing reacceptance after revocation."""
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            statement = insert(db.user_consents).values(
                id=uuid4(),
                user_id=user_id,
                consent_type=consent_type,
                policy_version=policy_version,
                platform=platform,
                accepted_at=now,
                revoked_at=None,
                ip=ip,
            )
            session.execute(
                statement.on_conflict_do_nothing(
                    index_elements=["user_id", "consent_type", "policy_version"],
                    index_where=db.user_consents.c.revoked_at.is_(None),
                )
            )
            row = (
                session.execute(
                    select(
                        db.user_consents.c.consent_type,
                        db.user_consents.c.policy_version,
                        db.user_consents.c.accepted_at,
                        db.user_consents.c.revoked_at,
                    )
                    .where(
                        db.user_consents.c.user_id == user_id,
                        db.user_consents.c.consent_type == consent_type,
                        db.user_consents.c.policy_version == policy_version,
                        db.user_consents.c.revoked_at.is_(None),
                    )
                    .order_by(db.user_consents.c.accepted_at.desc())
                    .limit(1)
                )
                .mappings()
                .one()
            )
            return dict(row)
