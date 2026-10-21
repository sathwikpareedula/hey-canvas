"""Provider-neutral Google Drive boundary for future academic workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class DriveItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=200)
    mime_type: str = Field(min_length=1, max_length=100)
    parent_id: str | None = Field(default=None, min_length=1, max_length=255)
    modified_at: datetime | None = None
    source: str = Field(default="user_selected", max_length=50)


class DriveProvider(Protocol):
    def list_items(self, *, query: str | None = None) -> tuple[DriveItem, ...]:
        ...

    def preview_upload(self, *, name: str, mime_type: str) -> DriveItem:
        ...

    def upload(self, *, name: str, mime_type: str, payload: bytes) -> DriveItem:
        ...


class DriveBoundaryConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    allow_writes: bool = False
    default_parent_id: str | None = Field(default=None, min_length=1, max_length=255)
