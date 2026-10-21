"""Workspace contracts with bounded continuity metadata."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceView(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace_key: str
    course_id: str | None
    display_name: str
    recent_entities: tuple[dict[str, str], ...]
    recent_intent: str | None
    updated_at: datetime


class WorkspaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    recent_entities: tuple[dict[str, str], ...] | None = Field(default=None, max_length=20)
    recent_intent: str | None = Field(default=None, max_length=80)
