"""Developer notifications contain approved diagnostics only."""

from backend.apps.worker.devbot import (
    DevbotRateLimiter,
    format_diagnostic,
    format_diagnostic_summary,
)


def test_diagnostic_format_uses_machine_code_and_trace():
    message = format_diagnostic(
        {
            "level": "error",
            "message_code": "sync.failed",
            "trace_id": "tr_12345678",
            "context": {"status_code": 503},
        }
    )
    assert "ERROR" in message
    assert "sync.failed" in message
    assert "tr_12345678" in message
    assert "status_code=503" in message


def test_devbot_caps_messages_and_reserves_summary_slot():
    limiter = DevbotRateLimiter()
    for index in range(19):
        assert limiter.mode(float(index)) == "single"
        limiter.sent(float(index))
    assert limiter.mode(19.0) == "aggregate"
    limiter.sent(19.0)
    assert limiter.mode(20.0) == "wait"
    assert limiter.mode(60.0) == "aggregate"
    assert limiter.mode(79.0) == "single"


def test_diagnostic_summary_counts_machine_codes():
    summary = format_diagnostic_summary(
        [
            {"message_code": "sync.failed"},
            {"message_code": "sync.failed"},
            {"message_code": "auth.failed"},
        ]
    )
    assert "Diagnostics grouped: 3" in summary
    assert "sync.failed: 2" in summary
    assert "auth.failed: 1" in summary
