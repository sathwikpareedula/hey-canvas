"""Canvas assignment retrieval and defensive normalization."""

from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.assignments.models import AssignmentSnapshot
from app.canvas.client import CanvasClient
from app.canvas.courses import _clean_optional_text, _normalize_canvas_id, _normalize_datetime
from app.canvas.exceptions import CanvasResponseError


class _CanvasAssignmentPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int
    course_id: str | int | None = None
    name: str | None = None
    description: str | None = None
    due_at: datetime | None = None
    unlock_at: datetime | None = None
    lock_at: datetime | None = None
    points_possible: float | None = None
    submission_types: list[str] | None = None
    workflow_state: str | None = None
    html_url: str | None = None
    published: bool | None = None
    has_submitted_submissions: bool | None = None
    updated_at: datetime | None = None
    rubric: list[dict[str, Any]] | None = None

    @field_validator("id", "course_id", mode="before")
    @classmethod
    def reject_boolean_ids(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas identifiers cannot be boolean")
        return value

    @field_validator("due_at", "unlock_at", "lock_at", "updated_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class CanvasAssignmentSource:
    """Fetch assignments for one known Canvas course."""

    def __init__(self, client: CanvasClient) -> None:
        self._client = client

    async def fetch_course_assignments(self, canvas_course_id: str) -> list[AssignmentSnapshot]:
        course_id = _normalize_canvas_id(canvas_course_id, field_name="course id")
        encoded_course_id = quote(course_id, safe="~")
        payloads = await self._client.get_paginated(
            f"/api/v1/courses/{encoded_course_id}/assignments",
            params=httpx.QueryParams({"per_page": "100"}),
        )
        return [
            normalize_assignment(payload, canvas_course_id=course_id, index=index)
            for index, payload in enumerate(payloads)
        ]


def normalize_assignment(
    payload: dict[str, Any],
    *,
    canvas_course_id: str,
    index: int = 0,
) -> AssignmentSnapshot:
    """Normalize one assignment without echoing HTML or payload content in errors."""

    try:
        course_id = _normalize_canvas_id(canvas_course_id, field_name="course id")
        assignment = _CanvasAssignmentPayload.model_validate(payload)
        assignment_id = _normalize_canvas_id(assignment.id, field_name="assignment id")
        if assignment.course_id is not None:
            response_course_id = _normalize_canvas_id(
                assignment.course_id,
                field_name="assignment course id",
            )
            if response_course_id != course_id:
                raise ValueError("assignment course id does not match requested course")
    except (ValidationError, ValueError, TypeError) as exc:
        raise CanvasResponseError(
            f"Canvas assignment object at index {index} is malformed"
        ) from exc

    submission_types = tuple(
        value
        for value in (_clean_optional_text(item) for item in assignment.submission_types or [])
        if value is not None
    )
    return AssignmentSnapshot(
        canvas_assignment_id=assignment_id,
        canvas_course_id=course_id,
        name=_clean_optional_text(assignment.name),
        description_html=assignment.description,
        due_at=assignment.due_at,
        unlock_at=assignment.unlock_at,
        lock_at=assignment.lock_at,
        points_possible=assignment.points_possible,
        submission_types=submission_types,
        workflow_state=_clean_optional_text(assignment.workflow_state),
        html_url=_clean_optional_text(assignment.html_url),
        published=assignment.published,
        has_submitted_submissions=assignment.has_submitted_submissions,
        canvas_updated_at=assignment.updated_at,
        rubric=assignment.rubric,
    )

