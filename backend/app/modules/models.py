"""Provider-neutral module synchronization values."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ModuleItemSnapshot(BaseModel):
    """Normalized state for one ordered Canvas module item."""

    model_config = ConfigDict(frozen=True)

    canvas_module_item_id: str
    canvas_module_id: str
    canvas_course_id: str
    title: str | None = None
    position: int | None = None
    item_type: str
    content_id: str | None = None
    html_url: str | None = None
    api_url: str | None = None
    page_url: str | None = None
    external_url: str | None = None
    new_tab: bool | None = None
    completion_requirement: dict[str, Any] | None = None
    content_details: dict[str, Any] | None = None
    indent: int | None = None
    published: bool | None = None


class ModuleSnapshot(BaseModel):
    """Normalized module metadata plus its completely fetched item set."""

    model_config = ConfigDict(frozen=True)

    canvas_module_id: str
    canvas_course_id: str
    name: str | None = None
    position: int | None = None
    unlock_at: datetime | None = None
    require_sequential_progress: bool | None = None
    requirement_type: str | None = None
    publish_final_grade: bool | None = None
    prerequisite_module_ids: tuple[str, ...] = ()
    workflow_state: str | None = None
    state: str | None = None
    completed_at: datetime | None = None
    items_count: int | None = None
    published: bool | None = None
    items: tuple[ModuleItemSnapshot, ...] = ()


class ModuleCourseSyncCounts(BaseModel):
    """Upsert counts for one successfully fetched course structure."""

    model_config = ConfigDict(frozen=True)

    modules_received: int
    modules_created: int
    modules_updated: int
    modules_unchanged: int
    items_received: int
    items_created: int
    items_updated: int
    items_unchanged: int


class ModuleSyncFailure(BaseModel):
    """Safe per-course module failure information."""

    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    error_type: str
    message: str


class ModuleSyncSummary(BaseModel):
    """Aggregate counts for independent per-course module synchronization."""

    model_config = ConfigDict(frozen=True)

    courses_attempted: int
    courses_succeeded: int
    courses_failed: int
    modules_received: int
    modules_created: int
    modules_updated: int
    modules_unchanged: int
    items_received: int
    items_created: int
    items_updated: int
    items_unchanged: int
    failures: tuple[ModuleSyncFailure, ...] = ()


class AssignmentReference(BaseModel):
    """Optional local assignment metadata resolved from a module-item content ID."""

    model_config = ConfigDict(frozen=True)

    canvas_assignment_id: str
    name: str | None
    due_at: datetime | None


class ModuleItemStructure(BaseModel):
    """An inert item reference in a deterministic local course structure."""

    canvas_module_item_id: str
    canvas_module_id: str
    canvas_course_id: str
    title: str | None
    position: int | None
    item_type: str
    content_id: str | None
    html_url: str | None
    api_url: str | None
    page_url: str | None
    external_url: str | None
    new_tab: bool | None
    completion_requirement: dict[str, Any] | None
    content_details: dict[str, Any] | None
    indent: int | None
    published: bool | None
    assignment: AssignmentReference | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_synced_at: datetime


class CourseModuleStructure(BaseModel):
    """A persisted module with its ordered item references."""

    canvas_module_id: str
    canvas_course_id: str
    name: str | None
    position: int | None
    unlock_at: datetime | None
    require_sequential_progress: bool | None
    requirement_type: str | None
    publish_final_grade: bool | None
    prerequisite_module_ids: list[str]
    workflow_state: str | None
    state: str | None
    completed_at: datetime | None
    items_count: int | None
    published: bool | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_synced_at: datetime
    items: list[ModuleItemStructure]
