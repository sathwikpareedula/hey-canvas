"""Restrict local API access to loopback clients and trusted Hey Canvas origins.

Implemented as a pure ASGI middleware so the request body limit applies to the
actual receive channel handed to the application (including chunked bodies).
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.security.request_body_limit import BodyLimitState, RequestBodyTooLarge, limit_receive

LOCAL_CLIENT_HEADER = "x-hey-canvas-client"
LOCAL_CLIENT_VALUE = "hey-canvas-local"

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Starlette's TestClient identifies itself with these synthetic values.
_TEST_PEER = "testclient"
_TEST_HOST = "testserver"
_LOCAL_HOSTNAMES = frozenset({"localhost"})
_HOST_PATTERN = re.compile(
    r"^(?P<host>\[[0-9a-fA-F:.]+\]|[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)"
    r"(?::(?P<port>[0-9]{1,5}))?$"
)
_HOST_DENIED = {"detail": "Hey Canvas API is only available on this computer."}
_PRIVACY_DENIED = {"detail": "This request was blocked for your privacy."}
_TOO_LARGE = {"detail": "Request body is too large."}


def _parse_allowed_origins(raw: str) -> frozenset[str]:
    origins: set[str] = set()
    for part in raw.split(","):
        trimmed = part.strip().rstrip("/")
        if trimmed:
            origins.add(trimmed.lower())
    return frozenset(origins)


def _is_loopback_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_loopback


def _peer_allowed(client: tuple[str, int] | None) -> bool:
    if client is None:
        return False
    host = client[0]
    return host == _TEST_PEER or _is_loopback_ip(host)


def _hostname_allowed(hostname: str, peer: str | None) -> bool:
    if hostname in _LOCAL_HOSTNAMES or _is_loopback_ip(hostname):
        return True
    return hostname == _TEST_HOST and peer == _TEST_PEER


def _host_header_allowed(headers: Headers, peer: str | None) -> bool:
    """Accept only exactly one well-formed loopback Host header."""
    values = headers.getlist("host")
    if len(values) != 1:
        return False
    match = _HOST_PATTERN.match(values[0].strip())
    if match is None:
        return False
    port = match.group("port")
    if port is not None and int(port) > 65535:
        return False
    hostname = match.group("host").lower()
    if hostname.startswith("["):
        hostname = hostname[1:-1]
    return _hostname_allowed(hostname, peer)


def _origin_allowed(origin: str | None, allowed: frozenset[str]) -> bool:
    if not origin:
        return True
    normalized = origin.strip().rstrip("/").lower()
    try:
        parsed = urlsplit(normalized)
        parsed.port  # noqa: B018 - raises ValueError for malformed ports
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if parsed.path or parsed.query or parsed.fragment:
        return False
    # A malicious local web server is still an untrusted origin. Only the
    # configured frontend origins are allowed, including for safe methods.
    return normalized in allowed


class LocalApiGuardMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from app.config import get_settings

        settings = get_settings()
        if not settings.local_api_guard_enabled:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        method = str(scope["method"]).upper()
        path = str(scope["path"])
        client = scope.get("client")
        peer = client[0] if client else None

        if not _peer_allowed(client) or not _host_header_allowed(headers, peer):
            await self._reject(403, _HOST_DENIED, scope, receive, send)
            return

        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        origin = headers.get("origin")
        if origin is not None and not _origin_allowed(
            origin, _parse_allowed_origins(settings.local_api_allowed_origins)
        ):
            await self._reject(403, _PRIVACY_DENIED, scope, receive, send)
            return
        if method in _SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        if headers.get(LOCAL_CLIENT_HEADER) != LOCAL_CLIENT_VALUE:
            await self._reject(403, _PRIVACY_DENIED, scope, receive, send)
            return

        max_bytes = settings.local_api_max_body_bytes
        declared = headers.get("content-length")
        if declared is not None:
            try:
                declared_bytes = int(declared)
            except ValueError:
                await self._reject(400, {"detail": "Invalid request."}, scope, receive, send)
                return
            if declared_bytes < 0:
                await self._reject(400, {"detail": "Invalid request."}, scope, receive, send)
                return
            if declared_bytes > max_bytes:
                await self._reject(413, _TOO_LARGE, scope, receive, send)
                return

        state = BodyLimitState()
        limited = limit_receive(receive, max_bytes, state)
        response_started = False
        replaced = False

        async def guarded_send(message: Message) -> None:
            nonlocal response_started, replaced
            if state.exceeded:
                # Frameworks may turn the aborted read into another status; force 413.
                if not response_started and not replaced:
                    replaced = True
                    await self._reject(413, _TOO_LARGE, scope, receive, send)
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited, guarded_send)
        except RequestBodyTooLarge:
            if not response_started and not replaced:
                await self._reject(413, _TOO_LARGE, scope, receive, send)
        else:
            if state.exceeded and not response_started and not replaced:
                await self._reject(413, _TOO_LARGE, scope, receive, send)

    @staticmethod
    async def _reject(
        status_code: int,
        content: dict[str, str],
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        response = JSONResponse(status_code=status_code, content=content)
        await response(scope, receive, send)
