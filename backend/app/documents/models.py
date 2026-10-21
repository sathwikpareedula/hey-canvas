"""Typed contracts for document parsing, ingestion, querying, and search."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.files.models import FileReference

DocumentType = Literal["pdf", "pptx", "docx", "text", "markdown", "csv"]
DocumentStatus = Literal[
    "not_ingested",
    "download_required",
    "parsed",
    "unsupported",
    "needs_ocr",
    "failed",
    "source_missing",
    "source_corrupt",
]


class DocumentLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_source_bytes: int
    max_characters: int
    max_units: int
    max_unit_characters: int
    max_archive_entries: int
    max_archive_uncompressed_bytes: int
    max_archive_ratio: int


class ParsedUnit(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_type: str
    unit_index: int
    page_number: int | None = None
    slide_number: int | None = None
    heading: str | None = None
    text: str
    text_fingerprint: str
    character_count: int


class ParseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    detected_type: DocumentType
    status: Literal["parsed", "needs_ocr"]
    parser_name: str
    parser_version: str
    units: tuple[ParsedUnit, ...]
    character_count: int


class DocumentView(BaseModel):
    canvas_file_id: str
    display_name: str | None
    filename: str | None
    content_type: str | None
    detected_type: str | None
    status: str
    parser_name: str | None
    parser_version: str | None
    source_sha256: str | None
    parsed_at: datetime | None
    unit_count: int
    character_count: int
    last_attempted_at: datetime
    last_attempt_status: str
    last_error_category: str | None
    is_stale: bool
    references: list[FileReference]


class DocumentUnitView(BaseModel):
    canvas_file_id: str
    source_sha256: str | None
    parser_name: str | None
    parser_version: str | None
    unit_type: str
    unit_index: int
    page_number: int | None
    slide_number: int | None
    heading: str | None
    text: str
    text_fingerprint: str
    character_count: int
    references: list[FileReference]


class DocumentSearchHit(BaseModel):
    canvas_file_id: str
    display_name: str | None
    filename: str | None
    unit_type: str
    unit_index: int
    page_number: int | None
    slide_number: int | None
    heading: str | None
    snippet: str
    score: int
    source_sha256: str
    is_stale: bool
    references: list[FileReference]


class IngestionOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    canvas_file_id: str
    status: str
    parsed: bool = False
    skipped: bool = False
    downloaded: bool = False
    downloaded_bytes: int = 0
    units: int = 0
    characters: int = 0
    error_category: str | None = None


class IngestionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    eligible_files: int
    already_local_files: int
    new_download_files: int
    new_download_bytes: int
    deferred_files: int


class IngestionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    files_selected: int
    files_parsed: int
    files_skipped: int
    files_failed: int
    files_unsupported: int
    files_needing_ocr: int
    files_download_required: int
    files_downloaded: int
    downloaded_bytes: int
    units_written: int
    characters_written: int
    outcomes: tuple[IngestionOutcome, ...]


class CourseDocumentCoverage(BaseModel):
    """Safe per-course summary of locally usable Canvas document evidence."""

    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    known_files: int
    eligible_files: int
    indexed_current: int
    indexed_stale: int
    awaiting_download: int
    needs_ocr: int
    unsupported: int
    failed: int


class KnowledgePreparationSummary(BaseModel):
    """Bounded result persisted as the knowledge stage of a Canvas sync run."""

    model_config = ConfigDict(frozen=True)

    courses_selected: int
    files_considered: int
    files_prepared: int
    files_unchanged: int
    files_deferred: int
    files_failed: int
    files_needing_ocr: int
    files_unsupported: int
    files_downloaded: int
    downloaded_bytes: int
