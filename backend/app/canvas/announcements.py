"""Canvas course announcements (discussion topics) retrieval."""

from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.announcements.models import AnnouncementSnapshot
from app.canvas.client import CanvasClient
from app.canvas.courses import _clean_optional_text, _normalize_canvas_id, _normalize_datetime
from app.canvas.exceptions import CanvasResponseError


class _CanvasAnnouncementPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int
    title: str | None = None
    message: str | None = None
    posted_at: datetime | None = None
    delayed_post_at: datetime | None = None
    published: bool | None = None
    html_url: str | None = None
    last_reply_at: datetime | None = None

    @field_validator("id", mode="before")
    @classmethod
    def reject_boolean_id(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Canvas identifiers cannot be boolean")
        return value

    @field_validator("posted_at", "delayed_post_at", "last_reply_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return _normalize_datetime(value)


class CanvasAnnouncementSource:
    """Fetch paginated announcements for one Canvas course."""

    def __init__(self, client: CanvasClient) -> None:
        self._client = client

    async def fetch_course_announcements(
        self, canvas_course_id: str
    ) -> list[AnnouncementSnapshot]:
        course_id = _normalize_canvas_id(canvas_course_id, field_name="course id")
        encoded = quote(course_id, safe="~")
        payloads = await self._client.get_paginated(
            f"/api/v1/courses/{encoded}/discussion_topics",
            params=httpx.QueryParams(
                {
                    "only_announcements": "true",
                    "per_page": "100",
                }
            ),
        )
        return [
            normalize_announcement(payload, canvas_course_id=course_id, index=index)
            for index, payload in enumerate(payloads)
        ]


def normalize_announcement(
    payload: dict[str, Any],
    *,
    canvas_course_id: str,
    index: int = 0,
) -> AnnouncementSnapshot:
    try:
        course_id = _normalize_canvas_id(canvas_course_id, field_name="course id")
        topic = _CanvasAnnouncementPayload.model_validate(payload)
        topic_id = _normalize_canvas_id(topic.id, field_name="announcement id")
    except (ValidationError, ValueError) as exc:
        raise CanvasResponseError(
            f"announcement payload at index {index} failed validation"
        ) from exc
    updated = topic.last_reply_at or topic.posted_at
    return AnnouncementSnapshot(
        canvas_topic_id=topic_id,
        canvas_course_id=course_id,
        title=_clean_optional_text(topic.title),
        message_html=topic.message,
        posted_at=topic.posted_at,
        delayed_post_at=topic.delayed_post_at,
        published=topic.published,
        html_url=_clean_optional_text(topic.html_url),
        canvas_updated_at=updated,
    )
