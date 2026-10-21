"""Provider-neutral orchestration contracts."""

from collections.abc import Iterable
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.assistant_tools.models import (
    AcademicContextPackage,
    AssignmentContext,
    AssignmentToolRecord,
    AssistantEvidenceReference,
    AssistantRequest,
    AssistantResponse,
    CanvasTextEvidence,
    ChangeToolResult,
    DeadlineToolResult,
    DocumentEvidence,
    DocumentSearchToolResult,
    ResponseBlockType,
    SourceAuthority,
)
from app.calendar.models import CalendarEvent
from app.notifications.models import NotificationList
from app.practice_sessions.models import PracticeFeedback, PracticeSessionView
from app.reminders.models import ReminderPlanPreview
from app.study_guides.models import StudyGuide
from app.study_sessions.models import StudySessionView


class AssistantOperation(StrEnum):
    COURSE_LOOKUP = "course_lookup"
    FOCUS_COURSES = "focus_courses"
    SYNC_STATUS = "sync_status"
    DEADLINES = "deadlines"
    ASSIGNMENT_CONTEXT = "assignment_context"
    MATERIAL_SEARCH = "material_search"
    RECENT_CHANGES = "recent_changes"
    STUDY_HELP = "study_help"
    STUDY_PLAN = "study_plan"
    PRACTICE_SESSION = "practice_session"
    PRACTICE_HINT = "practice_hint"
    PRACTICE_ANSWER = "practice_answer"
    STUDY_GUIDE = "study_guide"
    LIST_NOTIFICATIONS = "list_notifications"
    PREVIEW_REMINDER_PLAN = "preview_reminder_plan"
    PREVIEW_CALENDAR_EVENT = "preview_calendar_event"


class ToolPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: AssistantOperation
    course_id: str | None = Field(default=None, max_length=255)
    query: str = Field(max_length=4000)


class AssistantModelInput(BaseModel):
    """Explicit data package; source material is data, never instructions."""

    model_config = ConfigDict(frozen=True)

    request: AssistantRequest
    plan: ToolPlan
    context: AcademicContextPackage | None
    deadlines: DeadlineToolResult | None = None
    assignment_context: AssignmentContext | None = None
    recent_changes: ChangeToolResult | None = None
    material_search: DocumentSearchToolResult | None = None
    evidence: tuple[DocumentEvidence, ...] = Field(default=(), max_length=20)
    canvas_text_evidence: tuple[CanvasTextEvidence, ...] = Field(default=(), max_length=10)
    untrusted_material: tuple[str, ...] = Field(default=(), max_length=20)
    study_plan: StudySessionView | None = None
    practice_session: PracticeSessionView | None = None
    practice_hint: str | None = None
    practice_feedback: PracticeFeedback | None = None
    study_guide: StudyGuide | None = None
    notifications: NotificationList | None = None
    reminder_preview: ReminderPlanPreview | None = None
    calendar_preview: CalendarEvent | None = None
    course_list: tuple[BaseModel, ...] = ()
    sync_status: dict[str, object] | None = None
    assignment_candidates: tuple[AssignmentToolRecord, ...] = ()


class AssistantEventType(StrEnum):
    STARTED = "started"
    TEXT_DELTA = "text_delta"
    BLOCK = "block"
    SOURCE = "source"
    WARNING = "warning"
    ERROR = "error"
    FOLLOW_UP = "follow_up"
    COMPLETED = "completed"


class AssistantEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: AssistantEventType
    text: str | None = Field(default=None, max_length=4000)
    block_type: ResponseBlockType | None = None
    source: SourceAuthority | None = None
    identifier: str | None = Field(default=None, max_length=255)
    payload: dict[str, object] | None = Field(default=None, max_length=20)
    references: tuple[AssistantEvidenceReference, ...] = Field(default=(), max_length=20)
    response: AssistantResponse | None = None


class CancellationToken(Protocol):
    @property
    def cancelled(self) -> bool:
        ...


class AcademicModelProvider(Protocol):
    """Minimal provider seam; implementations may be synthetic or future model adapters."""

    def complete(self, model_input: AssistantModelInput) -> AssistantResponse:
        ...

    def stream(self, model_input: AssistantModelInput) -> Iterable[AssistantEvent]:
        ...
