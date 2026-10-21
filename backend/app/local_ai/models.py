"""Typed Local AI settings contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InstalledModelsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    models: tuple[str, ...] = Field(max_length=20)


class LocalModelSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str = Field(min_length=1, max_length=255)
    source: str = Field(pattern="^(saved|environment_default)$")
    updated_at: datetime | None = None


class LocalModelSelectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    model: str = Field(min_length=1, max_length=255)
