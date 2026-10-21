"""Typed source-aware academic context contracts."""

from enum import StrEnum

from pydantic import BaseModel

from app.course_profiles.models import CourseStudyPreferences
from app.course_router.models import ResolutionEvidence
from app.study_context.models import StudyContextView


class ContextAuthority(StrEnum):
    CANVAS_TRUTH = "canvas_truth"
    USER_CONFIGURATION = "user_configuration"
    USER_PERSONAL_STATE = "user_personal_state"
    ROUTING_DECISION = "routing_decision"
    FUTURE_RETRIEVAL = "future_retrieval"
    PROFESSOR_MATERIAL = "professor_material"


class RetrievalEvidenceSlot(BaseModel):
    """State of the optional provenance-backed retrieval injection boundary."""

    available: bool = False
    authority: ContextAuthority = ContextAuthority.FUTURE_RETRIEVAL


class AcademicContext(BaseModel):
    course_id: str
    course_name: str | None
    course_code: str | None
    routing_evidence: tuple[ResolutionEvidence, ...]
    profile_preferences: CourseStudyPreferences
    course_instructions: str | None
    study_context: StudyContextView
    retrieval: RetrievalEvidenceSlot
