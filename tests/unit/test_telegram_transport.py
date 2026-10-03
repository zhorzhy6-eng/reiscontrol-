"""Telegram transport sends the Bot API contract without leaking tokens on failure."""

import httpx
import pytest

from backend.infrastructure.telegram import TelegramDeliveryError, TelegramTransport


def test_send_message_uses_post_and_checks_telegram_ok():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    client = httpx.Client(transport=httpx.MockTransport(handle))
    TelegramTransport("test-token", client).send_message("123", "Hello")
    assert requests[0].method == "POST"
    assert requests[0].url.path.endswith("/sendMessage")


def test_send_message_masks_provider_failure():
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(500)))
    with pytest.raises(TelegramDeliveryError) as captured:
        TelegramTransport("test-token", client).send_message("123", "Hello")
    assert "test-token" not in str(captured.value)
