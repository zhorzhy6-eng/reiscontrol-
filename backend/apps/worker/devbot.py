"""Deliver redacted client error codes from integration_jobs to a developer bot."""

import logging
import os
import time

from backend.apps.api.logging_config import configure_json_logging
from backend.infrastructure.postgres import models as db
from backend.infrastructure.telegram import TelegramDeliveryError, TelegramTransport
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


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


def main() -> None:
    """Poll the diagnostic queue with the developer bot's separate credentials."""
    configure_json_logging(service="devbot-worker", level=os.getenv("LOG_LEVEL", "INFO"))
    sessions = sessionmaker(create_engine(os.environ["DATABASE_URL"]))
    repository = PostgresDevJobRepository(sessions)
    transport = TelegramTransport(os.environ["TELEGRAM_DEV_BOT_TOKEN"])
    chat_id = os.environ["TELEGRAM_DEV_CHAT_ID"]
    while True:
        try:
            if not repository.deliver_one(transport, chat_id):
                time.sleep(2)
        except TelegramDeliveryError:
            logger.warning("Developer bot delivery delayed")
            time.sleep(5)


if __name__ == "__main__":
    main()
