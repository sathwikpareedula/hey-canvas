"""Typed privacy and course policy contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PrivacyMode(StrEnum):
    LOCAL_ONLY = "LOCAL_ONLY"
    OPTIONAL_CLOUD_BYO = "OPTIONAL_CLOUD_BYO"


class CourseAIPolicyValue(StrEnum):
    UNKNOWN = "unknown"
    ALLOWED = "allowed"
    RESTRICTED = "restricted"
    DISABLED = "disabled"


class PrivacySettingsView(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_key: str
    mode: PrivacyMode
    updated_at: datetime


class PrivacySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: PrivacyMode


class CourseAIPolicyView(BaseModel):
    model_config = ConfigDict(frozen=True)

    course_id: str
    policy: CourseAIPolicyValue
    provider_mode: PrivacyMode
    notes: str | None
    updated_at: datetime


class CourseAIPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: CourseAIPolicyValue
    provider_mode: PrivacyMode = PrivacyMode.LOCAL_ONLY
    notes: str | None = Field(default=None, max_length=1000)
