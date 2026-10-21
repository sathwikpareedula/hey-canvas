"""Privacy mode and per-course AI policy APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.privacy.models import (
    CourseAIPolicyUpdate,
    CourseAIPolicyView,
    PrivacySettingsUpdate,
    PrivacySettingsView,
)
from app.privacy.service import PrivacyService

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


@router.get("", response_model=PrivacySettingsView)
def get_privacy(session: Annotated[Session, Depends(get_session)]) -> PrivacySettingsView:
    return PrivacyService(session).settings()


@router.put("", response_model=PrivacySettingsView)
def update_privacy(
    request: PrivacySettingsUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> PrivacySettingsView:
    return PrivacyService(session).update_settings(request)


@router.get("/courses/{course_id}", response_model=CourseAIPolicyView)
def get_course_policy(
    course_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> CourseAIPolicyView:
    return PrivacyService(session).policy(course_id)


@router.put("/courses/{course_id}", response_model=CourseAIPolicyView)
def put_course_policy(
    course_id: str,
    request: CourseAIPolicyUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> CourseAIPolicyView:
    try:
        return PrivacyService(session).set_policy(course_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
