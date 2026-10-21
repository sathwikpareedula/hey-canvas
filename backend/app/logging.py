"""Minimal JSON logging with defense-in-depth credential redaction."""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "canvas_token",
        "password",
        "secret",
        "token",
    }
)
BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+\S+")
CAPABILITY_QUERY_PATTERN = re.compile(
    r"(?i)([?&](?:token|signature|sig|verifier|sf_verifier|x-amz-signature|"
    r"x-amz-credential|x-amz-security-token)=)[^&\s\"']+"
)


def _redact(value: Any, key: str | None = None) -> Any:
    if key and any(fragment in key.lower() for fragment in SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            item_key: _redact(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        redacted = BEARER_PATTERN.sub("Bearer [REDACTED]", value)
        return CAPABILITY_QUERY_PATTERN.sub(r"\1[REDACTED]", redacted)
    return value


class JsonFormatter(logging.Formatter):
    """Render standard log records as single-line JSON."""

    _reserved = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._reserved and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(_redact(payload), default=str, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """Configure the root logger exactly once for application use."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # HTTPX logs complete request URLs at INFO. Canvas file downloads may use
    # short-lived capability URLs whose query strings must not enter telemetry.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
