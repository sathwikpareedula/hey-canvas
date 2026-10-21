"""Security & Health Center response models (credential-free)."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class SecurityCheckStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    NOT_CHECKED = "not_checked"


class SecurityCheck(BaseModel):
    id: str
    title: str
    status: SecurityCheckStatus
    summary: str
    detail: str | None = None


class SecurityHealthReport(BaseModel):
    generated_at: str
    checks: list[SecurityCheck] = Field(default_factory=list)
    overall: Literal["pass", "warning", "fail", "not_checked"] = "not_checked"
