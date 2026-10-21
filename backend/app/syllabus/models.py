"""Read-only Canvas syllabus contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SyllabusLinkedResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(max_length=500)
    url: str = Field(max_length=2048)
    resource_type: str = Field(default="link", max_length=50)


class SyllabusSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    canvas_course_id: str = Field(max_length=255)
    syllabus_html: str | None = None
    html_url: str | None = Field(default=None, max_length=2048)
    canvas_updated_at: datetime | None = None
    linked_resources: tuple[SyllabusLinkedResource, ...] = ()


class SyllabusSyncFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    error_type: str
    message: str = Field(max_length=300)


class SyllabusSyncSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    courses_attempted: int
    courses_succeeded: int
    courses_failed: int
    syllabi_received: int
    syllabi_created: int
    syllabi_updated: int
    syllabi_unchanged: int
    failures: tuple[SyllabusSyncFailure, ...] = ()
