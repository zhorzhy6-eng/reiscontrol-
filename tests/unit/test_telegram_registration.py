"""Telegram registration never trusts arbitrary messages as subscriptions."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, select

from apps.telegram.bot import registration_reply
from apps.telegram.subscribe import normalize_chat_id, set_subscription
from backend.infrastructure.postgres import models as db


def test_start_command_returns_chat_id_for_admin_binding():
    reply = registration_reply({"message": {"chat": {"id": -100123}, "text": "/start"}})
    assert reply[0] == "-100123"
    assert "-100123" in reply[1]
    assert registration_reply({"message": {"chat": {"id": 123}, "text": "hello"}}) is None


def test_chat_id_must_be_numeric():
    assert normalize_chat_id("-100123") == "-100123"
    with pytest.raises(ValueError):
        normalize_chat_id("@public-channel")


def test_repeated_subscription_updates_existing_row():
    with TemporaryDirectory() as directory:
        database_url = f"sqlite:///{Path(directory) / 'subscriptions.db'}"
        user_id = uuid4()
        engine = create_engine(database_url)
        db.metadata.create_all(engine, tables=[db.users, db.telegram_subscriptions])
        with engine.begin() as connection:
            connection.execute(
                insert(db.users).values(
                    id=user_id,
                    phone="+70000000000",
                    password_hash="test",
                    role="logistician",
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        engine.dispose()

        set_subscription(database_url, user_id, "12345", True)
        set_subscription(database_url, user_id, "12345", False)

        engine = create_engine(database_url)
        with engine.connect() as connection:
            rows = connection.execute(select(db.telegram_subscriptions)).mappings().all()
        engine.dispose()
        assert len(rows) == 1
        assert rows[0]["enabled"] is False
