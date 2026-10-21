"""Typed study-context contracts with bounded personal state."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CONTEXT_ITEMS = 20


class StudyMode(StrEnum):
    BALANCED = "balanced"
    REVIEW = "review"
    PRACTICE = "practice"
    EXAM_PREP = "exam_prep"


class StudyContextUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_topic: str | None = Field(default=None, max_length=255)
    assignment_id: str | None = Field(default=None, max_length=255)
    study_mode: StudyMode = StudyMode.BALANCED
    starting_point: str | None = Field(default=None, max_length=255)
    concepts_covered: list[str] = Field(default_factory=list, max_length=MAX_CONTEXT_ITEMS)
    topics_to_revisit: list[str] = Field(default_factory=list, max_length=MAX_CONTEXT_ITEMS)
    study_note: str | None = Field(default=None, max_length=2000)

    @field_validator("concepts_covered", "topics_to_revisit")
    @classmethod
    def validate_items(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values]
        if any(not item or len(item) > 255 for item in cleaned):
            raise ValueError("study context items must be non-empty and at most 255 characters")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("study context items must be unique")
        return cleaned


class StudyContextView(StudyContextUpdate):
    course_id: str
    course_name: str | None
    has_context: bool
    created_at: datetime | None
    updated_at: datetime | None
