"""Typed inputs and results for deterministic course resolution."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ResolutionOutcome(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class ResolutionEvidence(StrEnum):
    EXPLICIT_COURSE = "explicit_course"
    ASSIGNMENT_MEMBERSHIP = "assignment_membership"
    DOCUMENT_PROVENANCE = "document_provenance"
    MODULE_MEMBERSHIP = "module_membership"
    ACTIVE_CONTEXT = "active_context"
    PROFILE_ALIAS = "profile_alias"
    PROFILE_SHORT_LABEL = "profile_short_label"
    COURSE_NAME_MATCH = "course_name_match"


class CourseRoutingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    course_id: str | None = Field(default=None, min_length=1, max_length=255)
    assignment_id: str | None = Field(default=None, min_length=1, max_length=255)
    document_id: str | None = Field(default=None, min_length=1, max_length=255)
    module_id: str | None = Field(default=None, min_length=1, max_length=255)
    module_item_id: str | None = Field(default=None, min_length=1, max_length=255)
    active_course_id: str | None = Field(default=None, min_length=1, max_length=255)
    text: str | None = Field(default=None, max_length=500)


class ResolvedCourse(BaseModel):
    course_id: str
    course_name: str | None
    course_code: str | None


class CourseRoutingResult(BaseModel):
    outcome: ResolutionOutcome
    course: ResolvedCourse | None = None
    evidence: tuple[ResolutionEvidence, ...] = ()
    candidates: tuple[ResolvedCourse, ...] = ()
    reason: str
