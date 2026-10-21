"""Local-only document state and unit projections."""

from sqlalchemy.orm import Session

from app.database.document_repository import DocumentRepository
from app.database.file_repository import FileRepository
from app.documents.models import CourseDocumentCoverage, DocumentUnitView, DocumentView
from app.documents.parsing import supported_candidate


class DocumentQueryService:
    def __init__(self, session: Session) -> None:
        self._repository = DocumentRepository(session)

    def list_documents(
        self,
        *,
        canvas_course_id: str | None = None,
        status: str | None = None,
        detected_type: str | None = None,
        canvas_file_id: str | None = None,
        limit: int = 100,
    ) -> list[DocumentView]:
        records = self._repository.list_documents(
            canvas_course_id=canvas_course_id,
            status=status,
            detected_type=detected_type,
            canvas_file_id=canvas_file_id,
            limit=limit,
        )
        return self._repository.document_views(records)

    def units(self, canvas_file_id: str, *, limit: int = 2000) -> list[DocumentUnitView] | None:
        document = self._repository.get(canvas_file_id)
        if document is None:
            return None
        return self._repository.unit_views(
            document, self._repository.units_for(canvas_file_id, limit=limit)
        )

    def course_coverage(self, canvas_course_id: str) -> CourseDocumentCoverage:
        files = FileRepository(self._repository.session).list_all(
            canvas_course_id=canvas_course_id
        )
        eligible = [
            item
            for item in files
            if supported_candidate(item.filename or item.display_name, item.content_type)
        ]
        current = stale = awaiting = needs_ocr = unsupported = failed = 0
        for item in eligible:
            document = self._repository.get(item.canvas_file_id)
            source_current = bool(
                item.download_state == "downloaded"
                and item.sha256
                and item.downloaded_metadata_fingerprint == item.metadata_fingerprint
            )
            if not source_current:
                awaiting += 1
            if document is None:
                continue
            if (
                source_current
                and document.status == "parsed"
                and document.source_sha256 == item.sha256
            ):
                current += 1
            elif document.status == "parsed":
                stale += 1
            if document.status == "needs_ocr":
                needs_ocr += 1
            elif document.status == "unsupported":
                unsupported += 1
            elif document.last_attempt_status in {
                "failed",
                "source_missing",
                "source_corrupt",
            }:
                failed += 1
        return CourseDocumentCoverage(
            canvas_course_id=canvas_course_id,
            known_files=len(files),
            eligible_files=len(eligible),
            indexed_current=current,
            indexed_stale=stale,
            awaiting_download=awaiting,
            needs_ocr=needs_ocr,
            unsupported=unsupported,
            failed=failed,
        )
