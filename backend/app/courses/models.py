"""Provider-neutral course synchronization values."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CourseSnapshot(BaseModel):
    """Normalized course state observed during one upstream synchronization."""

    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    course_code: str | None = None
    course_name: str | None = None
    term_canvas_id: str | None = None
    term_name: str | None = None
    term_start_at: datetime | None = None
    term_end_at: datetime | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    workflow_state: str | None = None
    enrollment_state: str | None = None
    enrollment_type: str | None = None
    canvas_updated_at: datetime | None = None


class CourseSyncSummary(BaseModel):
    """Non-secret counts describing one atomic course synchronization."""

    model_config = ConfigDict(frozen=True)

    courses_received: int
    courses_created: int
    courses_updated: int
    courses_unchanged: int

