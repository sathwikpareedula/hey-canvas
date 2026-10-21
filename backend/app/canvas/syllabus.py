"""Canvas course syllabus retrieval."""

import re
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.canvas.client import CanvasClient
from app.canvas.courses import _clean_optional_text, _normalize_canvas_id, _normalize_datetime
from app.canvas.exceptions import CanvasResponseError
from app.syllabus.models import SyllabusLinkedResource, SyllabusSnapshot

_LINK_RE = re.compile(
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]{1,500})</a>',
    re.IGNORECASE,
)


class _CanvasSyllabusCoursePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int
    syllabus_body: str | None = None
    html_url: str | None = None
    updated_at: datetime | None = None

    @field_validator("id", mode="before")
    @classmethod
    def reject_boolean_id(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas course id cannot be boolean")
        return value

    @field_validator("updated_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class CanvasSyllabusSource:
    def __init__(self, client: CanvasClient) -> None:
        self._client = client

    async def fetch_course_syllabus(self, canvas_course_id: str) -> SyllabusSnapshot | None:
        course_id = _normalize_canvas_id(canvas_course_id, field_name="course id")
        encoded = quote(course_id, safe="~")
        payload = await self._client.get_json(
            f"/api/v1/courses/{encoded}",
            params=httpx.QueryParams([("include[]", "syllabus_body")]),
        )
        return normalize_syllabus(payload, canvas_course_id=course_id)


def normalize_syllabus(
    payload: dict[str, Any],
    *,
    canvas_course_id: str,
) -> SyllabusSnapshot | None:
    try:
        course_id = _normalize_canvas_id(canvas_course_id, field_name="course id")
        course = _CanvasSyllabusCoursePayload.model_validate(payload)
        if course.id is not None:
            response_id = _normalize_canvas_id(course.id, field_name="course id")
            if response_id != course_id:
                raise ValueError("syllabus course id mismatch")
    except (ValidationError, ValueError) as exc:
        raise CanvasResponseError("syllabus payload failed validation") from exc
    html = course.syllabus_body
    if not html or not html.strip():
        return SyllabusSnapshot(
            canvas_course_id=course_id,
            syllabus_html=None,
            html_url=_clean_optional_text(course.html_url),
            canvas_updated_at=course.updated_at,
            linked_resources=(),
        )
    links = _extract_links(html)
    return SyllabusSnapshot(
        canvas_course_id=course_id,
        syllabus_html=html,
        html_url=_clean_optional_text(course.html_url),
        canvas_updated_at=course.updated_at,
        linked_resources=links,
    )


def _extract_links(html: str) -> tuple[SyllabusLinkedResource, ...]:
    resources: list[SyllabusLinkedResource] = []
    seen: set[str] = set()
    for match in _LINK_RE.finditer(html):
        url = match.group(1).strip()
        title = _clean_optional_text(match.group(2)) or url
        if not url or url in seen:
            continue
        seen.add(url)
        resources.append(
            SyllabusLinkedResource(title=title[:500], url=url[:2048], resource_type="link")
        )
        if len(resources) >= 50:
            break
    return tuple(resources)
