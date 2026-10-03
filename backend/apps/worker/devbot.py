"""Deliver redacted client error codes from integration_jobs to a developer bot."""

import logging
import os
import time
from collections import Counter, deque

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from backend.apps.api.logging_config import configure_json_logging
from backend.infrastructure.postgres import models as db
from backend.infrastructure.telegram import TelegramDeliveryError, TelegramTransport

logger = logging.getLogger(__name__)

MAX_MESSAGES_PER_MINUTE = 20


class DevbotRateLimiter:
    """Reserve the final minute slot for an aggregated diagnostic message."""

    def __init__(self) -> None:
        self.sent_at: deque[float] = deque()

    def mode(self, now: float) -> str:
        """Return single, aggregate, or wait for the rolling minute."""
        while self.sent_at and now - self.sent_at[0] >= 60:
            self.sent_at.popleft()
        if len(self.sent_at) >= MAX_MESSAGES_PER_MINUTE:
            return "wait"
        if len(self.sent_at) == MAX_MESSAGES_PER_MINUTE - 1:
            return "aggregate"
        return "single"

    def sent(self, now: float) -> None:
        """Record a successful Telegram send, never an attempted send."""
        self.sent_at.append(now)


def format_diagnostic(payload: dict) -> str:
    """Render only the server-validated code, trace and approved context."""
    level = str(payload["level"]).upper()
    message_code = str(payload["message_code"])
    trace_id = str(payload["trace_id"])
    context = payload.get("context", {})
    details = ", ".join(f"{key}={value}" for key, value in sorted(context.items()))
    return f"{level} · API\nTrace: {trace_id}\nCode: {message_code}" + (
        f"\nContext: {details}" if details else ""
    )


def format_diagnostic_summary(payloads: list[dict]) -> str:
    """Count machine codes without including request data or personal details."""
    counts = Counter(str(payload["message_code"]) for payload in payloads)
    lines = [f"{code}: {count}" for code, count in sorted(counts.items())]
    return f"ERROR · API\nDiagnostics grouped: {len(payloads)}\n" + "\n".join(lines)


class PostgresDevJobRepository:
    """Send under a row lock so a failure leaves the job pending for retry."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def deliver_one(self, transport: TelegramTransport, chat_id: str) -> bool:
        """Deliver one due developer notification from the generic integration queue."""
        with self.sessions.begin() as session:
            job = (
                session.execute(
                    select(db.integration_jobs)
                    .where(
                        db.integration_jobs.c.integration == "devbot",
                        db.integration_jobs.c.status == "pending",
                    )
                    .order_by(db.integration_jobs.c.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if job is None:
                return False
            transport.send_message(chat_id, format_diagnostic(job["payload"]))
            session.execute(
                update(db.integration_jobs)
                .where(db.integration_jobs.c.id == job["id"])
                .values(status="sent")
            )
            return True

    def deliver_aggregate(self, transport: TelegramTransport, chat_id: str) -> bool:
        """Use one Telegram message for up to 100 pending diagnostics."""
        with self.sessions.begin() as session:
            jobs = (
                session.execute(
                    select(db.integration_jobs)
                    .where(
                        db.integration_jobs.c.integration == "devbot",
                        db.integration_jobs.c.status == "pending",
                    )
                    .order_by(db.integration_jobs.c.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(100)
                )
                .mappings()
                .all()
            )
            if not jobs:
                return False
            transport.send_message(
                chat_id, format_diagnostic_summary([job["payload"] for job in jobs])
            )
            session.execute(
                update(db.integration_jobs)
                .where(db.integration_jobs.c.id.in_([job["id"] for job in jobs]))
                .values(status="sent")
            )
            return True


def main() -> None:
    """Poll the diagnostic queue with the developer bot's separate credentials."""
    configure_json_logging(service="devbot-worker", level=os.getenv("LOG_LEVEL", "INFO"))
    sessions = sessionmaker(create_engine(os.environ["DATABASE_URL"]))
    repository = PostgresDevJobRepository(sessions)
    transport = TelegramTransport(os.environ["TELEGRAM_DEV_BOT_TOKEN"])
    chat_id = os.environ["TELEGRAM_DEV_CHAT_ID"]
    limiter = DevbotRateLimiter()
    while True:
        try:
            now = time.monotonic()
            mode = limiter.mode(now)
            if mode == "wait":
                time.sleep(1)
                continue
            delivered = (
                repository.deliver_aggregate(transport, chat_id)
                if mode == "aggregate"
                else repository.deliver_one(transport, chat_id)
            )
            if delivered:
                limiter.sent(time.monotonic())
            else:
                time.sleep(2)
        except TelegramDeliveryError:
            logger.warning("Developer bot delivery delayed")
            time.sleep(5)


if __name__ == "__main__":
    main()
