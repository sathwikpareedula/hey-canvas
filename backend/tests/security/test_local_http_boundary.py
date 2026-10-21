"""Adversarial checks for the browser-to-local-service trust boundary."""

from collections.abc import Callable, Iterator

import httpx
import pytest
from app.api import assistant_stream_errors
from app.api.routes import assistant as assistant_routes
from app.config import get_settings
from app.database.session import get_session
from app.main import app
from app.security.local_api_guard import LOCAL_CLIENT_HEADER, LOCAL_CLIENT_VALUE
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture(autouse=True)
def _enable_local_api_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_API_GUARD_ENABLED", "true")
    get_settings.cache_clear()


def make_session_override(
    session_factory: sessionmaker[Session],
) -> Callable[[], Iterator[Session]]:
    def override() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    return override


@pytest.mark.asyncio
async def test_untrusted_host_is_rejected_before_routing() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://attacker.example",
    ) as client:
        response = await client.get("/health")

    assert response.status_code in {400, 403}


@pytest.mark.asyncio
async def test_loopback_host_remains_available() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8000",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "uta-academic-copilot"}


@pytest.mark.asyncio
async def test_direct_cross_origin_preflight_is_not_authorized() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8000",
    ) as client:
        response = await client.options(
            "/api/privacy",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code >= 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_untrusted_origin_cannot_change_local_privacy_mode(
    session_factory: sessionmaker[Session],
) -> None:
    app.dependency_overrides[get_session] = make_session_override(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
        ) as client:
            response = await client.put(
                "/api/privacy",
                headers={
                    "Origin": "https://attacker.example",
                    LOCAL_CLIENT_HEADER: LOCAL_CLIENT_VALUE,
                },
                json={"mode": "OPTIONAL_CLOUD_BYO"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code in {400, 403}


@pytest.mark.asyncio
async def test_mutating_api_without_client_header_is_blocked() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8000",
    ) as client:
        response = await client.post(
            "/api/assistant/respond",
            json={"query": "hello"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_oversized_json_body_is_rejected_at_transport_boundary(
    session_factory: sessionmaker[Session],
) -> None:
    app.dependency_overrides[get_session] = make_session_override(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
        ) as client:
            response = await client.put(
                "/api/privacy",
                content=b'{"mode":"' + (b"A" * 1_000_000) + b'"}',
                headers={
                    "Content-Type": "application/json",
                    LOCAL_CLIENT_HEADER: LOCAL_CLIENT_VALUE,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_chunked_oversized_body_is_rejected_without_content_length(
    session_factory: sessionmaker[Session],
) -> None:
    from starlette.requests import Request

    from app.security.request_body_limit import RequestBodyTooLarge, wrap_request_receive

    chunks = [b"x" * 400_000, b"y" * 200_000]
    index = 0

    async def receive() -> dict[str, object]:
        nonlocal index
        if index >= len(chunks):
            return {"type": "http.request", "body": b"", "more_body": False}
        body = chunks[index]
        index += 1
        more = index < len(chunks)
        return {"type": "http.request", "body": body, "more_body": more}

    scope = {
        "type": "http",
        "method": "PUT",
        "path": "/api/privacy",
        "headers": [],
    }
    request = wrap_request_receive(Request(scope, receive), 512_000)
    with pytest.raises(RequestBodyTooLarge):
        while True:
            message = await request.receive()
            if message["type"] == "http.request" and not message.get("more_body"):
                break

    app.dependency_overrides[get_session] = make_session_override(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
        ) as client:
            response = await client.put(
                "/api/privacy",
                content=b"0" * 600_000,
                headers={
                    "Content-Type": "application/json",
                    LOCAL_CLIENT_HEADER: LOCAL_CLIENT_VALUE,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_assistant_response_does_not_reflect_internal_exception_text(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = "credential-marker C:\\private\\academic.db"

    async def no_prepare(*_: object, **__: object) -> None:
        return None

    async def fail_orchestrator(*_: object, **__: object) -> object:
        raise RuntimeError(marker)

    monkeypatch.setattr(assistant_routes, "prepare_material_for_request", no_prepare)
    monkeypatch.setattr(assistant_routes, "run_orchestrator", fail_orchestrator)
    app.dependency_overrides[get_session] = make_session_override(session_factory)
    app.dependency_overrides[assistant_routes.get_model_provider] = lambda: object()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
        ) as client:
            response = await client.post(
                "/api/assistant/respond",
                headers={LOCAL_CLIENT_HEADER: LOCAL_CLIENT_VALUE},
                json={"query": "Explain a synthetic concept."},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert marker not in response.text
    assert "academic.db" not in response.text


def test_assistant_stream_error_fallback_is_sanitized() -> None:
    marker = "credential-marker C:\\private\\academic.db"

    rendered = assistant_stream_errors.format_assistant_stream_error(RuntimeError(marker))

    assert marker not in rendered
    assert "academic.db" not in rendered
