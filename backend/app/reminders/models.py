"""Reminder planning contracts for user-driven academic follow-up."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReminderStatus(StrEnum):
    SCHEDULED = "scheduled"
    FIRED = "fired"
    CANCELLED = "cancelled"


class ReminderPreference(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    lead_times_hours: tuple[int, ...] = (24, 3)
    timezone: str = "America/Chicago"
    course_overrides: dict[str, tuple[int, ...]] = Field(default_factory=dict)


class ReminderOccurrence(BaseModel):
    model_config = ConfigDict(frozen=True)

    at: datetime
    lead_hours: int
    status: ReminderStatus = ReminderStatus.SCHEDULED


class ReminderPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: str = Field(min_length=1, max_length=255)
    course_id: str = Field(min_length=1, max_length=255)
    assignment_id: str = Field(min_length=1, max_length=255)
    due_at: datetime
    enabled: bool = True
    reminders: tuple[ReminderOccurrence, ...] = Field(default=(), max_length=20)


class ReminderPlanPreview(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=500)
    plan: ReminderPlan
