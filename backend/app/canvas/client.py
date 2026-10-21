"""Asynchronous, credential-safe Canvas REST API client."""

import asyncio
import logging
import math
import secrets
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import monotonic
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import SecretStr

from app.canvas.exceptions import (
    CanvasAPIError,
    CanvasAuthenticationError,
    CanvasConfigurationError,
    CanvasRateLimitError,
    CanvasResponseError,
    CanvasTransportError,
)

logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_ATTEMPTS = 10
MAX_RETRY_DELAY_SECONDS = 60.0

QueryPrimitive = str | int | float | bool
RequestParams = httpx.QueryParams | Mapping[str, QueryPrimitive]


class CanvasClient:
    """Small Canvas API client with pagination, retries, and safe diagnostics."""

    def __init__(
        self,
        *,
        base_url: str,
        token: SecretStr,
        timeout_seconds: float = 20.0,
        max_attempts: int = 3,
        backoff_base_seconds: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = _validate_base_url(base_url)
        if not token.get_secret_value().strip():
            raise CanvasConfigurationError("CANVAS_TOKEN is empty")
        if not 1 <= max_attempts <= MAX_RETRY_ATTEMPTS:
            raise CanvasConfigurationError(
                f"max_attempts must be between 1 and {MAX_RETRY_ATTEMPTS}"
            )
        if timeout_seconds <= 0:
            raise CanvasConfigurationError("timeout_seconds must be positive")
        if backoff_base_seconds < 0:
            raise CanvasConfigurationError("backoff_base_seconds cannot be negative")

        self._max_attempts = max_attempts
        self._backoff_base_seconds = backoff_base_seconds
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token.get_secret_value()}",
                "Accept": "application/json+canvas-string-ids",
                "User-Agent": "uta-academic-copilot/0.1",
            },
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
            follow_redirects=False,
        )

    async def __aenter__(self) -> "CanvasClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close pooled network connections."""

        await self._client.aclose()

    async def get_json(
        self,
        path: str,
        *,
        params: RequestParams | None = None,
    ) -> Any:
        """GET one JSON resource and reject malformed JSON."""

        response = await self._request("GET", self._resolve_url(path), params=params)
        return _decode_json(response)

    async def get_paginated(
        self,
        path: str,
        *,
        params: RequestParams | None = None,
        max_pages: int = 1_000,
    ) -> list[dict[str, Any]]:
        """Collect a Canvas list endpoint by following same-origin `rel=next` links."""

        if max_pages < 1:
            raise CanvasConfigurationError("max_pages must be at least 1")

        results: list[dict[str, Any]] = []
        next_url: str | None = self._resolve_url(path)
        next_params = params
        visited: set[str] = set()

        for _ in range(max_pages):
            if next_url is None:
                return results
            if next_url in visited:
                raise CanvasResponseError("Canvas pagination returned a repeated next link")
            visited.add(next_url)

            response = await self._request("GET", next_url, params=next_params)
            payload = _decode_json(response)
            if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
                raise CanvasResponseError("Canvas list endpoint returned an unexpected JSON shape")
            results.extend(payload)

            next_url = self._get_next_link(response)
            next_params = None

        if next_url is not None:
            raise CanvasResponseError(
                f"Canvas pagination exceeded the {max_pages}-page safety limit"
            )
        return results

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: RequestParams | None = None,
    ) -> httpx.Response:
        endpoint = _safe_endpoint(url)
        for attempt in range(1, self._max_attempts + 1):
            started_at = monotonic()
            try:
                response = await self._client.request(method, url, params=params)
            except httpx.TransportError as exc:
                logger.warning(
                    "Canvas request transport failure",
                    extra={
                        "operation": "canvas.request",
                        "method": method,
                        "endpoint": endpoint,
                        "attempt": attempt,
                        "duration_ms": round((monotonic() - started_at) * 1_000, 2),
                        "status": "retrying" if attempt < self._max_attempts else "failed",
                        "error": type(exc).__name__,
                    },
                )
                if attempt == self._max_attempts:
                    raise CanvasTransportError(
                        f"Canvas request failed after {attempt} attempt(s): {method} {endpoint}"
                    ) from exc
                await self._sleep_before_retry(attempt, retry_after_seconds=None)
                continue

            duration_ms = round((monotonic() - started_at) * 1_000, 2)
            remaining = _parse_numeric_header(response.headers.get("X-Rate-Limit-Remaining"))
            log_fields: dict[str, Any] = {
                "operation": "canvas.request",
                "method": method,
                "endpoint": endpoint,
                "attempt": attempt,
                "duration_ms": duration_ms,
                "http_status": response.status_code,
                "rate_limit_remaining": remaining,
            }

            if response.status_code in {401, 403}:
                logger.warning("Canvas authentication or authorization failed", extra=log_fields)
                raise CanvasAuthenticationError(
                    "Canvas rejected the configured credential or permission "
                    f"({response.status_code}) for {method} {endpoint}",
                    status_code=response.status_code,
                )

            if response.status_code in TRANSIENT_STATUS_CODES:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                if attempt == self._max_attempts:
                    logger.warning("Canvas request exhausted retries", extra=log_fields)
                    if response.status_code == 429:
                        raise CanvasRateLimitError(
                            f"Canvas rate limit persisted after {attempt} attempt(s)",
                            retry_after_seconds=retry_after,
                        )
                    raise CanvasAPIError(
                        f"Canvas returned {response.status_code} after {attempt} attempt(s) "
                        f"for {method} {endpoint}",
                        status_code=response.status_code,
                    )
                logger.info("Canvas request will be retried", extra=log_fields)
                await self._sleep_before_retry(attempt, retry_after_seconds=retry_after)
                continue

            if response.is_redirect:
                logger.warning(
                    "Canvas returned a redirect; redirect was not followed",
                    extra=log_fields,
                )
                raise CanvasAPIError(
                    f"Canvas returned redirect {response.status_code} for {method} {endpoint}; "
                    "automatic redirects are disabled",
                    status_code=response.status_code,
                )

            if response.is_error:
                logger.warning("Canvas request failed", extra=log_fields)
                raise CanvasAPIError(
                    f"Canvas returned {response.status_code} for {method} {endpoint}",
                    status_code=response.status_code,
                )

            logger.info("Canvas request completed", extra={**log_fields, "status": "ok"})
            return response

        raise AssertionError("retry loop ended unexpectedly")

    async def _sleep_before_retry(
        self,
        attempt: int,
        *,
        retry_after_seconds: float | None,
    ) -> None:
        exponential_delay = self._backoff_base_seconds * (2 ** (attempt - 1))
        jitter = secrets.SystemRandom().uniform(0, exponential_delay * 0.2)
        delay = (
            retry_after_seconds
            if retry_after_seconds is not None
            else exponential_delay + jitter
        )
        await asyncio.sleep(max(0.0, min(delay, MAX_RETRY_DELAY_SECONDS)))

    def _resolve_url(self, path: str) -> str:
        resolved = urljoin(f"{self._base_url}/", path.lstrip("/"))
        _assert_same_origin(self._base_url, resolved)
        return resolved

    def _get_next_link(self, response: httpx.Response) -> str | None:
        try:
            link = response.links.get("next")
        except ValueError as exc:
            raise CanvasResponseError("Canvas returned a malformed pagination Link header") from exc
        if link is None:
            return None
        next_url = str(link.get("url", ""))
        if not next_url:
            raise CanvasResponseError("Canvas next-page link did not contain a URL")
        _assert_same_origin(self._base_url, next_url)
        return next_url


