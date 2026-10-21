"""Bounded, failure-isolated synchronization of module-referenced file metadata."""

import asyncio
import logging
from collections.abc import Callable, Collection
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.database.change_repository import ChangeRecorder
from app.database.course_repository import CourseRepository
from app.database.file_repository import FileRepository
from app.files.models import CanvasFileMetadata, FileMetadataSyncSummary, FileSyncFailure
from app.services.sync_errors import safe_sync_failure_message

logger = logging.getLogger(__name__)


class FileMetadataSource(Protocol):
    async def fetch_file(self, canvas_file_id: str) -> CanvasFileMetadata: ...


class FileMetadataSyncService:
    def __init__(
        self,
        *,
        source: FileMetadataSource,
        session: Session,
        concurrency: int = 5,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not 1 <= concurrency <= 20:
            raise ValueError("concurrency must be between 1 and 20")
        self._source = source
        self._session = session
        self._concurrency = concurrency
        self._clock = clock or (lambda: datetime.now(UTC))

    async def synchronize(
        self,
        *,
        canvas_course_id: str | None = None,
        canvas_course_ids: Collection[str] | None = None,
    ) -> FileMetadataSyncSummary:
        repository = FileRepository(self._session)
        references = repository.discover_references(
            canvas_course_id=canvas_course_id,
            canvas_course_ids=canvas_course_ids,
        )
        unique_ids = list(dict.fromkeys(file_id for file_id, _ in references))
        semaphore = asyncio.Semaphore(self._concurrency)

        async def fetch(file_id: str) -> tuple[str, CanvasFileMetadata | None, Exception | None]:
            async with semaphore:
                try:
                    return file_id, await self._source.fetch_file(file_id), None
                except Exception as exc:
                    return file_id, None, exc

        results = await asyncio.gather(*(fetch(file_id) for file_id in unique_ids))
        metadata: list[CanvasFileMetadata] = []
        failures: list[FileSyncFailure] = []
        for file_id, item, error in results:
            if error is not None:
                failure = _safe_failure(file_id, error)
                failures.append(failure)
                logger.warning(
                    "Canvas file metadata synchronization failed for one file",
                    extra={
                        "operation": "files.metadata.sync",
                        "entity": file_id,
                        "status": "failed",
                        "error": failure.error_type,
                    },
                )
            elif item is not None:
                metadata.append(item)

        try:
            observed_at = self._clock()
            created, updated, unchanged = repository.synchronize(
                (item.snapshot for item in metadata), synced_at=observed_at
            )
            scoped_courses = (
                set(canvas_course_ids)
                if canvas_course_ids is not None
                else {canvas_course_id}
                if canvas_course_id is not None
                else {
                    course.canvas_course_id
                    for course in CourseRepository(self._session).list_syncable()
                }
            )
            repository.reconcile_course_references(
                references,
                canvas_course_ids={item for item in scoped_courses if item is not None},
            )
            recorder = ChangeRecorder(
                self._session, observed_at=observed_at, source="canvas_file_metadata"
            )
            for item in metadata:
                self._observe_access(
                    repository,
                    recorder,
                    item.snapshot.canvas_file_id,
                    "accessible",
                    transition_event="field_changed",
                )
            for file_id, _, error in results:
                if _status_code(error) in {403, 404} and repository.get(file_id) is not None:
                    self._observe_access(
                        repository,
                        recorder,
                        file_id,
                        "inaccessible",
                        transition_event="entity_became_inaccessible",
                        emit_initial=True,
                    )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return FileMetadataSyncSummary(
            references_seen=len(references),
            unique_file_ids=len(unique_ids),
            metadata_succeeded=len(metadata),
            metadata_failed=len(failures),
            files_created=created,
            files_updated=updated,
            files_unchanged=unchanged,
            failures=tuple(failures),
        )

    @staticmethod
    def _observe_access(
        repository: FileRepository,
        recorder: ChangeRecorder,
        file_id: str,
        status: str,
        *,
        transition_event: str,
        emit_initial: bool = False,
    ) -> None:
        for course_id in repository.reference_courses([file_id]).get(file_id, [None]):
            previous = recorder.observe_status(
                key=f"canvas_file_access:{file_id}:{course_id or ''}",
                entity_type="file",
                external_id=file_id,
                course_id=course_id,
                status=status,
                transition_event=transition_event,
            )
            if previous is None and emit_initial:
                recorder.record(
                    entity_type="file",
                    external_id=file_id,
                    course_id=course_id,
                    event_type=transition_event,
                    field_name="access_status",
                    old_value="accessible",
                    new_value=status,
                )


def _safe_failure(file_id: str, exc: Exception) -> FileSyncFailure:
    return FileSyncFailure(
        canvas_file_id=file_id,
        error_type=type(exc).__name__,
        message=safe_sync_failure_message(
            exc,
            local_message="File metadata synchronization failed locally",
        ),
    )


def _status_code(error: Exception | None) -> int | None:
    return getattr(error, "status_code", None)
