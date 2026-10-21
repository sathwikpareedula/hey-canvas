"""Local-only deterministic change history APIs."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.canvas.courses import _normalize_canvas_id
from app.changes.models import ChangeEventView, ChangeSummary
from app.database.session import get_session
from app.services.change_query import ChangeQueryService

router = APIRouter(prefix="/api/changes", tags=["changes"])


@router.get("", response_model=list[ChangeEventView])
def list_changes(
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
    entity_type: Annotated[str | None, Query(max_length=50)] = None,
    event_type: Annotated[str | None, Query(max_length=100)] = None,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ChangeEventView]:
    if since is not None and (since.tzinfo is None or since.utcoffset() is None):
        raise HTTPException(status_code=422, detail="since must include a UTC offset")
    normalized_course = None
    if course_id is not None:
        try:
            normalized_course = _normalize_canvas_id(course_id, field_name="course_id")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="course_id is invalid") from exc
    return ChangeQueryService(session).list_changes(
        course_id=normalized_course,
        entity_type=entity_type,
        event_type=event_type,
        since=since,
        limit=limit,
    )


@router.get("/summary", response_model=ChangeSummary)
def get_change_summary(
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
    since: datetime | None = None,
) -> ChangeSummary:
    if since is not None and (since.tzinfo is None or since.utcoffset() is None):
        raise HTTPException(status_code=422, detail="since must include a UTC offset")
    normalized_course = None
    if course_id is not None:
        try:
            normalized_course = _normalize_canvas_id(course_id, field_name="course_id")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="course_id is invalid") from exc
    return ChangeQueryService(session).summary(course_id=normalized_course, since=since)
