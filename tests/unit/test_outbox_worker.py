"""Outbox notifications obey scope recipients and retry partial delivery."""

from datetime import datetime, timezone
from uuid import uuid4

from backend.apps.worker.outbox import OutboxWorker, format_event_message
from backend.infrastructure.postgres.outbox import OutboxJob
from backend.infrastructure.telegram import TelegramDeliveryError


class FakeRepository:
    def __init__(self):
        self.job = OutboxJob(uuid4(), uuid4(), 0)
        self.delivered_chats = set()
        self.sent = False
        self.failed = 0

    def claim_next(self):
        return self.job

    def event_context(self, event_id):
        return {
            "state": "accepted",
            "trip_id": uuid4(),
            "client_id": uuid4(),
            "event_type_code": "ARRIVAL",
            "device_time_utc": datetime(2026, 10, 3, 10, tzinfo=timezone.utc),
            "lat": 55.75,
            "lon": 37.62,
        }

    def recipients(self, trip_id, client_id):
        return ["101", "202"]

    def delivered(self, event_id, chat_id):
        return chat_id in self.delivered_chats

    def mark_delivered(self, event_id, chat_id):
        self.delivered_chats.add(chat_id)

    def mark_sent(self, job_id):
        self.sent = True

    def mark_failed(self, job):
        self.failed += 1


class FlakyTelegram:
    def __init__(self):
        self.calls = []
        self.fail_second_once = True

    def send_message(self, chat_id, text):
        self.calls.append(chat_id)
        if chat_id == "202" and self.fail_second_once:
            self.fail_second_once = False
            raise TelegramDeliveryError("Telegram delivery failed")


def test_partial_delivery_retries_only_pending_recipient():
    repository, telegram = FakeRepository(), FlakyTelegram()
    worker = OutboxWorker(repository, telegram)
    assert worker.run_once()
    assert repository.failed == 1
    assert repository.delivered_chats == {"101"}
    assert worker.run_once()
    assert repository.sent
    assert telegram.calls == ["101", "202", "202"]


def test_event_message_includes_time_and_coordinates_without_personal_data():
    event = FakeRepository().event_context(uuid4())
    text = format_event_message(event)
    assert "ARRIVAL" in text
    assert "55.750000, 37.620000" in text
    assert "2026" in text
