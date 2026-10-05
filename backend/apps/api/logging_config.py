"""Structured, privacy-conscious JSON logging for API and workers."""

import json
import logging
from datetime import datetime, timezone

LOG_FIELDS = (
    "trace_id",
    "user_id",
    "device_id",
    "trip_id",
    "event_id",
    "app_version",
    "platform",
)
CONTEXT_FIELDS = ("event_type_code", "attachments_count", "duration_ms", "status_code")


class JsonFormatter(logging.Formatter):
    """Emit ADR-0011 fields while dropping unapproved context keys."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        """Format one log record without serializing request bodies or coordinates."""
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": self.service,
            "message": record.getMessage(),
        }
        for field in LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload["context"] = {key: context[key] for key in CONTEXT_FIELDS if key in context}
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_json_logging(*, service: str, level: str = "INFO") -> None:
    """Configure the process root logger for structured output."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service))
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
    # httpx includes the full Telegram Bot API URL, including its token, at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
