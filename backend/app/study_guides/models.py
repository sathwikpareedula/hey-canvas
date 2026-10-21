"""Typed, attributable study-guide contracts."""

from app.assistant_tools.models import AssistantEvidenceReference, AssistantStudyMode
from pydantic import BaseModel, ConfigDict, Field


class StudyGuideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1, max_length=255)
    topic: str | None = Field(default=None, max_length=500)
    assignment_id: str | None = Field(default=None, max_length=255)
    document_id: str | None = Field(default=None, max_length=255)
    study_mode: AssistantStudyMode = AssistantStudyMode.REVIEW


class StudyGuide(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=200)
    scope: str = Field(min_length=1, max_length=1000)
    key_concepts: tuple[str, ...] = Field(default=(), max_length=20)
    explanations: tuple[str, ...] = Field(default=(), max_length=20)
    evidence: tuple[AssistantEvidenceReference, ...] = Field(default=(), max_length=20)
    review_checklist: tuple[str, ...] = Field(default=(), max_length=20)
    practice_prompts: tuple[str, ...] = Field(default=(), max_length=20)
    uncertainties: tuple[str, ...] = Field(default=(), max_length=20)
