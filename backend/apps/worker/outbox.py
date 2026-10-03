"""Deliver accepted event notifications to scoped Telegram subscriptions."""

import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.apps.api.logging_config import configure_json_logging
from backend.infrastructure.postgres.outbox import OutboxJob, PostgresOutboxRepository
from backend.infrastructure.telegram import TelegramDeliveryError, TelegramTransport

logger = logging.getLogger(__name__)


class NoRecipientsError(RuntimeError):
    """No currently authorized logistician has subscribed to this trip."""


def format_event_message(event: dict) -> str:
    """Build a concise factual notification without names or credentials."""
    occurred = event.get("device_time_utc")
    if isinstance(occurred, datetime):
        occurred_text = occurred.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    else:
        occurred_text = "время не указано"
    lines = [
        f"Рейс-Контроль: {event['event_type_code']}",
        f"Рейс: {event['trip_id']}",
        f"Время: {occurred_text}",
    ]
    if event.get("lat") is not None and event.get("lon") is not None:
        lines.append(f"Координаты: {float(event['lat']):.6f}, {float(event['lon']):.6f}")
    return "\n".join(lines)


class OutboxWorker:
    """One bounded delivery pass; a supervisor may call it repeatedly."""

    def __init__(self, repository: PostgresOutboxRepository, telegram: TelegramTransport) -> None:
        self.repository = repository
        self.telegram = telegram

    def run_once(self) -> bool:
        """Claim and process one event, returning false when no job is due."""
        job = self.repository.claim_next()
        if job is None:
            return False
        try:
            self._deliver(job)
            self.repository.mark_sent(job.id)
            logger.info("Outbox notification sent", extra={"event_id": str(job.event_id)})
        except (TelegramDeliveryError, NoRecipientsError, ValueError) as error:
            self.repository.mark_failed(job)
            logger.warning(
                "Outbox notification delayed",
                extra={"event_id": str(job.event_id), "context": {"reason": type(error).__name__}},
            )
        return True

    def _deliver(self, job: OutboxJob) -> None:
        event = self.repository.event_context(job.event_id)
        if event is None or event["state"] != "accepted":
            raise ValueError("Accepted event unavailable")
        recipients = self.repository.recipients(event["trip_id"], event["client_id"])
        if not recipients:
            raise NoRecipientsError("No scoped Telegram subscriptions")
        message = format_event_message(event)
        for chat_id in recipients:
            if self.repository.delivered(job.event_id, chat_id):
                continue
            self.telegram.send_message(chat_id, message)
            self.repository.mark_delivered(job.event_id, chat_id)


def main() -> None:
    """Poll the PostgreSQL outbox with secrets injected through environment."""
    configure_json_logging(service="worker", level=os.getenv("LOG_LEVEL", "INFO"))
    sessions = sessionmaker(create_engine(os.environ["DATABASE_URL"]))
    worker = OutboxWorker(
        PostgresOutboxRepository(sessions), TelegramTransport(os.environ["TELEGRAM_BOT_TOKEN"])
    )
    while True:
        if not worker.run_once():
            time.sleep(2)


if __name__ == "__main__":
    main()
