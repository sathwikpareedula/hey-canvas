"""Read-only local course-module APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas.modules import CourseModuleResponse
from app.canvas.courses import _normalize_canvas_id
from app.database.session import get_session
from app.services.course_structure import CourseStructureService

router = APIRouter(tags=["modules"])


@router.get("/api/modules", response_model=list[CourseModuleResponse])
def list_modules(
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
) -> list[CourseModuleResponse]:
    """Return locally persisted module trees; course_id is a Canvas course ID."""

    return CourseStructureService(session).list_modules(
        canvas_course_id=_validate_course_id(course_id) if course_id is not None else None
    )


@router.get(
    "/api/courses/{course_id}/modules",
    response_model=list[CourseModuleResponse],
)
def list_course_modules(
    course_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> list[CourseModuleResponse]:
    """Return one Canvas course's locally persisted ordered structure."""

    return CourseStructureService(session).list_modules(
        canvas_course_id=_validate_course_id(course_id)
    )


def _validate_course_id(value: str) -> str:
    try:
        return _normalize_canvas_id(value, field_name="course id")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="course_id is invalid") from exc
