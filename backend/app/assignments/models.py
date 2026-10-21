"""Provider-neutral assignment synchronization values."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AssignmentSnapshot(BaseModel):
    """Normalized assignment state observed during one course synchronization."""

    model_config = ConfigDict(frozen=True)

    canvas_assignment_id: str
    canvas_course_id: str
    name: str | None = None
    description_html: str | None = None
    due_at: datetime | None = None
    unlock_at: datetime | None = None
    lock_at: datetime | None = None
    points_possible: float | None = None
    submission_types: tuple[str, ...] = ()
    workflow_state: str | None = None
    html_url: str | None = None
    published: bool | None = None
    has_submitted_submissions: bool | None = None
    canvas_updated_at: datetime | None = None
    rubric: list[dict[str, Any]] | None = None


class AssignmentSyncFailure(BaseModel):
    """Safe per-course failure information without upstream response content."""

    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    error_type: str
    message: str


class AssignmentCourseSyncCounts(BaseModel):
    """Upsert counts for one successfully fetched course."""

    model_config = ConfigDict(frozen=True)

    assignments_received: int
    assignments_created: int
    assignments_updated: int
    assignments_unchanged: int


class AssignmentSyncSummary(BaseModel):
    """Aggregate counts for an independent per-course assignment synchronization."""

    model_config = ConfigDict(frozen=True)

    courses_attempted: int
    courses_succeeded: int
    courses_failed: int
    assignments_received: int
    assignments_created: int
    assignments_updated: int
    assignments_unchanged: int
    failures: tuple[AssignmentSyncFailure, ...] = ()
