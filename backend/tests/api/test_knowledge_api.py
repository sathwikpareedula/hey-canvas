"""API tests for /api/knowledge endpoints."""

from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_session
from app.main import app


@pytest.mark.asyncio
async def test_get_knowledge_coverage_endpoint(
    session_factory: sessionmaker[Session],
) -> None:
    def override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/knowledge/coverage")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "courses_total" in data
    assert "focus_courses_total" in data
    assert "courses" in data


@pytest.mark.asyncio
async def test_get_knowledge_status_endpoint() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/knowledge/status")

    assert response.status_code == 200
    data = response.json()
    assert "is_preparing" in data
    assert data["is_preparing"] is False


@pytest.mark.asyncio
async def test_trigger_knowledge_prepare_endpoint() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/knowledge/prepare",
            json={"course_ids": ["non-existent"], "allow_download": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert "accepted" in data
    assert "message" in data
