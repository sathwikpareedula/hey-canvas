"""Typed contracts for unified synchronization and persisted run history."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SyncRunStatus = Literal["running", "succeeded", "partially_succeeded", "failed", "interrupted"]
SyncStageStatus = Literal["pending", "succeeded", "partially_succeeded", "failed", "skipped"]


class SyncRunError(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage: str
    course_id: str | None = None
    error_type: str
    message: str = Field(max_length=300)


class SyncStageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: SyncStageStatus
    counts: dict[str, int] = Field(default_factory=dict)
    reason: str | None = None


class SyncRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: int
    status: SyncRunStatus
    trigger: str
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    scope_course_ids: list[str]
    check_local_files: bool
    stages: dict[str, SyncStageResult]
    change_events_created: int
    changes: dict[str, int]
    errors: list[SyncRunError]


class SyncRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: datetime | None
    heartbeat_at: datetime
    status: SyncRunStatus
    trigger: str
    scope_course_ids: list[str]
    check_local_files: bool
    stage_results: dict[str, Any]
    change_summary: dict[str, int]
    change_events_created: int
    error_count: int
    errors: list[dict[str, Any]]
    created_at: datetime
