"""Structured study-guide API."""

from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.assistant_tools.models import AssistantEvidenceReference
from app.assistant_tools.service import AcademicToolService
from app.config import get_settings
from app.database.session import get_session
from app.services.course_profiles import CourseNotFoundError, CourseProfileService
from app.study_guides.models import StudyGuide, StudyGuideRequest
from app.study_guides.service import StudyGuideService

router = APIRouter(prefix="/api/study-guides", tags=["study-guides"])


@router.post("", response_model=StudyGuide)
def build_study_guide(
    request: StudyGuideRequest,
    session: Annotated[Session, Depends(get_session)],
) -> StudyGuide:
    evidence: tuple[AssistantEvidenceReference, ...] = ()
    settings = get_settings()
    if request.document_id:
        evidence = tuple(
            AssistantEvidenceReference(
                authority=item.authority,
                identifier=item.canvas_file_id,
                locator=item.heading,
            )
            for item in AcademicToolService(
                session,
                academic_timezone=ZoneInfo(settings.academic_timezone),
            ).get_document_evidence(request.document_id)
        )
    profile = CourseProfileService(session)
    try:
        course = profile.get(request.course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="course not found") from exc
    return StudyGuideService().build(
        request,
        course_name=course.course_name,
        evidence=evidence,
    )
