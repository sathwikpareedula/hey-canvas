"""Adversarial Host, Origin, client-header and request-body checks (synthetic only)."""

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from app.config import get_settings
from app.database.session import get_session
from app.main import app
from app.security.local_api_guard import LOCAL_CLIENT_HEADER, LOCAL_CLIENT_VALUE
from sqlalchemy.orm import Session, sessionmaker

CLIENT_HEADERS = {LOCAL_CLIENT_HEADER: LOCAL_CLIENT_VALUE}


@pytest.fixture(autouse=True)
def _enable_guard(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> Iterator[None]:
    monkeypatch.setenv("LOCAL_API_GUARD_ENABLED", "true")
    get_settings.cache_clear()

    def override() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()


async def _send(
    method: str = "GET",
    path: str = "/health",
    *,
    host: str | None = "127.0.0.1:8000",
    headers: dict[str, str] | None = None,
    content: bytes | AsyncIterator[bytes] | None = None,
    peer: tuple[str, int] | None = ("127.0.0.1", 50000),
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, client=peer)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        request = client.build_request(method, path, headers=headers or {}, content=content)
        if host is None:
            del request.headers["host"]
        else:
            request.headers["host"] = host
        return await client.send(request)


@pytest.mark.asyncio
@pytest.mark.parametrize("host", [None, ""])
async def test_missing_or_empty_host_header_is_rejected(host: str | None) -> None:
    response = await _send(host=host)
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "host",
    [
        "localhost:evil",
        "localhost:99999999",
        "localhost:",
        "localhost, evil.example",
        "localhost@evil.example",
        "localhost.evil.example",
        "127.0.0.1.evil.example",
        "evil.example:8000",
        "[::1",
        "localhost/evil",
        "0.0.0.0",
        "testserver",
    ],
)
async def test_malformed_or_non_loopback_host_is_rejected(host: str) -> None:
    response = await _send(host=host)
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "host", ["localhost", "LOCALHOST:3001", "127.0.0.1:8000", "[::1]:8000", "[::1]"]
)
async def test_legitimate_loopback_hosts_remain_available(host: str) -> None:
    response = await _send(host=host)
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("peer", [("10.0.0.5", 1), ("192.168.1.9", 1), None])
async def test_non_loopback_or_unknown_peer_is_rejected(peer: tuple[str, int] | None) -> None:
    response = await _send(peer=peer)
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("peer", [("::1", 1), ("::ffff:127.0.0.1", 1)])
async def test_ipv6_loopback_peers_remain_available(peer: tuple[str, int]) -> None:
    response = await _send(peer=peer)
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin",
    [
        "null",
        "https://attacker.example",
        "http://localhost.attacker.example",
        "http://localhost@attacker.example",
        "http://attacker.example/http://localhost",
        "http://localhost:3001/extra/path",
        "******localhost:3001",
        "http://localhost:3001?x=1",
        "http://localhost:abc",
        "ftp://localhost:3001",
        "file://",
        "javascript:alert(1)",
        "://",
        "   ",
    ],
)
async def test_hostile_or_malformed_origin_cannot_mutate(origin: str) -> None:
    response = await _send(
        "PUT",
        "/api/privacy",
        headers={**CLIENT_HEADERS, "origin": origin, "content-type": "application/json"},
        content=b'{"mode":"LOCAL_ONLY"}',
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_value", [None, "", "hey-canvas-local ", "HEY-CANVAS-LOCAL", "true", "hey-canvas"]
)
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_client_header_is_mandatory_even_without_origin(
    method: str, client_value: str | None
) -> None:
    headers = {} if client_value is None else {LOCAL_CLIENT_HEADER: client_value}
    response = await _send(method, "/api/privacy", headers=headers, content=b"{}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_chunked_body_without_content_length_is_capped() -> None:
    async def body() -> AsyncIterator[bytes]:
        yield b"x" * 300_000
        yield b"y" * 300_000

    response = await _send(
        "PUT",
        "/api/privacy",
        headers={**CLIENT_HEADERS, "content-type": "application/json"},
        content=body(),
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}


@pytest.mark.asyncio
async def test_small_chunked_body_still_reaches_route() -> None:
    async def body() -> AsyncIterator[bytes]:
        yield b'{"mode":'
        yield b'"NOT_A_MODE"}'

    response = await _send(
        "PUT",
        "/api/privacy",
        headers={**CLIENT_HEADERS, "content-type": "application/json"},
        content=body(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_non_numeric_content_length_is_rejected() -> None:
    response = await _send(
        "PUT",
        "/api/privacy",
        headers={**CLIENT_HEADERS, "content-length": "abc", "content-type": "application/json"},
        content=b"{}",
    )
    assert response.status_code in {400, 413}


@pytest.mark.asyncio
async def test_guard_rejection_does_not_echo_request_data() -> None:
    marker = "marker-secret-value"
    response = await _send(
        "PUT",
        "/api/privacy",
        host="evil.example",
        headers={"origin": f"https://{marker}.example", "authorization": "******"},
        content=b"{}",
    )
    assert response.status_code == 403
    assert marker not in response.text
    assert "evil.example" not in response.text


ASSISTANT_ROUTES = ["/api/assistant/respond", "/api/assistant/stream"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ASSISTANT_ROUTES)
@pytest.mark.parametrize(
    ("host", "headers"),
    [
        ("127.0.0.1:8000", {}),
        ("127.0.0.1:8000", {"origin": "https://attacker.example"}),
        ("attacker.example", dict(CLIENT_HEADERS)),
        ("127.0.0.1.attacker.example:8000", dict(CLIENT_HEADERS)),
        ("localhost:8000@attacker.example", dict(CLIENT_HEADERS)),
        ("127.0.0.1:8000", {**CLIENT_HEADERS, "origin": "http://localhost.attacker.example"}),
    ],
)
async def test_assistant_routes_reject_rebinding_and_cross_site_posts(
    path: str, host: str, headers: dict[str, str]
) -> None:
    response = await _send(
        "POST",
        path,
        host=host,
        headers={**headers, "content-type": "application/json"},
        content=b'{"query":"What is due today?"}',
    )
    assert response.status_code == 403
    assert "due today" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ASSISTANT_ROUTES)
async def test_assistant_routes_cap_declared_and_chunked_bodies(path: str) -> None:
    declared = await _send(
        "POST",
        path,
        headers={**CLIENT_HEADERS, "content-type": "application/json"},
        content=b'{"query":"' + b"a" * 600_000 + b'"}',
    )
    assert declared.status_code == 413

    async def body() -> AsyncIterator[bytes]:
        yield b'{"query":"' + b"a" * 300_000
        yield b"a" * 300_000 + b'"}'

    chunked = await _send(
        "POST",
        path,
        headers={**CLIENT_HEADERS, "content-type": "application/json"},
        content=body(),
    )
    assert chunked.status_code == 413


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/courses", "/api/privacy", "/health"])
async def test_reads_from_rebound_hosts_are_rejected(path: str) -> None:
    for host in ("attacker.example", "[::1", "127.0.0.1:99999", "localhost:8000, evil.example"):
        response = await _send("GET", path, host=host)
        assert response.status_code in {400, 403}, (path, host)


@pytest.mark.asyncio
async def test_hostile_origin_never_receives_cors_allowance() -> None:
    response = await _send("GET", "/health", headers={"origin": "https://attacker.example"})
    assert "access-control-allow-origin" not in response.headers
    assert response.headers.get("access-control-allow-credentials") is None
