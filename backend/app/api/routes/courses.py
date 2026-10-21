"""Read-only local course API."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database.announcement_repository import AnnouncementRepository
from app.database.course_repository import CourseRepository
from app.database.session import get_session

router = APIRouter(prefix="/api/courses", tags=["courses"])


class CourseResponse(BaseModel):
    """Stable public representation of a locally persisted course."""

    model_config = ConfigDict(from_attributes=True)

    canvas_course_id: str
    course_code: str | None
    course_name: str | None
    term_canvas_id: str | None
    term_name: str | None
    term_start_at: datetime | None
    term_end_at: datetime | None
    start_at: datetime | None
    end_at: datetime | None
    workflow_state: str | None
    enrollment_state: str | None
    enrollment_type: str | None
    canvas_updated_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_synced_at: datetime


@router.get("", response_model=list[CourseResponse])
def list_courses(session: Annotated[Session, Depends(get_session)]) -> list[CourseResponse]:
    """List locally persisted courses without contacting Canvas."""

    courses = CourseRepository(session).list_all()
    return [CourseResponse.model_validate(course) for course in courses]


class AnnouncementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    canvas_topic_id: str
    title: str | None
    posted_at: datetime | None
    html_url: str | None
    excerpt: str = Field(max_length=1000)


@router.get("/{canvas_course_id}/announcements", response_model=list[AnnouncementResponse])
def list_course_announcements(
    canvas_course_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> list[AnnouncementResponse]:
    if not CourseRepository(session).list_syncable(canvas_course_ids=[canvas_course_id]):
        raise HTTPException(status_code=404, detail="course not found locally")
    rows = AnnouncementRepository(session).list_for_course(canvas_course_id)
    responses: list[AnnouncementResponse] = []
    for row in rows:
        excerpt = (row.body_text or row.title or "")[:1000]
        responses.append(
            AnnouncementResponse(
                canvas_topic_id=row.canvas_topic_id,
                title=row.title,
                posted_at=row.posted_at,
                html_url=row.html_url,
                excerpt=excerpt,
            )
        )
    return responses

