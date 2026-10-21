from datetime import UTC

import httpx
import pytest
from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasResponseError
from app.canvas.files import CanvasFileSource, normalize_file
from pydantic import SecretStr

from tests.factories import canvas_file_payload


def test_normalize_complete_canvas_file() -> None:
    metadata = normalize_file(canvas_file_payload())

    assert metadata.snapshot.canvas_file_id == "7001"
    assert metadata.snapshot.folder_id == "9001"
    assert metadata.snapshot.content_type == "application/pdf"
    assert metadata.snapshot.canvas_updated_at is not None
    assert metadata.snapshot.canvas_updated_at.tzinfo == UTC
    assert metadata.download_url is not None


def test_normalize_optional_null_fields_and_content_type_alias() -> None:
    payload = canvas_file_payload(
        folder_id=None,
        display_name=None,
        filename=None,
        size=None,
        created_at=None,
        updated_at=None,
        url=None,
    )
    payload.pop("content-type")
    payload["content_type"] = "text/plain"
    metadata = normalize_file(payload)
    assert metadata.snapshot.folder_id is None
    assert metadata.snapshot.size is None
    assert metadata.download_url is None


@pytest.mark.parametrize("file_id", ["7001", 9_223_372_036_854_775_807])
def test_canvas_file_ids_remain_strings(file_id: str | int) -> None:
    assert normalize_file(canvas_file_payload(file_id)).snapshot.canvas_file_id == str(file_id)


@pytest.mark.parametrize("file_id", [True, "", "bad id"])
def test_malformed_or_boolean_file_id_is_rejected(file_id: object) -> None:
    with pytest.raises(CanvasResponseError, match="malformed"):
        normalize_file(canvas_file_payload(file_id))


@pytest.mark.parametrize("size", [True, -1])
def test_malformed_file_size_is_rejected(size: object) -> None:
    with pytest.raises(CanvasResponseError, match="malformed"):
        normalize_file(canvas_file_payload(size=size))


@pytest.mark.asyncio
async def test_file_source_uses_documented_get_endpoint_without_following_url() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=canvas_file_payload(), request=request)

    async with CanvasClient(
        base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        transport=httpx.MockTransport(handler),
    ) as client:
        metadata = await CanvasFileSource(client).fetch_file("7001")

    assert metadata.snapshot.canvas_file_id == "7001"
    assert [request.url.path for request in requests] == ["/api/v1/files/7001"]
    assert requests[0].method == "GET"


@pytest.mark.asyncio
async def test_file_source_rejects_mismatched_response_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=canvas_file_payload("other"), request=request)

    async with CanvasClient(
        base_url="https://canvas.example.edu",
        token=SecretStr("fake-unit-token"),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(CanvasResponseError, match="did not match"):
            await CanvasFileSource(client).fetch_file("7001")
