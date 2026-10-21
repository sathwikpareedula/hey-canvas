"""Managed local storage inspection, metrics, and safe maintenance service."""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import (
    AcademicDocument,
    CanvasFile,
    CourseMaterialReference,
    DocumentUnit,
    SyncRun,
)

logger = logging.getLogger(__name__)


class StorageSummary(BaseModel):
    """Machine-readable and user-facing storage usage metrics."""

    model_config = ConfigDict(frozen=True)

    total_storage_bytes: int
    database_bytes: int
    cached_files_bytes: int
    cached_files_count: int
    indexed_documents_count: int
    indexed_units_count: int
    metadata_only_files_count: int
    needs_ocr_files_count: int
    failed_documents_count: int
    orphaned_files_count: int
    orphaned_files_bytes: int
    temp_files_count: int
    temp_files_bytes: int
    last_sync_timestamp: datetime | None
    last_sync_status: str | None
    storage_root: str
    database_path: str


class CourseStoragePreview(BaseModel):
    """Course-scoped preview of storage and knowledge preparation size."""

    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    total_files: int
    downloaded_files: int
    not_downloaded_files: int
    total_file_bytes: int
    estimated_new_download_bytes: int
    indexed_documents: int
    needs_ocr_documents: int


class StorageCleanupRequest(BaseModel):
    confirm: bool = False
    remove_temp_files: bool = True
    remove_orphans: bool = False


class StorageCleanupResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    message: str
    bytes_freed: int
    files_removed: int
    is_dry_run: bool


