import hashlib
from pathlib import Path

import httpx
import pytest
from app.files.downloader import (
    ControlledFileDownloader,
    FileDownloadError,
    PublicHttpsDestinationPolicy,
)
from pydantic import SecretStr


async def allow_test_destination(_: httpx.URL) -> None:
    return None


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self):  # type: ignore[no-untyped-def]
        yield b"partial"
        raise httpx.ReadError("stream interrupted")


@pytest.mark.asyncio
async def test_same_origin_auth_and_cross_origin_redirect_strips_token(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "canvas.example.edu":
            return httpx.Response(
                302,
                headers={"Location": "https://cdn.example.net/file.pdf?signature=sensitive"},
                request=request,
            )
        return httpx.Response(200, content=b"course bytes", request=request)

    destination = tmp_path / "7001" / "lecture.pdf"
    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=1000,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        result = await downloader.download(
            "https://canvas.example.edu/files/7001/download", destination, storage_root=tmp_path
        )

    assert requests[0].headers["Authorization"] == "Bearer fake-unit-token"
    assert "Authorization" not in requests[1].headers
    assert result.sha256 == hashlib.sha256(b"course bytes").hexdigest()
    assert result.size == len(b"course bytes")
    assert destination.read_bytes() == b"course bytes"


@pytest.mark.asyncio
async def test_same_origin_final_download_preserves_auth(tmp_path: Path) -> None:
    seen_auth: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("Authorization"))
        return httpx.Response(200, content=b"ok", request=request)

    destination = tmp_path / "file" / "a.pdf"
    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        await downloader.download(
            "https://canvas.example.edu/files/1/download", destination, storage_root=tmp_path
        )
    assert seen_auth == ["Bearer fake-unit-token"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/file",
        "file:///tmp/file",
        "data:text/plain,hello",
        "javascript:alert(1)",
        "https://user:pass@example.com/file",
        "not a url",
    ],
)
async def test_dangerous_or_malformed_schemes_and_userinfo_are_rejected(
    url: str, tmp_path: Path
) -> None:
    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError):
            await downloader.download(url, tmp_path / "x" / "file", storage_root=tmp_path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/file",
        "https://127.0.0.1/file",
        "https://127.1.2.3/file",
        "https://[::1]/file",
        "https://10.0.0.1/file",
        "https://172.16.0.1/file",
        "https://192.168.1.1/file",
        "https://169.254.1.1/file",
        "https://[fe80::1]/file",
        "https://0.0.0.0/file",
    ],
)
async def test_ssrf_policy_rejects_non_public_destinations(url: str) -> None:
    with pytest.raises(FileDownloadError, match="not public"):
        await PublicHttpsDestinationPolicy()(httpx.URL(url))


@pytest.mark.asyncio
async def test_redirect_loop_is_rejected(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": str(request.url)}, request=request)

    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError, match="loop"):
            await downloader.download(
                "https://canvas.example.edu/files/1", tmp_path / "x" / "f", storage_root=tmp_path
            )


@pytest.mark.asyncio
async def test_redirect_limit_is_bounded(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        number = int(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(302, headers={"Location": f"/redirect/{number + 1}"}, request=request)

    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        max_redirects=2,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError, match="redirect limit"):
            await downloader.download(
                "https://canvas.example.edu/redirect/0", tmp_path / "x" / "f", storage_root=tmp_path
            )


@pytest.mark.asyncio
async def test_unsupported_redirect_status_is_not_treated_as_file_content(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(300, headers={"Location": "/ambiguous"}, request=request)

    destination = tmp_path / "x" / "file"
    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError, match="unsupported redirect"):
            await downloader.download(
                "https://canvas.example.edu/files/1", destination, storage_root=tmp_path
            )
    assert not destination.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ({"Content-Length": "11"}, b"01234567890"),
        ({}, b"01234567890"),
        ({"Content-Length": "2"}, b"01234567890"),
    ],
)
async def test_declared_or_actual_oversize_is_rejected_and_temp_cleaned(
    headers: dict[str, str], body: bytes, tmp_path: Path
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=headers, content=body, request=request)

    destination = tmp_path / "file" / "large.bin"
    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=10,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError) as exc_info:
            await downloader.download(
                "https://canvas.example.edu/files/1", destination, storage_root=tmp_path
            )
    assert exc_info.value.category == "too_large"
    assert not destination.exists()
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_interrupted_stream_preserves_previous_file_and_cleans_temp(tmp_path: Path) -> None:
    destination = tmp_path / "file" / "lecture.pdf"
    destination.parent.mkdir()
    destination.write_bytes(b"previous-good-copy")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=BrokenStream(), request=request)

    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError, match="stream failed"):
            await downloader.download(
                "https://canvas.example.edu/files/1", destination, storage_root=tmp_path
            )
    assert destination.read_bytes() == b"previous-good-copy"
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_http_error_body_and_signed_url_are_not_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    secret_url = "https://cdn.example.net/file?signature=do-not-log"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="hostile sensitive response body", request=request)

    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError, match="HTTP 500"):
            await downloader.download(secret_url, tmp_path / "x" / "f", storage_root=tmp_path)
    assert "do-not-log" not in caplog.text
    assert "hostile sensitive response body" not in caplog.text
    assert "fake-unit-token" not in caplog.text


