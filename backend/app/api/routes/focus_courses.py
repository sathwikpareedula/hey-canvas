"""Persistent focus-course scope APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.focus_courses.models import FocusCourseMutation, FocusCourseSelection, FocusCourseView
from app.focus_courses.service import FocusCourseService

router = APIRouter(prefix="/api/focus-courses", tags=["focus-courses"])


@router.get("", response_model=tuple[FocusCourseView, ...])
def list_focus_courses(
    session: Annotated[Session, Depends(get_session)],
) -> tuple[FocusCourseView, ...]:
    return FocusCourseService(session).list()


@router.get("/suggestions", response_model=tuple[str, ...])
def suggest_focus_courses(
    session: Annotated[Session, Depends(get_session)],
) -> tuple[str, ...]:
    return FocusCourseService(session).suggested()


@router.put("", response_model=tuple[FocusCourseView, ...])
def replace_focus_courses(
    request: FocusCourseSelection,
    session: Annotated[Session, Depends(get_session)],
) -> tuple[FocusCourseView, ...]:
    try:
        return FocusCourseService(session).replace(request.course_ids)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=FocusCourseView)
def add_focus_course(
    request: FocusCourseMutation,
    session: Annotated[Session, Depends(get_session)],
) -> FocusCourseView:
    try:
        return FocusCourseService(session).add(request.course_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{course_id}", response_model=tuple[FocusCourseView, ...])
def remove_focus_course(
    course_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> tuple[FocusCourseView, ...]:
    try:
        return FocusCourseService(session).remove(course_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
