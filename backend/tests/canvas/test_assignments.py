from datetime import UTC, datetime

import httpx
import pytest
from app.canvas.assignments import CanvasAssignmentSource, normalize_assignment
from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasResponseError
from pydantic import SecretStr

from tests.factories import canvas_assignment_payload


def make_client(handler: httpx.MockTransport) -> CanvasClient:
    return CanvasClient(
        base_url="https://canvas.example.edu",
        token=SecretStr("unit-test-secret"),
        backoff_base_seconds=0,
        transport=handler,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 3])
async def test_fetches_one_or_multiple_assignments(count: int) -> None:
    payloads = [canvas_assignment_payload(str(index)) for index in range(1, count + 1)]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/courses/101/assignments"
        assert request.url.params["per_page"] == "100"
        return httpx.Response(200, json=payloads)

    async with make_client(httpx.MockTransport(handler)) as client:
        assignments = await CanvasAssignmentSource(client).fetch_course_assignments("101")

    assert [item.canvas_assignment_id for item in assignments] == [
        str(index) for index in range(1, count + 1)
    ]


@pytest.mark.asyncio
async def test_assignment_pagination_and_empty_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json=[canvas_assignment_payload()],
            headers={
                "Link": (
                    '<https://canvas.example.edu/api/v1/courses/101/assignments?page=2>; '
                    'rel="next"'
                )
            },
        )

    async with make_client(httpx.MockTransport(handler)) as client:
        assignments = await CanvasAssignmentSource(client).fetch_course_assignments("101")

    assert len(assignments) == 1


def test_missing_optional_fields_and_null_due_date() -> None:
    assignment = normalize_assignment({"id": "501", "due_at": None}, canvas_course_id="101")

    assert assignment.canvas_assignment_id == "501"
    assert assignment.due_at is None
    assert assignment.description_html is None
    assert assignment.submission_types == ()


@pytest.mark.parametrize("assignment_id", ["900719925474099312345", 9_007_199_254_740_993])
def test_string_and_large_assignment_ids_are_preserved(assignment_id: str | int) -> None:
    assignment = normalize_assignment(
        canvas_assignment_payload(assignment_id),
        canvas_course_id="101",
    )

    assert assignment.canvas_assignment_id == str(assignment_id)


@pytest.mark.parametrize("assignment_id", [None, "", True, "has whitespace", {"bad": "id"}])
def test_malformed_and_boolean_assignment_ids_are_rejected(assignment_id: object) -> None:
    payload = canvas_assignment_payload()
    payload["id"] = assignment_id
    payload["description"] = "secret-description-marker"

    with pytest.raises(CanvasResponseError, match="assignment object at index 7") as caught:
        normalize_assignment(payload, canvas_course_id="101", index=7)

    assert "secret-description-marker" not in str(caught.value)


def test_html_is_preserved_as_untrusted_text_and_submission_types_remain_multiple() -> None:
    html = '<script>alert("never execute")</script><p>Instructions</p>'
    assignment = normalize_assignment(
        canvas_assignment_payload(description=html),
        canvas_course_id="101",
    )

    assert assignment.description_html == html
    assert assignment.submission_types == ("online_upload", "online_text_entry")
    assert assignment.rubric == [
        {"id": "criterion-1", "description": "Correctness", "points": 10}
    ]


def test_assignment_timestamps_are_absolute_utc_instants() -> None:
    assignment = normalize_assignment(canvas_assignment_payload(), canvas_course_id="101")

    assert assignment.due_at == datetime(2026, 10, 2, 4, 59, tzinfo=UTC)
    assert assignment.unlock_at is not None
    assert assignment.unlock_at.tzinfo == UTC


def test_response_course_id_must_match_requested_course() -> None:
    with pytest.raises(CanvasResponseError, match="malformed"):
        normalize_assignment(canvas_assignment_payload(course_id="999"), canvas_course_id="101")
