"""Enforce maximum inbound HTTP body size, including chunked requests."""

from __future__ import annotations

from typing import Any, cast

from starlette.requests import Request
from starlette.types import Message, Receive


class RequestBodyTooLarge(Exception):
    """Raised when an inbound body exceeds the configured limit."""


class BodyLimitState:
    """Tracks whether a request body went over the configured limit."""

    def __init__(self) -> None:
        self.exceeded = False


def limit_receive(receive: Receive, max_bytes: int, state: BodyLimitState) -> Receive:
    """Wrap an ASGI receive callable so it enforces a cumulative body byte limit.

    The limit is recorded on ``state`` so callers can answer 413 even when an
    application framework converts the raised exception into another status.
    """
    received = 0

    async def limited_receive() -> Message:
        nonlocal received
        message = await receive()
        if message["type"] == "http.request":
            chunk = message.get("body", b"") or b""
            if isinstance(chunk, str):
                chunk = chunk.encode()
            received += len(chunk)
            if received > max_bytes:
                state.exceeded = True
                raise RequestBodyTooLarge()
        return message

    return limited_receive


def wrap_request_receive(request: Request, max_bytes: int) -> Request:
    """Return a request whose receive() enforces a cumulative body byte limit."""
    limited = limit_receive(request.receive, max_bytes, BodyLimitState())
    return Request(request.scope, cast(Any, limited))
