"""Telegram registration never trusts arbitrary messages as subscriptions."""

import pytest

from apps.telegram.bot import registration_reply
from apps.telegram.subscribe import normalize_chat_id


def test_start_command_returns_chat_id_for_admin_binding():
    reply = registration_reply({"message": {"chat": {"id": -100123}, "text": "/start"}})
    assert reply[0] == "-100123"
    assert "-100123" in reply[1]
    assert registration_reply({"message": {"chat": {"id": 123}, "text": "hello"}}) is None


def test_chat_id_must_be_numeric():
    assert normalize_chat_id("-100123") == "-100123"
    with pytest.raises(ValueError):
        normalize_chat_id("@public-channel")
