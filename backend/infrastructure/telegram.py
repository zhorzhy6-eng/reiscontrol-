"""Small Telegram Bot API transport with secret-safe errors."""

import httpx


class TelegramDeliveryError(RuntimeError):
    """A Telegram request failed without exposing the token-bearing URL."""


class TelegramTransport:
    """Send text through an injected HTTP client for deterministic tests."""

    def __init__(self, token: str, client: httpx.Client | None = None) -> None:
        self.token = token
        self.client = client or httpx.Client(timeout=10)

    def send_message(self, chat_id: str, text: str) -> None:
        """Deliver a message and reject Telegram-level errors as retryable."""
        try:
            response = self.client.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
            if response.json().get("ok") is not True:
                raise TelegramDeliveryError("Telegram delivery failed")
        except (httpx.HTTPError, ValueError) as error:
            raise TelegramDeliveryError("Telegram delivery failed") from error
