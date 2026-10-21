"""Local-only file metadata and provenance projection."""

from sqlalchemy.orm import Session

from app.database.file_repository import FileRepository
from app.files.models import DownloadState, FileRecordView


class FileQueryService:
    def __init__(self, session: Session) -> None:
        self._repository = FileRepository(session)

    def list_files(
        self,
        *,
        canvas_course_id: str | None = None,
        download_state: DownloadState | None = None,
        canvas_file_id: str | None = None,
    ) -> list[FileRecordView]:
        records = self._repository.list_all(
            canvas_course_id=canvas_course_id,
            download_state=download_state,
            canvas_file_id=canvas_file_id,
        )
        references = self._repository.references_for(item.canvas_file_id for item in records)
        return [
            FileRecordView(
                canvas_file_id=item.canvas_file_id,
                display_name=item.display_name,
                filename=item.filename,
                content_type=item.content_type,
                size=item.size,
                folder_id=item.folder_id,
                canvas_created_at=item.canvas_created_at,
                canvas_updated_at=item.canvas_updated_at,
                canvas_modified_at=item.canvas_modified_at,
                unlock_at=item.unlock_at,
                lock_at=item.lock_at,
                locked=item.locked,
                hidden=item.hidden,
                hidden_for_user=item.hidden_for_user,
                visibility_level=item.visibility_level,
                first_seen_at=item.first_seen_at,
                last_seen_at=item.last_seen_at,
                last_synced_at=item.last_synced_at,
                downloaded_at=item.downloaded_at,
                local_relative_path=item.local_relative_path,
                sha256=item.sha256,
                local_size=item.local_size,
                download_http_content_type=item.download_http_content_type,
                download_state=item.download_state,
                last_download_error=item.last_download_error,
                references=references.get(item.canvas_file_id, []),
            )
            for item in records
        ]
