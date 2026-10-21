"""Typed structured study-session contracts."""

from enum import StrEnum

from app.assistant_tools.models import AssistantEvidenceReference, AssistantStudyMode
from pydantic import BaseModel, ConfigDict, Field


class StudySessionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class StudyStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    order: int = Field(ge=1, le=50)
    title: str = Field(min_length=1, max_length=200)
    minutes: int = Field(ge=1, le=480)
    status: str = Field(default="pending", max_length=20)


class StudySessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1, max_length=255)
    goal: str = Field(min_length=1, max_length=1000)
    duration_minutes: int = Field(ge=5, le=480)
    topics: tuple[str, ...] = Field(default=(), max_length=20)
    study_mode: AssistantStudyMode = AssistantStudyMode.LEARN
    assignment_ids: tuple[str, ...] = Field(default=(), max_length=20)


class StudySessionView(StudySessionCreate):
    session_id: str
    status: StudySessionStatus
    relevant_evidence: tuple[AssistantEvidenceReference, ...] = Field(default=(), max_length=20)
    steps: tuple[StudyStep, ...] = Field(default=(), max_length=50)
    progress: int = Field(ge=0, le=100)


class StudySessionProgress(BaseModel):
    completed_step: int = Field(ge=1, le=50)

