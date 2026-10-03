"""Developer notifications contain approved diagnostics only."""

from backend.apps.worker.devbot import format_diagnostic


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
