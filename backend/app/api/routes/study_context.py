"""Local-only bounded study-context APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.services.course_profiles import CourseNotFoundError
from app.services.study_context import StudyContextService
from app.study_context.models import StudyContextUpdate, StudyContextView

router = APIRouter(prefix="/api/study-context", tags=["study-context"])


@router.get("/{course_id}", response_model=StudyContextView)
def get_study_context(
    course_id: Annotated[str, Path(max_length=255)],
    session: Annotated[Session, Depends(get_session)],
) -> StudyContextView:
    try:
        return StudyContextService(session).get(course_id)
    except (CourseNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="course not found") from exc


@router.put("/{course_id}", response_model=StudyContextView)
def put_study_context(
    course_id: Annotated[str, Path(max_length=255)],
    payload: StudyContextUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> StudyContextView:
    try:
        return StudyContextService(session).update(course_id, payload)
    except (CourseNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="course not found") from exc


@router.delete("/{course_id}", status_code=204)
def delete_study_context(
    course_id: Annotated[str, Path(max_length=255)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    try:
        StudyContextService(session).reset(course_id)
    except (CourseNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="course not found") from exc
