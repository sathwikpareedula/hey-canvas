from collections.abc import Iterator

import httpx
import pytest
from app.canvas.client import CanvasClient
from app.canvas.exceptions import (
    CanvasAPIError,
    CanvasAuthenticationError,
    CanvasConfigurationError,
    CanvasRateLimitError,
    CanvasResponseError,
)
from pydantic import SecretStr


def make_client(
    handler: httpx.MockTransport,
    *,
    max_attempts: int = 3,
) -> CanvasClient:
    return CanvasClient(
        base_url="https://canvas.example.edu",
        token=SecretStr("unit-test-secret"),
        max_attempts=max_attempts,
        backoff_base_seconds=0,
        transport=handler,
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://canvas.example.edu",
        "https://user:password@canvas.example.edu",
        "https://canvas.example.edu/courses",
        "https://canvas.example.edu?token=unsafe",
    ],
)
def test_base_url_rejects_unsafe_non_origin_values(base_url: str) -> None:
    with pytest.raises(CanvasConfigurationError):
        CanvasClient(base_url=base_url, token=SecretStr("unit-test-secret"))


def test_retry_attempts_have_a_configuration_upper_bound() -> None:
    with pytest.raises(CanvasConfigurationError, match="between 1 and 10"):
        CanvasClient(
            base_url="https://canvas.example.edu",
            token=SecretStr("unit-test-secret"),
            max_attempts=11,
        )


@pytest.mark.asyncio
async def test_authorization_header_is_sent_without_exposing_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer unit-test-secret"
        assert request.headers["Accept"] == "application/json+canvas-string-ids"
        assert request.extensions["timeout"] == {
            "connect": 20.0,
            "read": 20.0,
            "write": 20.0,
            "pool": 20.0,
        }
        return httpx.Response(200, json={"id": 42})

    async with make_client(httpx.MockTransport(handler)) as client:
        payload = await client.get_json("/api/v1/users/self/profile")

    assert payload == {"id": 42}
    assert "unit-test-secret" not in repr(client)


@pytest.mark.asyncio
async def test_pagination_follows_same_origin_next_link() -> None:
    requested_pages: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_pages.append(request.url.params.get("page"))
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"id": 2}])
        headers = {
            "Link": '<https://canvas.example.edu/api/v1/courses?page=2>; rel="next"'
        }
        return httpx.Response(200, json=[{"id": 1}], headers=headers)

    async with make_client(httpx.MockTransport(handler)) as client:
        courses = await client.get_paginated("/api/v1/courses", params={"per_page": 100})

    assert courses == [{"id": 1}, {"id": 2}]
    assert requested_pages == [None, "2"]


@pytest.mark.asyncio
async def test_pagination_rejects_cross_origin_next_link() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        headers = {"Link": '<https://attacker.example/api/v1/courses?page=2>; rel="next"'}
        return httpx.Response(200, json=[{"id": 1}], headers=headers)

    async with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(CanvasResponseError, match="leave the configured origin"):
            await client.get_paginated("/api/v1/courses")


@pytest.mark.asyncio
async def test_redirect_is_not_followed_or_sent_authorization() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://attacker.example/collect"})

    async with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(CanvasAPIError, match="automatic redirects are disabled"):
            await client.get_json("/api/v1/courses")

    assert len(requests) == 1
    assert requests[0].url.host == "canvas.example.edu"


@pytest.mark.asyncio
async def test_authentication_failure_is_safe() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized unit-test-secret"})

    async with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(CanvasAuthenticationError) as caught:
            await client.get_json("/api/v1/courses")

    assert "unit-test-secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_authentication_failure_does_not_log_response_body_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bearer unit-test-secret"})

    caplog.set_level("INFO")
    async with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(CanvasAuthenticationError):
            await client.get_json("/api/v1/courses")

    assert "unit-test-secret" not in caplog.text


@pytest.mark.asyncio
async def test_rate_limit_retries_are_bounded() -> None:
    attempts: Iterator[int] = iter(range(3))
    seen = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        next(attempts)
        return httpx.Response(429, json={"message": "slow down"}, headers={"Retry-After": "0"})

    async with make_client(httpx.MockTransport(handler), max_attempts=3) as client:
        with pytest.raises(CanvasRateLimitError) as caught:
            await client.get_json("/api/v1/courses")

    assert seen == 3
    assert caught.value.retry_after_seconds == 0


@pytest.mark.asyncio
async def test_retry_after_is_capped_at_one_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    delays: list[float] = []
    seen = 0

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        if seen == 1:
            return httpx.Response(429, headers={"Retry-After": "999999"})
        return httpx.Response(200, json={"id": 1})

    monkeypatch.setattr("app.canvas.client.asyncio.sleep", fake_sleep)
    async with make_client(httpx.MockTransport(handler)) as client:
        await client.get_json("/api/v1/users/self/profile")

    assert delays == [60.0]


@pytest.mark.asyncio
async def test_transient_failure_is_retried() -> None:
    seen = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        if seen == 1:
            return httpx.Response(503, json={"message": "temporarily unavailable"})
        return httpx.Response(200, json={"id": 1})

    async with make_client(httpx.MockTransport(handler)) as client:
        payload = await client.get_json("/api/v1/users/self/profile")

    assert payload == {"id": 1}
    assert seen == 2


@pytest.mark.asyncio
async def test_malformed_json_is_rejected() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    async with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(CanvasResponseError, match="malformed JSON"):
            await client.get_json("/api/v1/courses")


@pytest.mark.asyncio
async def test_list_endpoint_requires_an_array_of_objects() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 1})

    async with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(CanvasResponseError, match="unexpected JSON shape"):
            await client.get_paginated("/api/v1/courses")
