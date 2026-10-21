from datetime import UTC, datetime

import httpx
import pytest
from app.canvas.client import CanvasClient
from app.canvas.courses import CanvasCourseSource, normalize_course
from app.canvas.exceptions import (
    CanvasAuthenticationError,
    CanvasResponseError,
)
from pydantic import SecretStr

from tests.factories import canvas_course_payload


def make_client(handler: httpx.MockTransport, *, max_attempts: int = 3) -> CanvasClient:
    return CanvasClient(
        base_url="https://canvas.example.edu",
        token=SecretStr("unit-test-secret"),
        max_attempts=max_attempts,
        backoff_base_seconds=0,
        transport=handler,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 3])
async def test_fetches_one_or_multiple_courses(count: int) -> None:
    payloads = [canvas_course_payload(str(index)) for index in range(1, count + 1)]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["enrollment_state"] == "active"
        assert request.url.params["state[]"] == "available"
        assert request.url.params["include[]"] == "term"
        assert request.url.params["per_page"] == "100"
        return httpx.Response(200, json=payloads)

    async with make_client(httpx.MockTransport(handler)) as client:
        courses = await CanvasCourseSource(client).fetch_current_courses()

    assert [course.canvas_course_id for course in courses] == [
        str(index) for index in range(1, count + 1)
    ]


@pytest.mark.asyncio
async def test_fetches_paginated_courses() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[canvas_course_payload("2")])
        return httpx.Response(
            200,
            json=[canvas_course_payload("1")],
            headers={
                "Link": '<https://canvas.example.edu/api/v1/courses?page=2>; rel="next"'
            },
        )

    async with make_client(httpx.MockTransport(handler)) as client:
        courses = await CanvasCourseSource(client).fetch_current_courses()

    assert [course.canvas_course_id for course in courses] == ["1", "2"]


@pytest.mark.asyncio
async def test_empty_course_response_is_valid() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    async with make_client(httpx.MockTransport(handler)) as client:
        courses = await CanvasCourseSource(client).fetch_current_courses()

    assert courses == []


def test_optional_course_fields_may_be_missing() -> None:
    course = normalize_course({"id": "101"})

    assert course.canvas_course_id == "101"
    assert course.course_name is None
    assert course.course_code is None
    assert course.term_canvas_id is None
    assert course.enrollment_state is None


@pytest.mark.parametrize("course_id", ["900719925474099312345", 9_007_199_254_740_993])
def test_string_and_very_large_canvas_ids_are_preserved(course_id: str | int) -> None:
    course = normalize_course(canvas_course_payload(course_id))

    assert course.canvas_course_id == str(course_id)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": ""},
        {"id": "has whitespace"},
        {"id": True},
        {"id": "101", "start_at": "2026-01-01T10:00:00"},
        {"id": {"nested": "invalid"}},
    ],
)
def test_malformed_course_object_is_rejected_without_echoing_content(
    payload: dict[str, object],
) -> None:
    secret_marker = "do-not-echo-course-content"
    payload["name"] = secret_marker

    with pytest.raises(CanvasResponseError, match="course object at index 4") as caught:
        normalize_course(payload, index=4)

    assert secret_marker not in str(caught.value)


def test_datetimes_are_normalized_to_aware_utc() -> None:
    course = normalize_course(canvas_course_payload())

    assert course.start_at == datetime(2026, 8, 24, 14, 0, tzinfo=UTC)
    assert course.start_at is not None
    assert course.start_at.utcoffset() is not None
    assert course.term_end_at is not None
    assert course.term_end_at.utcoffset() is not None


def test_active_enrollment_is_selected_deterministically() -> None:
    payload = canvas_course_payload(
        enrollments=[
            {"type": "StudentEnrollment", "enrollment_state": "completed"},
            {"type": "StudentEnrollment", "enrollment_state": "active"},
        ]
    )

    course = normalize_course(payload)

    assert course.enrollment_state == "active"
    assert course.enrollment_type == "StudentEnrollment"


@pytest.mark.asyncio
async def test_course_source_propagates_safe_authentication_failure() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bearer unit-test-secret"})

    async with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(CanvasAuthenticationError) as caught:
            await CanvasCourseSource(client).fetch_current_courses()

    assert "unit-test-secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_course_source_recovers_from_one_transient_failure() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=[canvas_course_payload()])

    async with make_client(httpx.MockTransport(handler)) as client:
        courses = await CanvasCourseSource(client).fetch_current_courses()

    assert len(courses) == 1
    assert calls == 2


@pytest.mark.asyncio
async def test_course_source_keeps_cross_origin_pagination_protection() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[canvas_course_payload()],
            headers={"Link": '<https://attacker.example/courses?page=2>; rel="next"'},
        )

    async with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(CanvasResponseError, match="leave the configured origin"):
            await CanvasCourseSource(client).fetch_current_courses()
