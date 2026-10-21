"""Typed focus-course contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FocusCourseView(BaseModel):
    model_config = ConfigDict(frozen=True)

    course_id: str = Field(min_length=1, max_length=255)
    position: int = Field(ge=0, le=500)
    course_name: str | None = Field(default=None, max_length=500)
    course_code: str | None = Field(default=None, max_length=255)
    term_name: str | None = Field(default=None, max_length=500)
    workflow_state: str | None = Field(default=None, max_length=100)
    enrollment_state: str | None = Field(default=None, max_length=100)
    selected_at: datetime


class FocusCourseSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    course_ids: tuple[str, ...] = Field(max_length=100)


class FocusCourseMutation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    course_id: str = Field(min_length=1, max_length=255)
