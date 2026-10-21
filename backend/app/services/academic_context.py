"""Deterministic composition of course, profile, routing, and study state."""

from sqlalchemy.orm import Session

from app.academic_context.models import AcademicContext, RetrievalEvidenceSlot
from app.course_router.models import CourseRoutingRequest
from app.services.course_profiles import CourseProfileService
from app.services.course_router import CourseRouterService
from app.services.study_context import StudyContextService


class AcademicContextService:
    """Compose local state without retrieval, network, or prompt generation."""

    def __init__(self, session: Session) -> None:
        self._profiles = CourseProfileService(session)
        self._router = CourseRouterService(session)
        self._study = StudyContextService(session)

    def build(self, request: CourseRoutingRequest) -> AcademicContext | None:
        result = self._router.resolve(request)
        if result.course is None:
            return None
        profile = self._profiles.effective_context(result.course.course_id)
        study = self._study.get(result.course.course_id)
        return AcademicContext(
            course_id=result.course.course_id,
            course_name=result.course.course_name,
            course_code=result.course.course_code,
            routing_evidence=result.evidence,
            profile_preferences=profile.preferences,
            course_instructions=profile.course_instructions,
            study_context=study,
            retrieval=RetrievalEvidenceSlot(),
        )
