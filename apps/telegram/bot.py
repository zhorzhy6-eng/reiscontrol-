"""Small polling bot that reveals a chat ID for administrator subscription setup."""

import logging
import os
import time

import httpx

from backend.apps.api.logging_config import configure_json_logging
from backend.infrastructure.telegram import TelegramDeliveryError, TelegramTransport

logger = logging.getLogger(__name__)


def registration_reply(update: dict) -> tuple[str, str] | None:
    """Reply only to explicit registration commands without trusting message text."""
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    command = str(message.get("text", "")).split(maxsplit=1)[0]
    chat = message.get("chat", {})
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    if command not in ("/start", "/chatid") or not isinstance(chat_id, int):
        return None
    return (
        str(chat_id),
        f"ID чата: {chat_id}\nПередайте ID администратору для подключения уведомлений о рейсах.",
    )


def main() -> None:
    """Poll Telegram for registration commands; deliveries run in the backend worker."""
    configure_json_logging(service="telegram-bot", level=os.getenv("LOG_LEVEL", "INFO"))
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    transport = TelegramTransport(token)
    offset = 0
    with httpx.Client(timeout=35) as client:
        while True:
            try:
                response = client.get(
                    f"https://api.telegram.org/bot{token}/getUpdates",
                    params={"offset": offset, "timeout": 25, "allowed_updates": '["message"]'},
                )
                response.raise_for_status()
                result = response.json()
                if result.get("ok") is not True:
                    raise TelegramDeliveryError("Telegram polling failed")
                for update in result.get("result", []):
                    offset = max(offset, int(update["update_id"]) + 1)
                    reply = registration_reply(update)
                    if reply is not None:
                        transport.send_message(*reply)
            except (httpx.HTTPError, ValueError, KeyError, TelegramDeliveryError):
                logger.warning("Telegram polling delayed")
                time.sleep(5)


if __name__ == "__main__":
    main()
