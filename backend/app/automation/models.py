"""Safe assistant automation contracts and allowlist boundary."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AllowedAutomationOperation(StrEnum):
    LIST_NOTIFICATIONS = "list_notifications"
    PREVIEW_REMINDER_PLAN = "preview_reminder_plan"
    PREVIEW_CALENDAR_EVENT = "preview_calendar_event"
    LIST_LINKED_CALENDAR_EVENTS = "list_linked_calendar_events"


class AutomationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: AllowedAutomationOperation
    course_id: str | None = Field(default=None, min_length=1, max_length=255)
    assignment_id: str | None = Field(default=None, min_length=1, max_length=255)
    query: str | None = Field(default=None, max_length=4000)


class AutomationPreview(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: AllowedAutomationOperation
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1000)
    payload: dict[str, object] | None = Field(default=None, max_length=20)
    requires_confirmation: bool = False
    safe_to_execute: bool = True


class AutomationExecution(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: AllowedAutomationOperation
    accepted: bool = True
    preview: AutomationPreview | None = None
    message: str | None = Field(default=None, max_length=500)
