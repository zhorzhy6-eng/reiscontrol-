"""Structured log serialization test."""

import json
import logging

from backend.apps.api.logging_config import JsonFormatter, configure_json_logging


def test_json_formatter_omits_unapproved_context_fields():
    record = logging.makeLogRecord(
        {
            "name": "test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "Event accepted",
            "trace_id": "trace-1",
            "context": {"status_code": 200, "lat": 55.7, "phone": "+70000000000"},
        }
    )
    payload = json.loads(JsonFormatter("api").format(record))
    assert payload["service"] == "api"
    assert payload["trace_id"] == "trace-1"
    assert payload["context"] == {"status_code": 200}
    assert "phone" not in json.dumps(payload)


def test_httpx_info_logs_are_suppressed_to_protect_bot_tokens():
    configure_json_logging(service="worker")
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
