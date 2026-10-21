import app.main as main_module
import httpx
import pytest
from app.main import app


@pytest.mark.asyncio
async def test_health(monkeypatch: pytest.MonkeyPatch) -> None:
    initialized = False

    def initialize_test_database() -> None:
        nonlocal initialized
        initialized = True

    monkeypatch.setattr(main_module, "initialize_database", initialize_test_database)
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "uta-academic-copilot"}
    assert initialized is True