@pytest.mark.asyncio
async def test_authorization_stays_stripped_across_multiple_cross_origin_redirects(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "canvas.example.edu":
            location = "https://cdn-one.example/file?signature=first"
            return httpx.Response(302, headers={"Location": location}, request=request)
        if request.url.host == "cdn-one.example":
            location = "https://cdn-two.example/file?signature=second"
            return httpx.Response(307, headers={"Location": location}, request=request)
        return httpx.Response(200, content=b"ok", request=request)

    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        await downloader.download(
            "https://canvas.example.edu/files/1",
            tmp_path / "x" / "file",
            storage_root=tmp_path,
        )
    assert requests[0].headers.get("Authorization") == "Bearer fake-unit-token"
    assert all("Authorization" not in request.headers for request in requests[1:])


@pytest.mark.asyncio
async def test_authorization_is_not_restored_after_cross_origin_redirect(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                302, headers={"Location": "https://cdn.example/file"}, request=request
            )
        if len(requests) == 2:
            return httpx.Response(
                302,
                headers={"Location": "https://canvas.example.edu/files/1/final"},
                request=request,
            )
        return httpx.Response(200, content=b"ok", request=request)

    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        await downloader.download(
            "https://canvas.example.edu/files/1",
            tmp_path / "x" / "file",
            storage_root=tmp_path,
        )
    assert requests[0].headers.get("Authorization") == "Bearer fake-unit-token"
    assert all("Authorization" not in request.headers for request in requests[1:])


@pytest.mark.asyncio
async def test_https_redirect_to_http_is_rejected_before_second_request(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            302, headers={"Location": "http://cdn.example/file"}, request=request
        )

    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError, match="HTTPS"):
            await downloader.download(
                "https://canvas.example.edu/files/1",
                tmp_path / "x" / "file",
                storage_root=tmp_path,
            )
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_missing_content_length_allows_small_stream(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=httpx.ByteStream(b"small"), request=request)

    destination = tmp_path / "x" / "small.bin"
    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        result = await downloader.download(
            "https://canvas.example.edu/files/1", destination, storage_root=tmp_path
        )
    assert result.size == 5
    assert destination.read_bytes() == b"small"


@pytest.mark.asyncio
async def test_timeout_and_http_error_are_sanitized_and_leave_no_file(tmp_path: Path) -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret transport detail", request=request)

    destination = tmp_path / "x" / "file"
    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(timeout_handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError, match="timed out"):
            await downloader.download(
                "https://canvas.example.edu/files/1", destination, storage_root=tmp_path
            )
    assert not destination.exists()

    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="hostile response body", request=request)

    async with ControlledFileDownloader(
        canvas_base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        max_bytes=100,
        transport=httpx.MockTransport(error_handler),
        destination_validator=allow_test_destination,
    ) as downloader:
        with pytest.raises(FileDownloadError) as error:
            await downloader.download(
                "https://canvas.example.edu/files/1", destination, storage_root=tmp_path
            )
    assert error.value.category == "inaccessible"
    assert "hostile response body" not in str(error.value)


@pytest.mark.asyncio
async def test_dns_resolution_with_any_private_address_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mixed_resolution(*_: object, **__: object) -> list[tuple[object, ...]]:
        return [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("10.0.0.5", 443)),
        ]

    monkeypatch.setattr("app.files.downloader.socket.getaddrinfo", mixed_resolution)
    with pytest.raises(FileDownloadError, match="not public"):
        await PublicHttpsDestinationPolicy()(httpx.URL("https://mixed.example/file"))
