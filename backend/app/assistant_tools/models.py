"""Provider-neutral, bounded academic assistant tool contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.academic_context.models import AcademicContext
from app.changes.models import ChangeEventView
from app.course_profiles.models import CourseProfileView
from app.course_router.models import CourseRoutingResult
from app.documents.models import DocumentSearchHit, DocumentUnitView, DocumentView
from app.study_context.models import StudyContextView


class SourceAuthority(StrEnum):
    CANVAS_TRUTH = "canvas_truth"
    PROFESSOR_MATERIAL = "professor_material"
    USER_PROFILE = "user_profile"
    USER_STUDY_CONTEXT = "user_study_context"
    ROUTING_EVIDENCE = "routing_evidence"
    CHANGE_EVENT = "change_event"


class AssistantStudyMode(StrEnum):
    LEARN = "learn"
    REVIEW = "review"
    PRACTICE = "practice"
    EXAM_PREP = "exam_prep"


class CourseToolRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.CANVAS_TRUTH
    canvas_course_id: str = Field(max_length=255)
    course_code: str | None = Field(default=None, max_length=255)
    course_name: str | None = Field(default=None, max_length=500)
    term_name: str | None = Field(default=None, max_length=500)
    workflow_state: str | None = Field(default=None, max_length=100)
    enrollment_state: str | None = Field(default=None, max_length=100)


class AssignmentToolRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.CANVAS_TRUTH
    canvas_assignment_id: str = Field(max_length=255)
    canvas_course_id: str = Field(max_length=255)
    name: str | None = Field(default=None, max_length=500)
    due_at: datetime | None
    unlock_at: datetime | None
    lock_at: datetime | None
    points_possible: float | None
    submission_types: tuple[str, ...]
    workflow_state: str | None = Field(default=None, max_length=100)
    published: bool | None


class DeadlineToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    window: str = Field(min_length=1, max_length=30)
    authority: SourceAuthority = SourceAuthority.CANVAS_TRUTH
    assignments: tuple[AssignmentToolRecord, ...] = Field(max_length=500)
    normalized_window: str | None = Field(default=None, max_length=50)



class CanvasTextEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.CANVAS_TRUTH
    source_kind: Literal["announcement", "syllabus", "assignment_description"]
    canvas_course_id: str = Field(max_length=255)
    source_id: str = Field(max_length=255)
    title: str | None = Field(default=None, max_length=500)
    excerpt: str = Field(max_length=1000)
    html_url: str | None = Field(default=None, max_length=2048)
    posted_at: datetime | None = None


class TopicModuleLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    topic: str = Field(max_length=200)
    canvas_module_id: str = Field(max_length=255)
    canvas_module_item_id: str = Field(max_length=255)
    item_title: str | None = Field(default=None, max_length=500)
    item_type: str = Field(max_length=50)
    content_id: str | None = Field(default=None, max_length=255)


class DocumentEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.PROFESSOR_MATERIAL
    canvas_file_id: str = Field(max_length=255)
    canvas_course_id: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=1000)
    filename: str | None = Field(default=None, max_length=1000)
    source_sha256: str | None = Field(default=None, max_length=64)
    parser_name: str | None = Field(default=None, max_length=100)
    parser_version: str | None = Field(default=None, max_length=50)
    unit_type: str = Field(max_length=50)
    unit_index: int
    page_number: int | None
    slide_number: int | None
    heading: str | None
    excerpt: str = Field(max_length=1000)
    is_stale: bool
    module_references: tuple[str, ...] = Field(default=(), max_length=20)
    module_item_references: tuple[str, ...] = Field(default=(), max_length=20)


class ChangeToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.CHANGE_EVENT
    changes: tuple[ChangeEventView, ...] = Field(max_length=500)


class DocumentToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.PROFESSOR_MATERIAL
    documents: tuple[DocumentView, ...] = Field(max_length=500)


class DocumentUnitToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.PROFESSOR_MATERIAL
    units: tuple[DocumentUnitView, ...] = Field(max_length=2000)


class DocumentSearchToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.PROFESSOR_MATERIAL
    hits: tuple[DocumentSearchHit, ...] = Field(max_length=100)


class CourseProfileToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.USER_PROFILE
    profile: CourseProfileView


class StudyContextToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.USER_STUDY_CONTEXT
    context: StudyContextView


class RoutingToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority = SourceAuthority.ROUTING_EVIDENCE
    result: CourseRoutingResult


class AssignmentContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    assignment: AssignmentToolRecord
    description_text: str | None = Field(default=None, max_length=4000)
    course: CourseToolRecord
    modules: tuple[str, ...]
    related_documents: tuple[DocumentView, ...]
    profile: CourseProfileView
    study_context: StudyContextView
    retrieval_evidence: tuple[DocumentEvidence, ...] = Field(default=(), max_length=20)
    canvas_text_evidence: tuple[CanvasTextEvidence, ...] = Field(default=(), max_length=10)
    topic_module_links: tuple[TopicModuleLink, ...] = Field(default=(), max_length=12)
    authority: tuple[SourceAuthority, ...] = Field(
        default=(
            SourceAuthority.CANVAS_TRUTH,
            SourceAuthority.PROFESSOR_MATERIAL,
            SourceAuthority.USER_PROFILE,
            SourceAuthority.USER_STUDY_CONTEXT,
        ),
        max_length=10,
    )


class RetrievalEvidenceProvider(Protocol):
    """Provider-neutral injection boundary implemented by the retrieval layer."""

    def evidence_for(self, *, course_id: str, query: str) -> tuple[DocumentEvidence, ...]:
        ...


class AcademicContextPackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    context: AcademicContext
    retrieval_evidence: tuple[DocumentEvidence, ...] = Field(default=(), max_length=20)
    authorities: tuple[SourceAuthority, ...] = Field(
        default=(
            SourceAuthority.CANVAS_TRUTH,
            SourceAuthority.ROUTING_EVIDENCE,
            SourceAuthority.USER_PROFILE,
            SourceAuthority.USER_STUDY_CONTEXT,
        ),
        max_length=10,
    )


class AssistantRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    query: str = Field(min_length=1, max_length=4000)
    course_id: str | None = Field(default=None, min_length=1, max_length=255)
    assignment_id: str | None = Field(default=None, min_length=1, max_length=255)
    document_id: str | None = Field(default=None, min_length=1, max_length=255)
    study_mode: AssistantStudyMode | None = None
    session_id: str | None = Field(default=None, min_length=1, max_length=255)
    active_course_id: str | None = Field(default=None, min_length=1, max_length=255)
    practice_session_id: str | None = Field(default=None, min_length=1, max_length=255)
    practice_question_id: str | None = Field(default=None, min_length=1, max_length=255)
    answer: str | None = Field(default=None, min_length=1, max_length=4000)
    operation: str = Field(default="answer", min_length=1, max_length=80)


class ResponseBlockType(StrEnum):
    TEXT = "text"
    DEADLINES = "deadline_group"
    ASSIGNMENT_CONTEXT = "assignment_context"
    STUDY_PLAN = "study_plan"
    DOCUMENT_EVIDENCE = "document_evidence"
    RECENT_CHANGES = "recent_changes"
    WARNING = "warning"
    ERROR = "error"
    FOLLOW_UP = "follow_up"
    NOTIFICATION_SUMMARY = "notification_summary"
    REMINDER_PREVIEW = "reminder_preview"
    CALENDAR_ACTION_PREVIEW = "calendar_action_preview"
    CALENDAR_ACTION_RESULT = "calendar_action_result"
    PRACTICE_QUESTION = "practice_question"
    PRACTICE_FEEDBACK = "practice_feedback"
    STUDY_GUIDE = "study_guide"
    COURSE_LIST = "course_list"
    SYNC_STATUS = "sync_status"


class AssistantEvidenceReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority: SourceAuthority
    identifier: str = Field(min_length=1, max_length=255)
    locator: str | None = Field(default=None, min_length=1, max_length=255)


class AssistantResponseBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: ResponseBlockType
    text: str | None = Field(default=None, max_length=4000)
    payload: dict[str, object] | None = Field(default=None, max_length=20)
    references: tuple[AssistantEvidenceReference, ...] = Field(default=(), max_length=20)


class AssistantResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = Field(min_length=1, max_length=40)
    blocks: tuple[AssistantResponseBlock, ...] = Field(default=(), max_length=50)
    course_id: str | None = Field(default=None, min_length=1, max_length=255)
