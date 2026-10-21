from datetime import UTC, datetime

import httpx
import pytest
from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasResponseError
from app.canvas.modules import CanvasModuleSource, normalize_module, normalize_module_item
from pydantic import SecretStr

from tests.factories import canvas_module_item_payload, canvas_module_payload


def make_client(handler: httpx.MockTransport) -> CanvasClient:
    return CanvasClient(
        base_url="https://canvas.example.edu",
        token=SecretStr("unit-test-secret"),
        backoff_base_seconds=0,
        transport=handler,
    )


@pytest.mark.asyncio
async def test_fetches_paginated_modules_and_uses_inline_items() -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        assert request.url.params.get_list("include[]") == ["items", "content_details"]
        if request.url.params.get("page") == "2":
            return httpx.Response(
                200,
                json=[canvas_module_payload("202", name="Second", items=[])],
            )
        return httpx.Response(
            200,
            json=[
                canvas_module_payload(
                    items=[canvas_module_item_payload()],
                    items_count=1,
                )
            ],
            headers={
                "Link": (
                    '<https://canvas.example.edu/api/v1/courses/101/modules?page=2&'
                    'include%5B%5D=items&include%5B%5D=content_details>; rel="next"'
                )
            },
        )

    async with make_client(httpx.MockTransport(handler)) as client:
        modules = await CanvasModuleSource(client).fetch_course_modules("101")

    assert [module.canvas_module_id for module in modules] == ["201", "202"]
    assert modules[0].items[0].canvas_module_item_id == "1001"
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_omitted_items_use_paginated_fallback_endpoint() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/modules"):
            payload = canvas_module_payload(items=None, items_count=2)
            payload.pop("items")
            return httpx.Response(200, json=[payload])
        if request.url.params.get("page") == "2":
            return httpx.Response(
                200,
                json=[canvas_module_item_payload("1002", title="Overview")],
            )
        return httpx.Response(
            200,
            json=[canvas_module_item_payload()],
            headers={
                "Link": (
                    '<https://canvas.example.edu/api/v1/courses/101/modules/201/items?page=2>; '
                    'rel="next"'
                )
            },
        )

    async with make_client(httpx.MockTransport(handler)) as client:
        modules = await CanvasModuleSource(client).fetch_course_modules("101")

    assert [item.canvas_module_item_id for item in modules[0].items] == ["1001", "1002"]
    assert calls.count("/api/v1/courses/101/modules/201/items") == 2


@pytest.mark.asyncio
async def test_empty_module_list_requires_no_item_requests() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/courses/101/modules"
        return httpx.Response(200, json=[])

    async with make_client(httpx.MockTransport(handler)) as client:
        assert await CanvasModuleSource(client).fetch_course_modules("101") == []


def test_module_optional_fields_and_utc_timestamps() -> None:
    module = normalize_module(
        {"id": "201", "unlock_at": "2026-08-24T00:00:00-05:00", "items": []},
        canvas_course_id="101",
    )

    assert module.name is None
    assert module.position is None
    assert module.prerequisite_module_ids == ()
    assert module.unlock_at == datetime(2026, 8, 24, 5, 0, tzinfo=UTC)


@pytest.mark.parametrize("module_id", ["900719925474099312345", 9_007_199_254_740_993])
def test_string_and_large_module_ids_are_preserved(module_id: str | int) -> None:
    module = normalize_module(
        canvas_module_payload(module_id, items=[]),
        canvas_course_id="101",
    )
    assert module.canvas_module_id == str(module_id)


@pytest.mark.parametrize("module_id", [None, "", True, "has whitespace", {"bad": "id"}])
def test_malformed_and_boolean_module_ids_are_rejected(module_id: object) -> None:
    payload = canvas_module_payload(items=[])
    payload["id"] = module_id
    payload["name"] = "private-module-title-marker"

    with pytest.raises(CanvasResponseError, match="module object at index 4") as caught:
        normalize_module(payload, canvas_course_id="101", index=4)

    assert "private-module-title-marker" not in str(caught.value)


@pytest.mark.parametrize(
    "item_type",
    [
        "File",
        "Assignment",
        "Page",
        "Discussion",
        "Quiz",
        "SubHeader",
        "ExternalUrl",
        "ExternalTool",
        "FutureCanvasType",
    ],
)
def test_known_and_unknown_item_types_are_preserved(item_type: str) -> None:
    item = normalize_module_item(
        canvas_module_item_payload(item_type=item_type),
        canvas_course_id="101",
        canvas_module_id="201",
    )
    assert item.item_type == item_type


def test_module_item_optional_fields_and_order_metadata() -> None:
    item = normalize_module_item(
        {"id": "1001", "type": "SubHeader", "position": 3, "indent": 2},
        canvas_course_id="101",
        canvas_module_id="201",
    )
    assert item.content_id is None
    assert item.position == 3
    assert item.indent == 2


@pytest.mark.parametrize("item_id", [True, None, "", "bad id"])
def test_malformed_and_boolean_item_ids_are_rejected(item_id: object) -> None:
    payload = canvas_module_item_payload()
    payload["id"] = item_id
    payload["external_url"] = "https://do-not-fetch.example/private"
    with pytest.raises(CanvasResponseError, match="module item object") as caught:
        normalize_module_item(
            payload,
            canvas_course_id="101",
            canvas_module_id="201",
        )
    assert "do-not-fetch" not in str(caught.value)


def test_item_urls_and_content_metadata_are_inert_preserved_data() -> None:
    item = normalize_module_item(
        canvas_module_item_payload(
            item_type="ExternalUrl",
            content_id=None,
            external_url="https://untrusted.example/resource",
            page_url="page-slug",
            completion_requirement={"type": "must_view"},
            content_details={"locked_for_user": True},
        ),
        canvas_course_id="101",
        canvas_module_id="201",
    )
    assert item.external_url == "https://untrusted.example/resource"
    assert item.content_id is None
    assert item.completion_requirement == {"type": "must_view"}
    assert item.content_details == {"locked_for_user": True}


def test_item_module_id_must_match_requested_module() -> None:
    with pytest.raises(CanvasResponseError, match="malformed"):
        normalize_module_item(
            canvas_module_item_payload(module_id="999"),
            canvas_course_id="101",
            canvas_module_id="201",
        )


@pytest.mark.parametrize("item_id", ["900719925474099312345", 9_007_199_254_740_993])
def test_string_and_large_module_item_ids_are_preserved(item_id: str | int) -> None:
    item = normalize_module_item(
        canvas_module_item_payload(item_id),
        canvas_course_id="101",
        canvas_module_id="201",
    )
    assert item.canvas_module_item_id == str(item_id)


def test_boolean_content_id_is_rejected() -> None:
    with pytest.raises(CanvasResponseError, match="malformed"):
        normalize_module_item(
            canvas_module_item_payload(content_id=True),
            canvas_course_id="101",
            canvas_module_id="201",
        )


@pytest.mark.asyncio
async def test_external_url_is_never_requested() -> None:
    paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "canvas.example.edu"
        paths.append(request.url.path)
        return httpx.Response(
            200,
            json=[
                canvas_module_payload(
                    items=[
                        canvas_module_item_payload(
                            item_type="ExternalUrl",
                            content_id=None,
                            external_url="https://external.example/never-request",
                        )
                    ]
                )
            ],
        )

    async with make_client(httpx.MockTransport(handler)) as client:
        modules = await CanvasModuleSource(client).fetch_course_modules("101")

    assert paths == ["/api/v1/courses/101/modules"]
    assert modules[0].items[0].external_url == "https://external.example/never-request"
