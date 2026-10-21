"""Shared secret redaction for errors and diagnostics."""

import re

from app.logging import BEARER_PATTERN, CAPABILITY_QUERY_PATTERN, SENSITIVE_KEYS

_TOKEN_LIKE = re.compile(
    r"(?i)\b(?:canvas[_-]?token|authorization|bearer|api[_-]?key)\b\s*[:=]\s*\S+"
)


def redact_secrets(text: str) -> str:
    if not text:
        return text
    redacted = BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    redacted = CAPABILITY_QUERY_PATTERN.sub(r"\1[REDACTED]", redacted)
    redacted = _TOKEN_LIKE.sub("[REDACTED]", redacted)
    for key in SENSITIVE_KEYS:
        redacted = re.sub(
            rf"(?i)({re.escape(key)}\s*[:=]\s*)(\S+)",
            r"\1[REDACTED]",
            redacted,
        )
    return redacted
