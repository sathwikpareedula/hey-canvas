"""SQLAlchemy models for locally synchronized academic metadata."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.database.types import UTCDateTime


class Base(DeclarativeBase):
    """Base class for persisted domain models."""


class Course(Base):
    """A Canvas course identified by its stable external Canvas ID."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    canvas_course_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    course_code: Mapped[str | None] = mapped_column(String(255))
    course_name: Mapped[str | None] = mapped_column(String(500))
    term_canvas_id: Mapped[str | None] = mapped_column(String(255))
    term_name: Mapped[str | None] = mapped_column(String(500))
    term_start_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    term_end_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    start_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    workflow_state: Mapped[str | None] = mapped_column(String(100))
    enrollment_state: Mapped[str | None] = mapped_column(String(100))
    enrollment_type: Mapped[str | None] = mapped_column(String(100))
    canvas_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_synced_at: Mapped[datetime] = mapped_column(UTCDateTime())
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="course")
    modules: Mapped[list["CourseModule"]] = relationship(back_populates="course")
    module_items: Mapped[list["ModuleItem"]] = relationship(back_populates="course")
    profile: Mapped["CourseProfile | None"] = relationship(
        back_populates="course",
        uselist=False,
        cascade="all, delete-orphan",
    )
    study_context: Mapped["StudyContext | None"] = relationship(
        back_populates="course",
        uselist=False,
        cascade="all, delete-orphan",
    )
    focus_selections: Mapped[list["FocusCourse"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    announcements: Mapped[list["CanvasAnnouncement"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    syllabus: Mapped["CourseSyllabus | None"] = relationship(
        back_populates="course",
        uselist=False,
        cascade="all, delete-orphan",
    )


class FocusCourse(Base):
    """User-selected preferred course scope for local academic assistance."""

    __tablename__ = "focus_courses"
    __table_args__ = (UniqueConstraint("user_key", "course_id", name="uq_focus_user_course"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(String(100), index=True)
    course_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("courses.canvas_course_id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course] = relationship(back_populates="focus_selections")


class AcademicWorkspace(Base):
    """Bounded durable workspace state; conversation text is never persisted."""

    __tablename__ = "academic_workspaces"
    __table_args__ = (
        UniqueConstraint("user_key", "workspace_key", name="uq_workspace_user_key"),
        Index("ix_workspaces_course", "course_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(String(100), index=True)
    workspace_key: Mapped[str] = mapped_column(String(255))
    course_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("courses.canvas_course_id", ondelete="SET NULL"),
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(255))
    recent_entities: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    recent_intent: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course | None] = relationship()


class PrivacySetting(Base):
    """Explicit local/cloud provider mode for the local owner."""

    __tablename__ = "privacy_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(30), default="LOCAL_ONLY")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class LocalAISetting(Base):
    """Persistent local model selection for the single local application owner."""

    __tablename__ = "local_ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    selected_model: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class CourseAIPolicy(Base):
    """Per-course AI boundary; unknown is intentionally conservative."""

    __tablename__ = "course_ai_policies"
    __table_args__ = (UniqueConstraint("user_key", "course_id", name="uq_ai_policy_user_course"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(String(100), index=True)
    course_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("courses.canvas_course_id", ondelete="CASCADE"),
        index=True,
    )
    policy: Mapped[str] = mapped_column(String(30), default="unknown")
    provider_mode: Mapped[str] = mapped_column(String(30), default="local_only")
    notes: Mapped[str | None] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class SchemaVersion(Base):
    """Durable schema marker used by non-destructive startup upgrades."""

    __tablename__ = "schema_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    applied_at: Mapped[datetime] = mapped_column(UTCDateTime())


class CourseProfile(Base):
    """User-controlled academic-assistance configuration for one Canvas course."""

    __tablename__ = "course_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("courses.canvas_course_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    display_alias: Mapped[str | None] = mapped_column(String(255))
    short_label: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(2000))
    teaching_depth: Mapped[str] = mapped_column(String(30), default="balanced")
    starting_level: Mapped[str] = mapped_column(String(30), default="course_context")
    explanation_style: Mapped[str] = mapped_column(String(40), default="concept_first")
    answer_style: Mapped[str] = mapped_column(String(30), default="balanced")
    step_by_step: Mapped[bool | None] = mapped_column(Boolean)
    exam_style: Mapped[bool] = mapped_column(Boolean, default=False)
    visual_preference: Mapped[str] = mapped_column(String(20), default="auto")
    math_detail: Mapped[str] = mapped_column(String(20), default="auto")
    code_detail: Mapped[str] = mapped_column(String(20), default="auto")
    terminology_notes: Mapped[str | None] = mapped_column(String(2000))
    study_instructions: Mapped[str | None] = mapped_column(String(4000))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course] = relationship(back_populates="profile")


class StudyContext(Base):
    """Bounded user-controlled continuity state for one Canvas course."""

    __tablename__ = "study_contexts"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("courses.canvas_course_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    current_topic: Mapped[str | None] = mapped_column(String(255))
    assignment_id: Mapped[str | None] = mapped_column(String(255))
    study_mode: Mapped[str] = mapped_column(String(30), default="balanced")
    starting_point: Mapped[str | None] = mapped_column(String(255))
    concepts_covered: Mapped[list[str]] = mapped_column(JSON, default=list)
    topics_to_revisit: Mapped[list[str]] = mapped_column(JSON, default=list)
    study_note: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course] = relationship(back_populates="study_context")


class Assignment(Base):
    """Canvas assignment scoped to a locally persisted course."""

    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "canvas_assignment_id",
            name="uq_assignments_course_canvas_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    canvas_assignment_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(500))
    description_html: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    unlock_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    lock_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    points_possible: Mapped[float | None] = mapped_column(Float)
    submission_types: Mapped[list[str]] = mapped_column(JSON)
    workflow_state: Mapped[str | None] = mapped_column(String(100))
    html_url: Mapped[str | None] = mapped_column(String(2048))
    published: Mapped[bool | None] = mapped_column(Boolean)
    has_submitted_submissions: Mapped[bool | None] = mapped_column(Boolean)
    canvas_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    rubric: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_synced_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course] = relationship(back_populates="assignments")

    @property
    def canvas_course_id(self) -> str:
        return self.course.canvas_course_id


class CanvasAnnouncement(Base):
    """Canvas course announcement (discussion topic) stored as read-only text."""

    __tablename__ = "canvas_announcements"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "canvas_topic_id",
            name="uq_announcements_course_topic",
        ),
        Index("ix_announcements_course_posted", "course_id", "posted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    canvas_topic_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    message_html: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    delayed_post_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    published: Mapped[bool | None] = mapped_column(Boolean)
    html_url: Mapped[str | None] = mapped_column(String(2048))
    canvas_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_synced_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course] = relationship(back_populates="announcements")

    @property
    def canvas_course_id(self) -> str:
        return self.course.canvas_course_id


class CourseSyllabus(Base):
    """Course syllabus body and extracted link references."""

    __tablename__ = "course_syllabi"
    __table_args__ = (UniqueConstraint("course_id", name="uq_syllabus_course"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    syllabus_html: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    html_url: Mapped[str | None] = mapped_column(String(2048))
    linked_resources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    canvas_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_synced_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course] = relationship(back_populates="syllabus")

    @property
    def canvas_course_id(self) -> str:
        return self.course.canvas_course_id


class CourseModule(Base):
    """A Canvas module scoped to its owning course."""

    __tablename__ = "modules"
    __table_args__ = (
        UniqueConstraint("course_id", "canvas_module_id", name="uq_modules_course_canvas_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    canvas_module_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(500))
    position: Mapped[int | None] = mapped_column(Integer)
    unlock_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    require_sequential_progress: Mapped[bool | None] = mapped_column(Boolean)
    requirement_type: Mapped[str | None] = mapped_column(String(100))
    publish_final_grade: Mapped[bool | None] = mapped_column(Boolean)
    prerequisite_module_ids: Mapped[list[str]] = mapped_column(JSON)
    workflow_state: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    items_count: Mapped[int | None] = mapped_column(Integer)
    published: Mapped[bool | None] = mapped_column(Boolean)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_synced_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course] = relationship(back_populates="modules")
    items: Mapped[list["ModuleItem"]] = relationship(back_populates="module")

    @property
    def canvas_course_id(self) -> str:
        return self.course.canvas_course_id


class ModuleItem(Base):
    """An inert Canvas module-item reference that may move between modules."""

    __tablename__ = "module_items"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "canvas_module_item_id",
            name="uq_module_items_course_canvas_id",
        ),
        Index("ix_module_items_course_content", "course_id", "content_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), index=True)
    canvas_module_item_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    position: Mapped[int | None] = mapped_column(Integer)
    item_type: Mapped[str] = mapped_column(String(255))
    content_id: Mapped[str | None] = mapped_column(String(255))
    html_url: Mapped[str | None] = mapped_column(String(2048))
    api_url: Mapped[str | None] = mapped_column(String(2048))
    page_url: Mapped[str | None] = mapped_column(String(2048))
    external_url: Mapped[str | None] = mapped_column(String(2048))
    new_tab: Mapped[bool | None] = mapped_column(Boolean)
    completion_requirement: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    content_details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    indent: Mapped[int | None] = mapped_column(Integer)
    published: Mapped[bool | None] = mapped_column(Boolean)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_synced_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course] = relationship(back_populates="module_items")
    module: Mapped[CourseModule] = relationship(back_populates="items")

    @property
    def canvas_course_id(self) -> str:
        return self.course.canvas_course_id

    @property
    def canvas_module_id(self) -> str:
        return self.module.canvas_module_id


class CanvasFile(Base):
    """One Canvas file identity with metadata and last valid local-copy state.

    Canvas exposes a global ``GET /api/v1/files/:id`` resource. Module-item
    provenance remains normalized in ``module_items`` and is resolved by matching
    File ``content_id`` values rather than duplicating module relationships here.
    """

    __tablename__ = "canvas_files"
    __table_args__ = (
        Index("ix_canvas_files_download_state", "download_state"),
        Index("ix_canvas_files_canvas_updated_at", "canvas_updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    canvas_file_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(1000))
    filename: Mapped[str | None] = mapped_column(String(1000))
    content_type: Mapped[str | None] = mapped_column(String(255))
    size: Mapped[int | None] = mapped_column(BigInteger)
    folder_id: Mapped[str | None] = mapped_column(String(255))
    canvas_created_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    canvas_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    canvas_modified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    unlock_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    lock_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    locked: Mapped[bool | None] = mapped_column(Boolean)
    hidden: Mapped[bool | None] = mapped_column(Boolean)
    hidden_for_user: Mapped[bool | None] = mapped_column(Boolean)
    visibility_level: Mapped[str | None] = mapped_column(String(100))
    metadata_fingerprint: Mapped[str] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_synced_at: Mapped[datetime] = mapped_column(UTCDateTime())
    downloaded_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    local_relative_path: Mapped[str | None] = mapped_column(String(2048))
    sha256: Mapped[str | None] = mapped_column(String(64))
    local_size: Mapped[int | None] = mapped_column(BigInteger)
    download_http_content_type: Mapped[str | None] = mapped_column(String(255))
    downloaded_metadata_fingerprint: Mapped[str | None] = mapped_column(String(64))
    download_state: Mapped[str] = mapped_column(String(50), default="not_downloaded")
    last_download_error: Mapped[str | None] = mapped_column(String(100))
    course_references: Mapped[list["CourseMaterialReference"]] = relationship(
        back_populates="canvas_file",
        cascade="all, delete-orphan",
    )


class CourseMaterialReference(Base):
    """Explicit course ownership/provenance for a globally identified Canvas file."""

    __tablename__ = "course_material_references"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "canvas_file_id",
            name="uq_course_material_reference",
        ),
        Index("ix_course_material_reference_course", "course_id"),
        Index("ix_course_material_reference_file", "canvas_file_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("courses.canvas_course_id", ondelete="CASCADE"),
        index=True,
    )
    canvas_file_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("canvas_files.canvas_file_id", ondelete="CASCADE"),
        index=True,
    )
    source_module_item_id: Mapped[str | None] = mapped_column(String(255))
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())

    course: Mapped[Course] = relationship()
    canvas_file: Mapped[CanvasFile] = relationship(back_populates="course_references")


class AcademicDocument(Base):
    """Latest deterministic parse state for one global Canvas file identity."""

    __tablename__ = "academic_documents"
    __table_args__ = (
        Index("ix_academic_documents_status", "status"),
        Index("ix_academic_documents_type", "detected_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    canvas_file_id: Mapped[str] = mapped_column(
        ForeignKey("canvas_files.canvas_file_id"), unique=True, index=True
    )
    detected_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))
    parser_name: Mapped[str | None] = mapped_column(String(100))
    parser_version: Mapped[str | None] = mapped_column(String(50))
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    parsed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    unit_count: Mapped[int] = mapped_column(Integer, default=0)
    character_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempted_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_attempt_source_sha256: Mapped[str | None] = mapped_column(String(64))
    last_attempt_parser_version: Mapped[str | None] = mapped_column(String(50))
    last_attempt_status: Mapped[str] = mapped_column(String(50))
    last_error_category: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())

    units: Mapped[list["DocumentUnit"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentUnit.unit_index",
    )


class DocumentUnit(Base):
    """One page, slide, section, or bounded text unit with source provenance."""

    __tablename__ = "document_units"
    __table_args__ = (
        UniqueConstraint("document_id", "unit_index", name="uq_document_units_index"),
        Index("ix_document_units_document_type", "document_id", "unit_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("academic_documents.id", ondelete="CASCADE"), index=True
    )
    unit_type: Mapped[str] = mapped_column(String(50))
    unit_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    slide_number: Mapped[int | None] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(1000))
    text: Mapped[str] = mapped_column(Text)
    text_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    character_count: Mapped[int] = mapped_column(Integer)

    document: Mapped[AcademicDocument] = relationship(back_populates="units")


class SyncRun(Base):
    """One persisted attempt to coordinate the validated synchronization stages."""

    __tablename__ = "sync_runs"
    __table_args__ = (
        Index("ix_sync_runs_started_at", "started_at"),
        Index("ix_sync_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    heartbeat_at: Mapped[datetime] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(50))
    trigger: Mapped[str] = mapped_column(String(50))
    scope_course_ids: Mapped[list[str]] = mapped_column(JSON)
    check_local_files: Mapped[bool] = mapped_column(Boolean)
    active_lock_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    stage_results: Mapped[dict[str, Any]] = mapped_column(JSON)
    change_summary: Mapped[dict[str, Any]] = mapped_column(JSON)
    change_events_created: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class ChangeEvent(Base):
    """A compact, deterministic transition observed from current academic state."""

    __tablename__ = "change_events"
    __table_args__ = (
        Index("ix_change_events_observed_at", "observed_at"),
        Index("ix_change_events_entity", "entity_type", "entity_external_id"),
        Index("ix_change_events_event_type", "event_type"),
        Index("ix_change_events_course", "course_canvas_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_external_id: Mapped[str] = mapped_column(String(255))
    course_canvas_id: Mapped[str | None] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(100))
    field_name: Mapped[str | None] = mapped_column(String(100))
    old_value: Mapped[Any | None] = mapped_column(JSON)
    new_value: Mapped[Any | None] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    source: Mapped[str] = mapped_column(String(100))
    context: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class NotificationRecord(Base):
    """Persisted local notification state keyed by deterministic dedupe identity."""

    __tablename__ = "notification_records"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_notification_dedupe_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    course_id: Mapped[str] = mapped_column(String(255), index=True)
    assignment_id: Mapped[str | None] = mapped_column(String(255), index=True)
    notification_type: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(1000))
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    source: Mapped[str] = mapped_column(String(100))
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    dedupe_key: Mapped[str] = mapped_column(String(255))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class ReminderPreferenceRecord(Base):
    """Persisted local reminder preferences for the single local user."""

    __tablename__ = "reminder_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    lead_times_hours: Mapped[list[int]] = mapped_column(JSON)
    timezone: Mapped[str] = mapped_column(String(100))
    course_overrides: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class CalendarLink(Base):
    """A user-approved provider/calendar identity without storing credentials."""

    __tablename__ = "calendar_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))
    calendar_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class CalendarAction(Base):
    """Preview/confirmation state for one immutable calendar write request."""

    __tablename__ = "calendar_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    operation: Mapped[str] = mapped_column(String(30))
    course_id: Mapped[str] = mapped_column(String(255), index=True)
    assignment_id: Mapped[str | None] = mapped_column(String(255), index=True)
    preview_fingerprint: Mapped[str] = mapped_column(String(64))
    confirmation_token_hash: Mapped[str] = mapped_column(String(64))
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    external_event_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    executed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class StudySessionRecord(Base):
    """Durable structured study continuity, not a chat transcript."""

    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    course_id: Mapped[str] = mapped_column(String(255), index=True)
    goal: Mapped[str] = mapped_column(String(1000))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    study_mode: Mapped[str] = mapped_column(String(30))
    topics: Mapped[list[str]] = mapped_column(JSON)
    assignment_ids: Mapped[list[str]] = mapped_column(JSON)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class PracticeSessionRecord(Base):
    """Durable practice state; generated questions are explicitly labeled."""

    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    course_id: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str] = mapped_column(String(500))
    study_mode: Mapped[str] = mapped_column(String(30))
    question_index: Mapped[int] = mapped_column(Integer, default=0)
    total_questions: Mapped[int] = mapped_column(Integer)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="active")
    current_question: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class PracticeTurnRecord(Base):
    """Bounded answer/feedback state for one practice question."""

    __tablename__ = "practice_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    question_id: Mapped[str | None] = mapped_column(String(255), index=True, default=None)
    question_index: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(String(2000))
    answer: Mapped[str | None] = mapped_column(String(4000))
    feedback: Mapped[str | None] = mapped_column(String(4000))
    hint: Mapped[str | None] = mapped_column(String(2000))
    generated: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class SyncRunChangeEvent(Base):
    """Transactional association between a sync run and an event it produced."""

    __tablename__ = "sync_run_change_events"
    __table_args__ = (
        UniqueConstraint("sync_run_id", "change_event_id", name="uq_sync_run_change_event"),
        Index("ix_sync_run_change_events_event", "change_event_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_id: Mapped[int] = mapped_column(ForeignKey("sync_runs.id"), index=True)
    change_event_id: Mapped[int] = mapped_column(ForeignKey("change_events.id"))
    change_event: Mapped[ChangeEvent] = relationship()


class EntityObservation(Base):
    """Last proven status for conservative absence, access, and integrity transitions."""

    __tablename__ = "entity_observations"
    __table_args__ = (
        UniqueConstraint("observation_key", name="uq_entity_observations_key"),
        Index("ix_entity_observations_entity", "entity_type", "entity_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    observation_key: Mapped[str] = mapped_column(String(1000))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_external_id: Mapped[str] = mapped_column(String(255))
    course_canvas_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    last_observed_at: Mapped[datetime] = mapped_column(UTCDateTime())
