"""Typed values for Canvas file metadata, provenance, and download results."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DownloadState = Literal["not_downloaded", "downloaded", "failed", "too_large", "inaccessible"]


class FileSnapshot(BaseModel):
    """Normalized metadata for one global Canvas file identity."""

    model_config = ConfigDict(frozen=True)

    canvas_file_id: str
    display_name: str | None = None
    filename: str | None = None
    content_type: str | None = None
    size: int | None = None
    folder_id: str | None = None
    canvas_created_at: datetime | None = None
    canvas_updated_at: datetime | None = None
    canvas_modified_at: datetime | None = None
    unlock_at: datetime | None = None
    lock_at: datetime | None = None
    locked: bool | None = None
    hidden: bool | None = None
    hidden_for_user: bool | None = None
    visibility_level: str | None = None


class CanvasFileMetadata(BaseModel):
    """Metadata plus an ephemeral download URL that is never persisted or serialized."""

    model_config = ConfigDict(frozen=True)

    snapshot: FileSnapshot
    download_url: str | None = None


class FileSyncFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    canvas_file_id: str
    error_type: str
    message: str


class FileMetadataSyncSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    references_seen: int
    unique_file_ids: int
    metadata_succeeded: int
    metadata_failed: int
    files_created: int
    files_updated: int
    files_unchanged: int
    failures: tuple[FileSyncFailure, ...] = ()


class FileReference(BaseModel):
    """One persisted module-item reference to a Canvas file."""

    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    canvas_module_id: str
    canvas_module_item_id: str
    module_name: str | None
    item_title: str | None


class FileRecordView(BaseModel):
    """Local-only safe file representation; signed URLs and absolute paths are excluded."""

    canvas_file_id: str
    display_name: str | None
    filename: str | None
    content_type: str | None
    size: int | None
    folder_id: str | None
    canvas_created_at: datetime | None
    canvas_updated_at: datetime | None
    canvas_modified_at: datetime | None
    unlock_at: datetime | None
    lock_at: datetime | None
    locked: bool | None
    hidden: bool | None
    hidden_for_user: bool | None
    visibility_level: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_synced_at: datetime
    downloaded_at: datetime | None
    local_relative_path: str | None
    sha256: str | None
    local_size: int | None
    download_http_content_type: str | None
    download_state: DownloadState
    last_download_error: str | None
    references: list[FileReference]


class FileDownloadSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    files_selected: int
    files_downloaded: int
    files_skipped: int
    files_failed: int
    files_too_large: int
    files_inaccessible: int
