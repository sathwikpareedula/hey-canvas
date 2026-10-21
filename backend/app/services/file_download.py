"""Idempotent controlled file download orchestration."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.database.file_repository import FileRepository
from app.files.downloader import ControlledFileDownloader, FileDownloadError
from app.files.models import CanvasFileMetadata, FileDownloadSummary
from app.files.paths import destination_for, relative_storage_path, resolve_relative_path
from app.services.file_metadata_sync import FileMetadataSource


class FileDownloadService:
    def __init__(
        self,
        *,
        source: FileMetadataSource,
        downloader: ControlledFileDownloader,
        session: Session,
        storage_root: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._downloader = downloader
        self._session = session
        self._root = storage_root
        self._clock = clock or (lambda: datetime.now(UTC))

    async def download(
        self,
        *,
        canvas_file_id: str,
        canvas_course_id: str | None = None,
        force: bool = False,
    ) -> FileDownloadSummary:
        repository = FileRepository(self._session)
        selected = repository.list_all(
            canvas_course_id=canvas_course_id,
            canvas_file_id=canvas_file_id,
        )
        if not selected:
            return FileDownloadSummary(
                files_selected=0,
                files_downloaded=0,
                files_skipped=0,
                files_failed=0,
                files_too_large=0,
                files_inaccessible=0,
            )
        record = selected[0]
        if not force and self._local_copy_is_current(record):
            return FileDownloadSummary(
                files_selected=1,
                files_downloaded=0,
                files_skipped=1,
                files_failed=0,
                files_too_large=0,
                files_inaccessible=0,
            )

        try:
            metadata = await self._source.fetch_file(record.canvas_file_id)
            repository.synchronize([metadata.snapshot], synced_at=self._clock())
            self._session.commit()
            refreshed_record = repository.get(record.canvas_file_id)
            if refreshed_record is None:
                raise RuntimeError("synchronized file record disappeared")
            await self._download_one(repository, refreshed_record, metadata)
        except FileDownloadError as exc:
            self._session.rollback()
            current = repository.get(record.canvas_file_id)
            if current is not None:
                repository.record_download_failure(current, exc.category)
                self._session.commit()
            return FileDownloadSummary(
                files_selected=1,
                files_downloaded=0,
                files_skipped=0,
                files_failed=int(exc.category not in {"too_large", "inaccessible"}),
                files_too_large=int(exc.category == "too_large"),
                files_inaccessible=int(exc.category == "inaccessible"),
            )
        return FileDownloadSummary(
            files_selected=1,
            files_downloaded=1,
            files_skipped=0,
            files_failed=0,
            files_too_large=0,
            files_inaccessible=0,
        )

    async def _download_one(
        self,
        repository: FileRepository,
        record: object,
        metadata: CanvasFileMetadata,
    ) -> None:
        from app.database.models import CanvasFile

        if not isinstance(record, CanvasFile):
            raise TypeError("record must be a CanvasFile")
        if metadata.download_url is None:
            raise FileDownloadError(
                "Canvas file metadata has no download URL", category="inaccessible"
            )
        old_relative_path = record.local_relative_path
        destination = destination_for(
            self._root,
            canvas_file_id=record.canvas_file_id,
            filename=record.filename or record.display_name,
        )
        result = await self._downloader.download(
            metadata.download_url,
            destination,
            storage_root=self._root,
        )
        new_relative_path = relative_storage_path(self._root, destination)
        repository.record_download_success(
            record,
            downloaded_at=self._clock(),
            local_relative_path=new_relative_path,
            sha256=result.sha256,
            local_size=result.size,
            http_content_type=result.http_content_type,
        )
        self._session.commit()
        if old_relative_path and old_relative_path != new_relative_path:
            old_path = resolve_relative_path(self._root, old_relative_path)
            old_path.unlink(missing_ok=True)

    def _local_copy_is_current(self, record: object) -> bool:
        from app.database.models import CanvasFile

        if not isinstance(record, CanvasFile):
            return False
        if (
            record.download_state != "downloaded"
            or not record.local_relative_path
            or not record.sha256
            or record.local_size is None
            or record.downloaded_metadata_fingerprint != record.metadata_fingerprint
        ):
            return False
        try:
            path = resolve_relative_path(self._root, record.local_relative_path)
        except ValueError:
            return False
        if not path.is_file() or path.stat().st_size != record.local_size:
            return False
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == record.sha256