def _validate_base_url(value: str) -> str:
    candidate = value.strip().rstrip("/")
    if not candidate:
        raise CanvasConfigurationError("CANVAS_BASE_URL is empty")
    try:
        url = httpx.URL(candidate)
    except Exception as exc:
        raise CanvasConfigurationError("CANVAS_BASE_URL is not a valid URL") from exc
    if (
        not url.host
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
        or url.username
        or url.password
    ):
        raise CanvasConfigurationError(
            "CANVAS_BASE_URL must be an origin URL without credentials, query, or fragment"
        )
    is_local = url.host in {"127.0.0.1", "localhost", "testserver"}
    if url.scheme != "https" and not is_local:
        raise CanvasConfigurationError("CANVAS_BASE_URL must use HTTPS")
    return str(url).rstrip("/")


def _assert_same_origin(base_url: str, candidate_url: str) -> None:
    base = httpx.URL(base_url)
    candidate = httpx.URL(candidate_url)
    if (base.scheme, base.host, base.port) != (candidate.scheme, candidate.host, candidate.port):
        raise CanvasResponseError("Canvas pagination attempted to leave the configured origin")


def _decode_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise CanvasResponseError(
            f"Canvas returned malformed JSON for {_safe_endpoint(str(response.request.url))}"
        ) from exc


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return min(MAX_RETRY_DELAY_SECONDS, max(0.0, float(value)))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return min(
            MAX_RETRY_DELAY_SECONDS,
            max(0.0, (retry_at - datetime.now(UTC)).total_seconds()),
        )


def _parse_numeric_header(value: str | None) -> float | None:
    """Return only a numeric rate-limit value, never an untrusted header string."""

    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _safe_endpoint(url: str) -> str:
    parsed = httpx.URL(url)
    return parsed.path


def ensure_sequence(value: Any) -> Sequence[Any]:
    """Narrow a decoded JSON value to a non-string sequence for future parsers."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CanvasResponseError("Canvas returned an unexpected JSON shape")
    return value
