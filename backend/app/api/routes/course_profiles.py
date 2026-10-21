"""Local-only course profile and study preference APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.course_profiles.models import (
    CourseProfileUpdate,
    CourseProfileView,
    EffectiveCourseContext,
)
from app.database.session import get_session
from app.services.course_profiles import CourseNotFoundError, CourseProfileService

router = APIRouter(prefix="/api/course-profiles", tags=["course-profiles"])


@router.get("", response_model=list[CourseProfileView])
def list_course_profiles(
    session: Annotated[Session, Depends(get_session)],
) -> list[CourseProfileView]:
    return CourseProfileService(session).list()


@router.get("/{course_id}", response_model=CourseProfileView)
def get_course_profile(
    course_id: Annotated[str, Path(max_length=255)],
    session: Annotated[Session, Depends(get_session)],
) -> CourseProfileView:
    try:
        return CourseProfileService(session).get(course_id)
    except (CourseNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="course not found") from exc


@router.put("/{course_id}", response_model=CourseProfileView)
def put_course_profile(
    course_id: Annotated[str, Path(max_length=255)],
    payload: CourseProfileUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> CourseProfileView:
    try:
        return CourseProfileService(session).upsert(course_id, payload)
    except (CourseNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="course not found") from exc


@router.delete("/{course_id}", status_code=204)
def delete_course_profile(
    course_id: Annotated[str, Path(max_length=255)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    try:
        CourseProfileService(session).delete(course_id)
    except (CourseNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="course not found") from exc


@router.get("/{course_id}/effective-context", response_model=EffectiveCourseContext)
def get_effective_course_context(
    course_id: Annotated[str, Path(max_length=255)],
    session: Annotated[Session, Depends(get_session)],
) -> EffectiveCourseContext:
    try:
        return CourseProfileService(session).effective_context(course_id)
    except (CourseNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="course not found") from exc
