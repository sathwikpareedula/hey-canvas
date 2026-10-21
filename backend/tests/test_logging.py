import json
import logging

from app.logging import JsonFormatter, configure_logging


def test_formatter_redacts_sensitive_fields_and_bearer_tokens() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request failed with Bearer abc:def?ghi=123",
        args=(),
        exc_info=None,
    )
    record.authorization = "Bearer never-log-this"
    record.operation = "canvas.request"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["authorization"] == "[REDACTED]"
    assert payload["operation"] == "canvas.request"
    assert payload["message"] == "request failed with Bearer [REDACTED]"
    assert "never-log-this" not in json.dumps(payload)


def test_formatter_redacts_capability_query_values() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            "download failed https://cdn.example/file?"
            "X-Amz-Signature=fake-signature&sf_verifier=fake-verifier"
        ),
        args=(),
        exc_info=None,
    )

    encoded = JsonFormatter().format(record)

    assert "fake-signature" not in encoded
    assert "fake-verifier" not in encoded
    assert encoded.count("[REDACTED]") == 2


def test_http_client_request_logging_is_suppressed_at_info() -> None:
    configure_logging("INFO")

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
