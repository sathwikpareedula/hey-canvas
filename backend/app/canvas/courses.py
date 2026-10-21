"""Canvas course retrieval and defensive normalization."""

from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasResponseError
from app.courses.models import CourseSnapshot

MAX_CANVAS_ID_LENGTH = 255


class _CanvasTermPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int | None = None
    name: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None

    @field_validator("id", mode="before")
    @classmethod
    def reject_boolean_id(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas term id cannot be boolean")
        return value

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class _CanvasEnrollmentPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str | None = None
    enrollment_state: str | None = None
    workflow_state: str | None = None


class _CanvasCoursePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int
    course_code: str | None = None
    name: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    workflow_state: str | None = None
    updated_at: datetime | None = None
    term: _CanvasTermPayload | None = None
    enrollments: list[_CanvasEnrollmentPayload] | None = None

    @field_validator("id", mode="before")
    @classmethod
    def reject_boolean_id(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas course id cannot be boolean")
        return value

    @field_validator("start_at", "end_at", "updated_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class CanvasCourseSource:
    """Fetch current courses from Canvas and return internal course snapshots."""

    def __init__(self, client: CanvasClient) -> None:
        self._client = client

    async def fetch_current_courses(self) -> list[CourseSnapshot]:
        params = httpx.QueryParams(
            [
                ("enrollment_state", "active"),
                ("state[]", "available"),
                ("include[]", "term"),
                ("per_page", "100"),
            ]
        )
        payloads = await self._client.get_paginated("/api/v1/courses", params=params)
        return [normalize_course(payload, index=index) for index, payload in enumerate(payloads)]


def normalize_course(payload: dict[str, Any], *, index: int = 0) -> CourseSnapshot:
    """Validate one Canvas course without leaking its content into errors."""

    try:
        course = _CanvasCoursePayload.model_validate(payload)
        course_id = _normalize_canvas_id(course.id, field_name="course id")
        term_id = (
            _normalize_canvas_id(course.term.id, field_name="term id")
            if course.term is not None and course.term.id is not None
            else None
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise CanvasResponseError(f"Canvas course object at index {index} is malformed") from exc

    enrollment = _select_enrollment(course.enrollments or [])
    return CourseSnapshot(
        canvas_course_id=course_id,
        course_code=_clean_optional_text(course.course_code),
        course_name=_clean_optional_text(course.name),
        term_canvas_id=term_id,
        term_name=_clean_optional_text(course.term.name) if course.term else None,
        term_start_at=course.term.start_at if course.term else None,
        term_end_at=course.term.end_at if course.term else None,
        start_at=course.start_at,
        end_at=course.end_at,
        workflow_state=_clean_optional_text(course.workflow_state),
        enrollment_state=(
            _clean_optional_text(enrollment.enrollment_state or enrollment.workflow_state)
            if enrollment
            else None
        ),
        enrollment_type=_clean_optional_text(enrollment.type) if enrollment else None,
        canvas_updated_at=course.updated_at,
    )


def _normalize_canvas_id(value: str | int, *, field_name: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} cannot be boolean")
    normalized = str(value).strip()
    if not normalized or len(normalized) > MAX_CANVAS_ID_LENGTH:
        raise ValueError(f"{field_name} has an invalid length")
    if any(character.isspace() or ord(character) < 32 for character in normalized):
        raise ValueError(f"{field_name} contains unsupported characters")
    return normalized


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Canvas datetime must include a timezone offset")
    return value.astimezone(UTC)


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _select_enrollment(
    enrollments: list[_CanvasEnrollmentPayload],
) -> _CanvasEnrollmentPayload | None:
    priorities = {"active": 0, "invited": 1, "completed": 2, "inactive": 3}

    def sort_key(enrollment: _CanvasEnrollmentPayload) -> tuple[int, str, str]:
        state = enrollment.enrollment_state or enrollment.workflow_state or ""
        return (
            priorities.get(state, 100),
            state,
            enrollment.type or "",
        )

    return min(enrollments, key=sort_key) if enrollments else None
