"""Provider-neutral course profile domain contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TeachingDepth(StrEnum):
    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


class StartingLevel(StrEnum):
    ZERO_KNOWLEDGE = "zero_knowledge"
    COURSE_CONTEXT = "course_context"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ExplanationStyle(StrEnum):
    CONCEPT_FIRST = "concept_first"
    STEP_BY_STEP = "step_by_step"
    WORKED_EXAMPLES = "worked_examples"
    DIAGRAM_AWARE = "diagram_aware"


class AnswerStyle(StrEnum):
    BALANCED = "balanced"
    CONCISE = "concise"
    EXAM_STYLE = "exam_style"


class DetailPreference(StrEnum):
    AUTO = "auto"
    LIGHT = "light"
    DETAILED = "detailed"


class CourseStudyPreferences(BaseModel):
    """Bounded preferences that a future assistant may interpret later."""

    model_config = ConfigDict(extra="forbid")

    teaching_depth: TeachingDepth = TeachingDepth.BALANCED
    starting_level: StartingLevel = StartingLevel.COURSE_CONTEXT
    explanation_style: ExplanationStyle = ExplanationStyle.CONCEPT_FIRST
    answer_style: AnswerStyle = AnswerStyle.BALANCED
    step_by_step: bool | None = None
    exam_style: bool = False
    visual_preference: DetailPreference = DetailPreference.AUTO
    math_detail: DetailPreference = DetailPreference.AUTO
    code_detail: DetailPreference = DetailPreference.AUTO


class CourseProfileData(CourseStudyPreferences):
    """Persisted custom profile fields, excluding identity and timestamps."""

    display_alias: str | None = Field(default=None, max_length=255)
    short_label: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    terminology_notes: str | None = Field(default=None, max_length=2000)
    study_instructions: str | None = Field(default=None, max_length=4000)
    enabled: bool = True


class CourseProfileUpdate(BaseModel):
    """Validated full replacement/update payload for a custom profile."""

    model_config = ConfigDict(extra="forbid")

    display_alias: str | None = Field(default=None, max_length=255)
    short_label: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    teaching_depth: TeachingDepth = TeachingDepth.BALANCED
    starting_level: StartingLevel = StartingLevel.COURSE_CONTEXT
    explanation_style: ExplanationStyle = ExplanationStyle.CONCEPT_FIRST
    answer_style: AnswerStyle = AnswerStyle.BALANCED
    step_by_step: bool | None = None
    exam_style: bool = False
    visual_preference: DetailPreference = DetailPreference.AUTO
    math_detail: DetailPreference = DetailPreference.AUTO
    code_detail: DetailPreference = DetailPreference.AUTO
    terminology_notes: str | None = Field(default=None, max_length=2000)
    study_instructions: str | None = Field(default=None, max_length=4000)
    enabled: bool = True


class EffectiveCourseContext(BaseModel):
    """Future-assistant boundary: local course truth plus effective preferences."""

    course_id: str
    course_name: str | None
    course_code: str | None
    preferences: CourseStudyPreferences
    course_instructions: str | None
    has_custom_profile: bool


class CourseProfileView(BaseModel):
    """API response distinguishing defaults from explicit custom data."""

    model_config = ConfigDict(from_attributes=True)

    course_id: str
    course_name: str | None
    course_code: str | None
    has_custom_profile: bool
    profile: CourseProfileData | None
    effective_preferences: CourseStudyPreferences
    effective_course_instructions: str | None
    created_at: datetime | None
    updated_at: datetime | None
