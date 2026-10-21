"""Read-only local assignment API."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas.assignments import AssignmentResponse
from app.canvas.courses import _normalize_canvas_id
from app.database.assignment_repository import AssignmentRepository
from app.database.session import get_session

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


@router.get("", response_model=list[AssignmentResponse])
def list_assignments(
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
) -> list[AssignmentResponse]:
    """Query persisted assignments; lower bounds are inclusive and upper bounds exclusive."""

    normalized_course_id = _validate_course_filter(course_id)
    lower = _validate_query_datetime(from_at, name="from")
    upper = _validate_query_datetime(to_at, name="to")
    if lower is not None and upper is not None and lower >= upper:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    assignments = AssignmentRepository(session).list_all(
        canvas_course_id=normalized_course_id,
        from_at=lower,
        to_at=upper,
    )
    return [AssignmentResponse.model_validate(item) for item in assignments]


def _validate_course_filter(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return _normalize_canvas_id(value, field_name="course id")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="course_id is invalid") from exc


def _validate_query_datetime(value: datetime | None, *, name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(status_code=422, detail=f"{name} must include a timezone offset")
    return value.astimezone(UTC)

