"""Streaming downloader with manual redirects, SSRF checks, and token isolation."""

import asyncio
import hashlib
import ipaddress
import os
import socket
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx
from pydantic import SecretStr

from app.files.paths import assert_contained

REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})


class FileDownloadError(Exception):
    """A sanitized download failure with a persistence-safe category."""

    def __init__(self, message: str, *, category: str = "failed") -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class DownloadedFile:
    sha256: str
    size: int
    http_content_type: str | None


DestinationValidator = Callable[[httpx.URL], Awaitable[None]]


class PublicHttpsDestinationPolicy:
    """Practical SSRF defense; DNS rebinding remains a documented local-app limitation."""

    async def __call__(self, url: httpx.URL) -> None:
        _validate_url_shape(url)
        host = url.host
        if host is None:
            raise FileDownloadError("download URL has no host")
        if host.lower() == "localhost":
            raise FileDownloadError("download destination is not public")
        try:
            addresses = await asyncio.to_thread(_resolve_host, host, url.port or 443)
        except OSError as exc:
            raise FileDownloadError("download destination could not be resolved") from exc
        if not addresses or any(
            not ipaddress.ip_address(address).is_global for address in addresses
        ):
            raise FileDownloadError("download destination is not public")


class ControlledFileDownloader:
    """Download opaque bytes while forwarding Canvas auth only to the Canvas origin."""

    def __init__(
        self,
        *,
        canvas_base_url: str,
        token: SecretStr,
        max_bytes: int,
        timeout_seconds: float = 60.0,
        max_redirects: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        destination_validator: DestinationValidator | None = None,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        if not 0 <= max_redirects <= 10:
            raise ValueError("max_redirects must be between 0 and 10")
        self._canvas_origin = _origin(httpx.URL(canvas_base_url))
        self._token = token
        self._max_bytes = max_bytes
        self._max_redirects = max_redirects
        self._validate_destination = destination_validator or PublicHttpsDestinationPolicy()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "uta-academic-copilot/0.1"},
        )

    async def __aenter__(self) -> "ControlledFileDownloader":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def download(self, url: str, destination: Path, *, storage_root: Path) -> DownloadedFile:
        root = storage_root.expanduser().resolve(strict=False)
        final_path = destination.resolve(strict=False)
        assert_contained(root, final_path)
        current = _parse_url(url)
        visited: set[str] = set()
        redirects = 0
        canvas_auth_allowed = _origin(current) == self._canvas_origin

        while True:
            await self._validate_destination(current)
            normalized = str(current)
            if normalized in visited:
                raise FileDownloadError("download redirect loop detected")
            visited.add(normalized)
            headers: dict[str, str] = {"Accept": "application/octet-stream,*/*"}
            if canvas_auth_allowed and _origin(current) == self._canvas_origin:
                headers["Authorization"] = f"Bearer {self._token.get_secret_value()}"
            request = self._client.build_request("GET", current, headers=headers)
            try:
                response = await self._client.send(request, stream=True)
            except httpx.TimeoutException as exc:
                raise FileDownloadError("file download timed out") from exc
            except httpx.TransportError as exc:
                raise FileDownloadError("file download transport failed") from exc

            if response.status_code in REDIRECT_STATUS_CODES:
                await response.aclose()
                if redirects >= self._max_redirects:
                    raise FileDownloadError("file download exceeded redirect limit")
                location = response.headers.get("Location")
                if not location:
                    raise FileDownloadError("file download redirect had no location")
                next_url = _parse_url(urljoin(str(current), location))
                if _origin(next_url) != self._canvas_origin:
                    canvas_auth_allowed = False
                current = next_url
                redirects += 1
                continue

            if 300 <= response.status_code < 400:
                await response.aclose()
                raise FileDownloadError("file download returned an unsupported redirect")

            if response.is_error:
                status = response.status_code
                await response.aclose()
                category = "inaccessible" if status in {401, 403, 404} else "failed"
                raise FileDownloadError(
                    f"file download returned HTTP {status}", category=category
                )
            return await self._stream_response(response, final_path, root)

    async def _stream_response(
        self, response: httpx.Response, destination: Path, root: Path
    ) -> DownloadedFile:
        content_length = _content_length(response.headers.get("Content-Length"))
        if content_length is not None and content_length > self._max_bytes:
            await response.aclose()
            raise FileDownloadError("file exceeds MAX_CANVAS_FILE_BYTES", category="too_large")

        destination.parent.mkdir(parents=True, exist_ok=True)
        assert_contained(root, destination)
        handle, temp_name = tempfile.mkstemp(
            prefix=".canvas-download-", suffix=".part", dir=destination.parent
        )
        temp_path = Path(temp_name)
        digest = hashlib.sha256()
        total = 0
        try:
            with os.fdopen(handle, "wb") as output:
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self._max_bytes:
                        raise FileDownloadError(
                            "file exceeds MAX_CANVAS_FILE_BYTES", category="too_large"
                        )
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_path, destination)
        except FileDownloadError:
            temp_path.unlink(missing_ok=True)
            raise
        except httpx.TimeoutException as exc:
            temp_path.unlink(missing_ok=True)
            raise FileDownloadError("file download timed out") from exc
        except httpx.TransportError as exc:
            temp_path.unlink(missing_ok=True)
            raise FileDownloadError("file download stream failed") from exc
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise FileDownloadError("local file storage operation failed") from exc
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        finally:
            await response.aclose()
        return DownloadedFile(
            sha256=digest.hexdigest(),
            size=total,
            http_content_type=response.headers.get("Content-Type"),
        )


def _parse_url(value: str) -> httpx.URL:
    try:
        url = httpx.URL(value)
    except Exception as exc:
        raise FileDownloadError("download URL is malformed") from exc
    _validate_url_shape(url)
    return url


def _validate_url_shape(url: httpx.URL) -> None:
    if url.scheme != "https":
        raise FileDownloadError("download URL must use HTTPS")
    if url.host is None or url.username or url.password:
        raise FileDownloadError("download URL is malformed or contains userinfo")


def _origin(url: httpx.URL) -> tuple[str, str, int]:
    if url.host is None:
        raise FileDownloadError("download URL has no host")
    return url.scheme, url.host.lower(), url.port or 443


def _resolve_host(host: str, port: int) -> set[str]:
    return {
        str(entry[4][0])
        for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    }


def _content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None
