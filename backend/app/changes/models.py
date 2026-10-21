"""Stable public values for deterministic change history."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ChangeEventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_external_id: str
    course_canvas_id: str | None
    event_type: str
    field_name: str | None
    old_value: Any | None
    new_value: Any | None
    observed_at: datetime
    source: str
    context: dict[str, Any] | None
    created_at: datetime


class ChangeSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    new_assignments: int = 0
    deadline_changes: int = 0
    module_changes: int = 0
    module_item_changes: int = 0
    file_metadata_changes: int = 0
    file_content_changes: int = 0
    local_file_integrity_issues: int = 0
