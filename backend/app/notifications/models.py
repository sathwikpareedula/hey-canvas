"""Deterministic academic notification contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class NotificationType(StrEnum):
    ASSIGNMENT_DUE_SOON = "assignment_due_soon"
    ASSIGNMENT_DUE_TOMORROW = "assignment_due_tomorrow"
    ASSIGNMENT_OVERDUE = "assignment_overdue"
    ASSIGNMENT_NEW = "assignment_new"
    ASSIGNMENT_DUE_DATE_CHANGED = "assignment_due_date_changed"
    MATERIAL_NEW = "professor_material_new"
    MATERIAL_CHANGED = "professor_material_changed"
    EXAM_UPCOMING = "exam_upcoming"


class NotificationSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=255)
    course_id: str = Field(min_length=1, max_length=255)
    assignment_id: str | None = Field(default=None, min_length=1, max_length=255)
    notification_type: NotificationType
    severity: NotificationSeverity
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=1000)
    due_at: datetime | None = None
    source: str = Field(default="canvas_sync", max_length=100)
    observed_at: datetime
    dedupe_key: str = Field(min_length=1, max_length=255)
    read: bool = False
    dismissed: bool = False


class NotificationList(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[NotificationCandidate, ...] = Field(default=(), max_length=200)
    total: int = 0
