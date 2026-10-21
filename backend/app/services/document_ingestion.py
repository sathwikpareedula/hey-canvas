"""Explicit, bounded academic document ingestion using validated local files."""

import hashlib
from collections.abc import Collection
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.canvas.exceptions import CanvasAPIError, CanvasError
from app.database.document_repository import DocumentRepository
from app.database.file_repository import FileRepository
from app.database.models import CanvasFile
from app.documents.models import (
    DocumentLimits,
    IngestionOutcome,
    IngestionPlan,
    IngestionSummary,
    KnowledgePreparationSummary,
)
from app.documents.parsing import (
    PARSER_NAME,
    PARSER_VERSION,
    DocumentParseError,
    detect_document_type,
    parse_document,
    supported_candidate,
)
from app.files.models import FileDownloadSummary
from app.files.paths import resolve_relative_path


class ExistingFileDownloader(Protocol):
    async def download(
        self,
        *,
        canvas_file_id: str,
        canvas_course_id: str | None = None,
        force: bool = False,
    ) -> FileDownloadSummary: ...


class DocumentIngestionService:
    """Parse one file identity once, regardless of how many module items reference it.

    Batch processing is deliberately sequential. A concurrency bound of one avoids
    sharing a non-thread-safe SQLAlchemy Session and remains predictable for a personal
    local application; later workers can create independent service/session instances.
    """

    def __init__(
        self,
        *,
        session: Session,
        storage_root: Path,
        limits: DocumentLimits,
        downloader: ExistingFileDownloader | None = None,
    ) -> None:
        self._session = session
        self._root = storage_root
        self._limits = limits
        self._downloader = downloader

    def plan_course(
        self,
        canvas_course_id: str,
        *,
        max_new_download_files: int,
        max_new_download_bytes: int,
    ) -> IngestionPlan:
        eligible = self._eligible_course_files(canvas_course_id)
        local = 0
        selected_downloads = 0
        selected_bytes = 0
        deferred = 0
        for record in eligible:
            if self._local_source(record)[0] is not None:
                local += 1
                continue
            size = record.size
            if (
                size is None
                or selected_downloads >= max_new_download_files
                or selected_bytes + size > max_new_download_bytes
            ):
                deferred += 1
                continue
            selected_downloads += 1
            selected_bytes += size
        return IngestionPlan(
            canvas_course_id=canvas_course_id,
            eligible_files=len(eligible),
            already_local_files=local,
            new_download_files=selected_downloads,
            new_download_bytes=selected_bytes,
            deferred_files=deferred,
        )

    async def ingest_file(
        self,
        canvas_file_id: str,
        *,
        canvas_course_id: str | None = None,
        allow_download: bool = False,
    ) -> IngestionOutcome:
        files = FileRepository(self._session).list_all(
            canvas_course_id=canvas_course_id, canvas_file_id=canvas_file_id
        )
        if not files:
            return IngestionOutcome(
                canvas_file_id=canvas_file_id,
                status="failed",
                error_category="file_not_found",
            )
        record = files[0]
        references = FileRepository(self._session).references_for([canvas_file_id]).get(
            canvas_file_id, []
        )
        if not references and (
            canvas_course_id is None
            or not FileRepository(self._session).course_owns_file(
                canvas_course_id, canvas_file_id
            )
        ):
            return IngestionOutcome(
                canvas_file_id=canvas_file_id,
                status="failed",
                error_category="no_academic_provenance",
            )
        downloaded = False
        downloaded_bytes = 0
        source, source_problem = self._local_source(record)
        if source is None and allow_download:
            if self._downloader is None:
                return self._failure(record, "download_required", "downloader_unavailable")
            try:
                summary = await self._downloader.download(
                    canvas_file_id=canvas_file_id,
                    canvas_course_id=canvas_course_id,
                )
            except CanvasAPIError as exc:
                category = (
                    "inaccessible"
                    if exc.status_code in {401, 403, 404}
                    else "download_failed"
                )
                return self._failure(record, "download_required", category)
            except CanvasError:
                return self._failure(record, "download_required", "download_failed")
            downloaded = summary.files_downloaded == 1
            if not (summary.files_downloaded or summary.files_skipped):
                category = (
                    "too_large"
                    if summary.files_too_large
                    else "inaccessible"
                    if summary.files_inaccessible
                    else "download_failed"
                )
                return self._failure(record, "download_required", category)
            self._session.expire_all()
            refreshed = FileRepository(self._session).get(canvas_file_id)
            if refreshed is None:
                return self._failure(record, "failed", "file_state_missing")
            record = refreshed
            if downloaded:
                downloaded_bytes = record.local_size or 0
            source, source_problem = self._local_source(record)
        if source is None:
            status = source_problem or "download_required"
            return self._failure(record, status, status)
        if record.sha256 is None:
            return self._failure(record, "source_corrupt", "missing_source_hash")
        repository = DocumentRepository(self._session)
        if repository.cache_is_current(record.canvas_file_id, record.sha256, PARSER_VERSION):
            document = repository.get(record.canvas_file_id)
            if document is None:
                return self._failure(record, "failed", "document_state_missing")
            return IngestionOutcome(
                canvas_file_id=record.canvas_file_id,
                status=document.last_attempt_status,
                skipped=True,
                downloaded=downloaded,
                downloaded_bytes=downloaded_bytes,
                units=document.unit_count,
                characters=document.character_count,
            )
        attempted_at = datetime.now(UTC)
        detected_type: str | None = None
        try:
            detected_type = detect_document_type(
                source,
                filename=record.filename or record.display_name,
                content_type=record.content_type,
                limits=self._limits,
            )
            result = parse_document(source, detected_type, self._limits)
            repository.replace_success(
                canvas_file_id=record.canvas_file_id,
                source_sha256=record.sha256,
                result=result,
                attempted_at=attempted_at,
            )
            self._session.commit()
            return IngestionOutcome(
                canvas_file_id=record.canvas_file_id,
                status=result.status,
                parsed=True,
                downloaded=downloaded,
                downloaded_bytes=downloaded_bytes,
                units=len(result.units),
                characters=result.character_count,
            )
        except DocumentParseError as exc:
            self._session.rollback()
            status = (
                "unsupported"
                if exc.category.startswith("unsupported") or exc.category == "type_mismatch"
                else "failed"
            )
            repository = DocumentRepository(self._session)
            repository.record_failure(
                canvas_file_id=record.canvas_file_id,
                source_sha256=record.sha256,
                attempted_at=attempted_at,
                status=status,
                error_category=exc.category,
                detected_type=detected_type,
                parser_name=PARSER_NAME,
                parser_version=PARSER_VERSION,
            )
            self._session.commit()
            return IngestionOutcome(
                canvas_file_id=record.canvas_file_id,
                status=status,
                downloaded=downloaded,
                downloaded_bytes=downloaded_bytes,
                error_category=exc.category,
            )
        except SQLAlchemyError:
            self._session.rollback()
            return IngestionOutcome(
                canvas_file_id=record.canvas_file_id,
                status="failed",
                downloaded=downloaded,
                downloaded_bytes=downloaded_bytes,
                error_category="database_error",
            )

    async def ingest_files(
        self,
        canvas_file_ids: Collection[str],
        *,
        canvas_course_id: str | None = None,
        allow_download_ids: Collection[str] = (),
    ) -> IngestionSummary:
        unique_ids = tuple(dict.fromkeys(canvas_file_ids))
        if len(unique_ids) > 500:
            raise ValueError("at most 500 files may be ingested in one explicit batch")
        allowed = set(allow_download_ids)
        outcomes = [
            await self.ingest_file(
                file_id,
                canvas_course_id=canvas_course_id,
                allow_download=file_id in allowed,
            )
            for file_id in unique_ids
        ]
        return self._summary(outcomes)

    async def ingest_course(
        self,
        canvas_course_id: str,
        *,
        allow_download: bool = False,
        max_new_download_files: int = 15,
        max_new_download_bytes: int = 50 * 1024 * 1024,
    ) -> IngestionSummary:
        eligible = self._eligible_course_files(canvas_course_id)
        allowed: list[str] = []
        bytes_planned = 0
        if allow_download:
            for record in eligible:
                if self._local_source(record)[0] is not None:
                    continue
                if record.size is None:
                    continue
                if len(allowed) >= max_new_download_files:
                    continue
                if bytes_planned + record.size > max_new_download_bytes:
                    continue
                allowed.append(record.canvas_file_id)
                bytes_planned += record.size
        return await self.ingest_files(
            [record.canvas_file_id for record in eligible],
            canvas_course_id=canvas_course_id,
            allow_download_ids=allowed,
        )

    async def prepare_courses(
        self,
        canvas_course_ids: Collection[str],
        *,
        max_new_download_files: int,
        max_new_download_bytes: int,
        max_files_considered: int = 500,
    ) -> KnowledgePreparationSummary:
        """Incrementally prepare a fair, globally bounded set of course files."""

        course_ids = tuple(dict.fromkeys(canvas_course_ids))
        by_course = {
            course_id: self._eligible_course_files(course_id) for course_id in course_ids
        }
        ordered: list[tuple[str, CanvasFile]] = []
        seen: set[str] = set()
        offset = 0
        while len(ordered) < max_files_considered:
            added = False
            for course_id in course_ids:
                records = by_course[course_id]
                if offset >= len(records):
                    continue
                added = True
                record = records[offset]
                if record.canvas_file_id not in seen:
                    seen.add(record.canvas_file_id)
                    ordered.append((course_id, record))
                    if len(ordered) >= max_files_considered:
                        break
            if not added:
                break
            offset += 1

        download_ids: set[str] = set()
        bytes_planned = 0
        deferred = 0
        for _, record in ordered:
            if self._local_source(record)[0] is not None:
                continue
            size = record.size
            if (
                size is None
                or len(download_ids) >= max_new_download_files
                or bytes_planned + size > max_new_download_bytes
            ):
                deferred += 1
                continue
            download_ids.add(record.canvas_file_id)
            bytes_planned += size

        outcomes: list[IngestionOutcome] = []
        for course_id, record in ordered:
            needs_download = self._local_source(record)[0] is None
            if needs_download and record.canvas_file_id not in download_ids:
                continue
            outcomes.append(
                await self.ingest_file(
                    record.canvas_file_id,
                    canvas_course_id=course_id,
                    allow_download=record.canvas_file_id in download_ids,
                )
            )
        unique_eligible = len(
            {item.canvas_file_id for values in by_course.values() for item in values}
        )
        return KnowledgePreparationSummary(
            courses_selected=len(course_ids),
            files_considered=len(ordered),
            files_prepared=sum(item.parsed for item in outcomes),
            files_unchanged=sum(item.skipped for item in outcomes),
            files_deferred=deferred + max(0, unique_eligible - len(ordered)),
            files_failed=sum(
                item.status in {
                    "failed",
                    "source_missing",
                    "source_corrupt",
                    "download_required",
                }
                for item in outcomes
            ),
            files_needing_ocr=sum(item.status == "needs_ocr" for item in outcomes),
            files_unsupported=sum(item.status == "unsupported" for item in outcomes),
            files_downloaded=sum(item.downloaded for item in outcomes),
            downloaded_bytes=sum(item.downloaded_bytes for item in outcomes),
        )

    def _eligible_course_files(self, canvas_course_id: str) -> list[CanvasFile]:
        return [
            record
            for record in FileRepository(self._session).list_all(
                canvas_course_id=canvas_course_id
            )
            if supported_candidate(record.filename or record.display_name, record.content_type)
        ]

    def _local_source(self, record: CanvasFile) -> tuple[Path | None, str | None]:
        if record.local_relative_path is None:
            return None, "download_required"
        try:
            path = resolve_relative_path(self._root, record.local_relative_path)
        except ValueError:
            return None, "source_corrupt"
        if not path.is_file():
            return None, "source_missing"
        if record.local_size is None or path.stat().st_size != record.local_size:
            return None, "source_corrupt"
        if record.sha256 is None or _sha256(path) != record.sha256:
            return None, "source_corrupt"
        # Metadata sync is non-downloading. Preserve the prior valid local copy for
        # rollback, but never present it as the current professor file after Canvas
        # reports changed source metadata.
        if record.downloaded_metadata_fingerprint != record.metadata_fingerprint:
            return None, "download_required"
        return path, None

    def _failure(self, record: CanvasFile, status: str, category: str) -> IngestionOutcome:
        attempted_at = datetime.now(UTC)
        DocumentRepository(self._session).record_failure(
            canvas_file_id=record.canvas_file_id,
            source_sha256=record.sha256,
            attempted_at=attempted_at,
            status=status,
            error_category=category,
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
        )
        self._session.commit()
        return IngestionOutcome(
            canvas_file_id=record.canvas_file_id,
            status=status,
            error_category=category,
        )

    @staticmethod
    def _summary(outcomes: list[IngestionOutcome]) -> IngestionSummary:
        return IngestionSummary(
            files_selected=len(outcomes),
            files_parsed=sum(item.parsed for item in outcomes),
            files_skipped=sum(item.skipped for item in outcomes),
            files_failed=sum(
                item.status in {"failed", "source_missing", "source_corrupt"}
                for item in outcomes
            ),
            files_unsupported=sum(item.status == "unsupported" for item in outcomes),
            files_needing_ocr=sum(item.status == "needs_ocr" for item in outcomes),
            files_download_required=sum(item.status == "download_required" for item in outcomes),
            files_downloaded=sum(item.downloaded for item in outcomes),
            downloaded_bytes=sum(item.downloaded_bytes for item in outcomes),
            units_written=sum(item.units for item in outcomes if item.parsed),
            characters_written=sum(item.characters for item in outcomes if item.parsed),
            outcomes=tuple(outcomes),
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
