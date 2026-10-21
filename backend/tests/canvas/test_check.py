import httpx
import pytest
from app.canvas.check import verify_canvas_connection
from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasResponseError
from pydantic import SecretStr


@pytest.mark.asyncio
async def test_connection_check_returns_only_non_secret_identity() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 123, "name": "Private Name"})

    async with CanvasClient(
        base_url="https://canvas.example.edu",
        token=SecretStr("unit-test-secret"),
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await verify_canvas_connection(client)

    assert result.user_id == "123"
    assert "Private Name" not in repr(result)


@pytest.mark.asyncio
async def test_connection_check_rejects_missing_user_id() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "Private Name"})

    async with CanvasClient(
        base_url="https://canvas.example.edu",
        token=SecretStr("unit-test-secret"),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(CanvasResponseError, match="did not contain a user ID"):
            await verify_canvas_connection(client)
