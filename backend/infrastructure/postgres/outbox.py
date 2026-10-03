"""Retryable PostgreSQL outbox and scoped Telegram recipients."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from backend.infrastructure.postgres import models as db

LEASE_SECONDS = 60
MAX_RETRIES = 8


@dataclass(frozen=True, slots=True)
class OutboxJob:
    """Claimed notification job."""

    id: UUID
    event_id: UUID
    retries: int


class PostgresOutboxRepository:
    """Claim one job with SKIP LOCKED and track per-recipient delivery."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def claim_next(self) -> OutboxJob | None:
        """Acquire a due job; expired processing leases are retried."""
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            row = (
                session.execute(
                    select(db.outbox)
                    .where(
                        db.outbox.c.next_attempt_at <= now,
                        or_(db.outbox.c.status == "pending", db.outbox.c.status == "processing"),
                        db.outbox.c.retries < MAX_RETRIES,
                    )
                    .order_by(db.outbox.c.next_attempt_at, db.outbox.c.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            session.execute(
                update(db.outbox)
                .where(db.outbox.c.id == row["id"])
                .values(status="processing", next_attempt_at=now + timedelta(seconds=LEASE_SECONDS))
            )
            return OutboxJob(row["id"], row["event_id"], row["retries"])

    def event_context(self, event_id: UUID) -> dict | None:
        """Read event, its trip and client scope in one query."""
        with self.sessions() as session:
            row = (
                session.execute(
                    select(
                        db.events.c.id,
                        db.events.c.trip_id,
                        db.events.c.event_type_code,
                        db.events.c.device_time_utc,
                        db.events.c.lat,
                        db.events.c.lon,
                        db.events.c.state,
                        db.orders.c.client_id,
                    )
                    .select_from(
                        db.events.join(db.trips, db.events.c.trip_id == db.trips.c.id).join(
                            db.orders, db.trips.c.order_id == db.orders.c.id
                        )
                    )
                    .where(db.events.c.id == event_id)
                )
                .mappings()
                .one_or_none()
            )
            return dict(row) if row else None

    def recipients(self, trip_id: UUID, client_id: UUID) -> list[str]:
        """Resolve enabled subscriptions through active logistician RBAC scope."""
        with self.sessions() as session:
            rows = (
                session.execute(
                    select(db.telegram_subscriptions.c.chat_id)
                    .select_from(
                        db.telegram_subscriptions.join(
                            db.users, db.telegram_subscriptions.c.user_id == db.users.c.id
                        ).join(db.access_scopes, db.access_scopes.c.user_id == db.users.c.id)
                    )
                    .where(
                        db.telegram_subscriptions.c.enabled,
                        db.users.c.is_active,
                        db.users.c.role == "logistician",
                        or_(
                            and_(
                                db.access_scopes.c.scope_type == "client",
                                db.access_scopes.c.scope_id == str(client_id),
                            ),
                            and_(
                                db.access_scopes.c.scope_type == "trip",
                                db.access_scopes.c.scope_id == str(trip_id),
                            ),
                        ),
                    )
                    .distinct()
                )
                .scalars()
                .all()
            )
            return list(rows)

    def delivered(self, event_id: UUID, chat_id: str) -> bool:
        """Skip a recipient recorded as delivered by a prior retry."""
        with self.sessions() as session:
            return (
                session.execute(
                    select(db.notification_log.c.id).where(
                        db.notification_log.c.event_id == event_id,
                        db.notification_log.c.recipient == chat_id,
                        db.notification_log.c.status == "sent",
                    )
                ).scalar_one_or_none()
                is not None
            )

    def mark_delivered(self, event_id: UUID, chat_id: str) -> None:
        """Record one successful recipient delivery idempotently."""
        with self.sessions.begin() as session:
            session.execute(
                pg_insert(db.notification_log)
                .values(
                    id=uuid4(),
                    event_id=event_id,
                    template_code="event_accepted",
                    recipient=chat_id,
                    status="sent",
                    sent_at=datetime.now(timezone.utc),
                    error=None,
                )
                .on_conflict_do_nothing(index_elements=["event_id", "recipient"])
            )

    def mark_sent(self, job_id: UUID) -> None:
        """Close a completed outbox job."""
        with self.sessions.begin() as session:
            session.execute(update(db.outbox).where(db.outbox.c.id == job_id).values(status="sent"))

    def mark_failed(self, job: OutboxJob) -> None:
        """Back off a failed delivery or park it after the retry limit."""
        retries = job.retries + 1
        delay_seconds = min(3600, 2**retries * 10)
        with self.sessions.begin() as session:
            session.execute(
                update(db.outbox)
                .where(db.outbox.c.id == job.id)
                .values(
                    status="failed" if retries >= MAX_RETRIES else "pending",
                    retries=retries,
                    next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=delay_seconds),
                )
            )
