"""Public assignment response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AssignmentResponse(BaseModel):
    """Local assignment metadata; description HTML remains untrusted text."""

    model_config = ConfigDict(from_attributes=True)

    canvas_assignment_id: str
    canvas_course_id: str
    name: str | None
    description_html: str | None
    due_at: datetime | None
    unlock_at: datetime | None
    lock_at: datetime | None
    points_possible: float | None
    submission_types: list[str]
    workflow_state: str | None
    html_url: str | None
    published: bool | None
    has_submitted_submissions: bool | None
    canvas_updated_at: datetime | None
    rubric: list[dict[str, Any]] | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_synced_at: datetime