class StorageManagementService:
    """Service to measure, inspect, and safely maintain local Hey Canvas storage."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def _resolve_db_path(self) -> Path | None:
        db_url = self._settings.database_url
        if db_url.startswith("sqlite:///"):
            raw_path = db_url.removeprefix("sqlite:///")
            p = Path(raw_path)
            if not p.is_absolute():
                p = Path.cwd() / p
            return p.resolve()
        return None

    def get_summary(self) -> StorageSummary:
        # 1. Database file size
        db_path = self._resolve_db_path()
        db_bytes = db_path.stat().st_size if db_path and db_path.exists() else 0

        # 2. Database statistics
        metadata_only_count = (
            self._session.scalar(
                select(func.count(CanvasFile.id)).where(
                    CanvasFile.download_state == "not_downloaded"
                )
            )
            or 0
        )
        indexed_doc_count = (
            self._session.scalar(
                select(func.count(AcademicDocument.id)).where(
                    AcademicDocument.status == "parsed"
                )
            )
            or 0
        )
        needs_ocr_count = (
            self._session.scalar(
                select(func.count(AcademicDocument.id)).where(
                    AcademicDocument.status == "needs_ocr"
                )
            )
            or 0
        )
        failed_doc_count = (
            self._session.scalar(
                select(func.count(AcademicDocument.id)).where(AcademicDocument.status == "failed")
            )
            or 0
        )
        indexed_unit_count = (
            self._session.scalar(select(func.count(DocumentUnit.id))) or 0
        )

        # 3. Latest Sync Run
        latest_sync = self._session.scalars(
            select(SyncRun).order_by(SyncRun.started_at.desc()).limit(1)
        ).first()
        last_sync_ts = latest_sync.started_at if latest_sync else None
        last_sync_stat = latest_sync.status if latest_sync else None

        # 4. Filesystem scan of storage root
        root = self._settings.academic_files_root.expanduser().resolve()
        cached_bytes = 0
        cached_count = 0
        temp_bytes = 0
        temp_count = 0
        orphaned_bytes = 0
        orphaned_count = 0

        known_paths: set[str] = set()
        for local_rel in self._session.scalars(
            select(CanvasFile.local_relative_path).where(CanvasFile.local_relative_path.is_not(None))
        ):
            if local_rel:
                known_paths.add(Path(local_rel).as_posix())

        if root.exists() and root.is_dir():
            for entry in root.rglob("*"):
                if entry.is_file():
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0
                    rel_posix = entry.relative_to(root).as_posix()
                    name = entry.name

                    if name.startswith(".canvas-download-") and name.endswith(".part"):
                        temp_count += 1
                        temp_bytes += size
                    elif rel_posix in known_paths:
                        cached_count += 1
                        cached_bytes += size
                    else:
                        orphaned_count += 1
                        orphaned_bytes += size

        total_bytes = db_bytes + cached_bytes + temp_bytes + orphaned_bytes

        return StorageSummary(
            total_storage_bytes=total_bytes,
            database_bytes=db_bytes,
            cached_files_bytes=cached_bytes,
            cached_files_count=cached_count,
            indexed_documents_count=indexed_doc_count,
            indexed_units_count=indexed_unit_count,
            metadata_only_files_count=metadata_only_count,
            needs_ocr_files_count=needs_ocr_count,
            failed_documents_count=failed_doc_count,
            orphaned_files_count=orphaned_count,
            orphaned_files_bytes=orphaned_bytes,
            temp_files_count=temp_count,
            temp_files_bytes=temp_bytes,
            last_sync_timestamp=last_sync_ts,
            last_sync_status=last_sync_stat,
            storage_root=str(root),
            database_path=str(db_path or "in-memory"),
        )

    def course_preview(self, canvas_course_id: str) -> CourseStoragePreview:
        """Estimate preparation size and file counts for a specific course."""
        file_ids = set(
            self._session.scalars(
                select(CourseMaterialReference.canvas_file_id).where(
                    CourseMaterialReference.course_id == canvas_course_id
                )
            )
        )
        if not file_ids:
            return CourseStoragePreview(
                canvas_course_id=canvas_course_id,
                total_files=0,
                downloaded_files=0,
                not_downloaded_files=0,
                total_file_bytes=0,
                estimated_new_download_bytes=0,
                indexed_documents=0,
                needs_ocr_documents=0,
            )

        files = list(
            self._session.scalars(
                select(CanvasFile).where(CanvasFile.canvas_file_id.in_(file_ids))
            )
        )
        downloaded = 0
        not_downloaded = 0
        total_bytes = 0
        est_new_bytes = 0

        for f in files:
            size = f.size or 0
            total_bytes += size
            if f.download_state == "downloaded":
                downloaded += 1
            else:
                not_downloaded += 1
                est_new_bytes += size

        indexed = (
            self._session.scalar(
                select(func.count(AcademicDocument.id)).where(
                    AcademicDocument.canvas_file_id.in_(file_ids),
                    AcademicDocument.status == "parsed",
                )
            )
            or 0
        )
        needs_ocr = (
            self._session.scalar(
                select(func.count(AcademicDocument.id)).where(
                    AcademicDocument.canvas_file_id.in_(file_ids),
                    AcademicDocument.status == "needs_ocr",
                )
            )
            or 0
        )

        return CourseStoragePreview(
            canvas_course_id=canvas_course_id,
            total_files=len(files),
            downloaded_files=downloaded,
            not_downloaded_files=not_downloaded,
            total_file_bytes=total_bytes,
            estimated_new_download_bytes=est_new_bytes,
            indexed_documents=indexed,
            needs_ocr_documents=needs_ocr,
        )

    def cleanup(
        self,
        *,
        remove_temp_files: bool = True,
        remove_orphans: bool = False,
        confirm: bool = False,
    ) -> StorageCleanupResult:
        """Safely prune temporary download files and unreferenced orphan files."""
        root = self._settings.academic_files_root.expanduser().resolve()
        if not root.exists() or not root.is_dir():
            return StorageCleanupResult(
                ok=True,
                message="Storage root directory does not exist; nothing to clean.",
                bytes_freed=0,
                files_removed=0,
                is_dry_run=not confirm,
            )

        known_paths: set[str] = set()
        for local_rel in self._session.scalars(
            select(CanvasFile.local_relative_path).where(CanvasFile.local_relative_path.is_not(None))
        ):
            if local_rel:
                known_paths.add(Path(local_rel).as_posix())

        targets: list[Path] = []
        freed_bytes = 0

        for entry in root.rglob("*"):
            if entry.is_file():
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                rel_posix = entry.relative_to(root).as_posix()
                name = entry.name

                is_temp = (
                    remove_temp_files
                    and name.startswith(".canvas-download-")
                    and name.endswith(".part")
                )
                is_orphan = remove_orphans and rel_posix not in known_paths
                if is_temp or is_orphan:
                    targets.append(entry)
                    freed_bytes += size

        if not confirm:
            msg = (
                f"Dry run: {len(targets)} files ({freed_bytes} bytes) eligible for cleanup. "
                "Set confirm=True to execute."
            )
            return StorageCleanupResult(
                ok=True,
                message=msg,
                bytes_freed=freed_bytes,
                files_removed=len(targets),
                is_dry_run=True,
            )

        removed_count = 0
        for target in targets:
            try:
                target.unlink(missing_ok=True)
                removed_count += 1
            except OSError as err:
                logger.warning("Failed to remove storage cleanup target %s: %s", target, err)

        # Remove empty parent directories inside storage root
        for parent in sorted(root.glob("*"), reverse=True):
            if parent.is_dir() and not any(parent.iterdir()):
                with contextlib.suppress(OSError):
                    parent.rmdir()

        return StorageCleanupResult(
            ok=True,
            message=f"Cleaned {removed_count} files ({freed_bytes} bytes freed).",
            bytes_freed=freed_bytes,
            files_removed=removed_count,
            is_dry_run=False,
        )
