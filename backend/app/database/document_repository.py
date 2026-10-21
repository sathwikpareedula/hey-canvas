"""Atomic persistence and local queries for parsed academic documents."""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.file_repository import FileRepository
from app.database.models import AcademicDocument, CanvasFile, DocumentUnit
from app.documents.models import DocumentUnitView, DocumentView, ParseResult


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def get(self, canvas_file_id: str) -> AcademicDocument | None:
        return self._session.scalar(
            select(AcademicDocument).where(AcademicDocument.canvas_file_id == canvas_file_id)
        )

    def cache_is_current(
        self, canvas_file_id: str, source_sha256: str, parser_version: str
    ) -> bool:
        record = self.get(canvas_file_id)
        return bool(
            record is not None
            and record.last_attempt_source_sha256 == source_sha256
            and record.last_attempt_parser_version == parser_version
            and record.last_attempt_status in {"parsed", "needs_ocr", "unsupported"}
        )

    def replace_success(
        self,
        *,
        canvas_file_id: str,
        source_sha256: str,
        result: ParseResult,
        attempted_at: datetime,
    ) -> AcademicDocument:
        self._require_aware(attempted_at)
        record = self.get(canvas_file_id)
        if record is None:
            record = AcademicDocument(
                canvas_file_id=canvas_file_id,
                status=result.status,
                last_attempt_status=result.status,
                last_attempted_at=attempted_at,
                last_attempt_parser_version=result.parser_version,
                created_at=attempted_at,
                updated_at=attempted_at,
            )
            self._session.add(record)
            self._session.flush()
        else:
            self._session.execute(
                delete(DocumentUnit).where(DocumentUnit.document_id == record.id)
            )
        record.detected_type = result.detected_type
        record.status = result.status
        record.parser_name = result.parser_name
        record.parser_version = result.parser_version
        record.source_sha256 = source_sha256
        record.parsed_at = attempted_at
        record.unit_count = len(result.units)
        record.character_count = result.character_count
        record.last_attempted_at = attempted_at
        record.last_attempt_source_sha256 = source_sha256
        record.last_attempt_parser_version = result.parser_version
        record.last_attempt_status = result.status
        record.last_error_category = None
        record.updated_at = attempted_at
        for unit in result.units:
            self._session.add(
                DocumentUnit(
                    document_id=record.id,
                    unit_type=unit.unit_type,
                    unit_index=unit.unit_index,
                    page_number=unit.page_number,
                    slide_number=unit.slide_number,
                    heading=unit.heading,
                    text=unit.text,
                    text_fingerprint=unit.text_fingerprint,
                    character_count=unit.character_count,
                )
            )
        return record

    def record_failure(
        self,
        *,
        canvas_file_id: str,
        source_sha256: str | None,
        attempted_at: datetime,
        status: str,
        error_category: str | None = None,
        detected_type: str | None = None,
        parser_name: str | None = None,
        parser_version: str | None = None,
    ) -> AcademicDocument:
        self._require_aware(attempted_at)
        record = self.get(canvas_file_id)
        if record is None:
            record = AcademicDocument(
                canvas_file_id=canvas_file_id,
                detected_type=detected_type,
                status=status,
                parser_name=parser_name,
                parser_version=parser_version,
                source_sha256=None,
                parsed_at=None,
                unit_count=0,
                character_count=0,
                last_attempted_at=attempted_at,
                last_attempt_source_sha256=source_sha256,
                last_attempt_parser_version=parser_version,
                last_attempt_status=status,
                last_error_category=error_category,
                created_at=attempted_at,
                updated_at=attempted_at,
            )
            self._session.add(record)
        else:
            # A failed replacement never demotes or destroys a last known-good parse.
            if record.status not in {"parsed", "needs_ocr"}:
                record.status = status
                if detected_type is not None:
                    record.detected_type = detected_type
            if record.status not in {"parsed", "needs_ocr"}:
                if parser_name is not None:
                    record.parser_name = parser_name
                if parser_version is not None:
                    record.parser_version = parser_version
            record.last_attempted_at = attempted_at
            record.last_attempt_source_sha256 = source_sha256
            record.last_attempt_parser_version = parser_version
            record.last_attempt_status = status
            record.last_error_category = error_category
            record.updated_at = attempted_at
        return record

    def list_documents(
        self,
        *,
        canvas_course_id: str | None = None,
        status: str | None = None,
        detected_type: str | None = None,
        canvas_file_id: str | None = None,
        limit: int = 100,
    ) -> list[AcademicDocument]:
        statement = select(AcademicDocument)
        if canvas_course_id is not None:
            file_ids = FileRepository(self._session).owned_file_ids(canvas_course_id)
            if not file_ids:
                return []
            statement = statement.where(AcademicDocument.canvas_file_id.in_(file_ids))
        if status is not None:
            statement = statement.where(AcademicDocument.status == status)
        if detected_type is not None:
            statement = statement.where(AcademicDocument.detected_type == detected_type)
        if canvas_file_id is not None:
            statement = statement.where(AcademicDocument.canvas_file_id == canvas_file_id)
        statement = statement.order_by(AcademicDocument.canvas_file_id).limit(limit)
        return list(self._session.scalars(statement))

    def units_for(self, canvas_file_id: str, *, limit: int = 2000) -> list[DocumentUnit]:
        statement = (
            select(DocumentUnit)
            .join(AcademicDocument, DocumentUnit.document_id == AcademicDocument.id)
            .where(AcademicDocument.canvas_file_id == canvas_file_id)
            .order_by(DocumentUnit.unit_index)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def document_views(self, records: Iterable[AcademicDocument]) -> list[DocumentView]:
        items = list(records)
        if not items:
            return []
        files = {
            record.canvas_file_id: record
            for record in self._session.scalars(
                select(CanvasFile).where(
                    CanvasFile.canvas_file_id.in_([item.canvas_file_id for item in items])
                )
            )
        }
        references = FileRepository(self._session).references_for(
            item.canvas_file_id for item in items
        )
        return [
            DocumentView(
                canvas_file_id=item.canvas_file_id,
                display_name=files[item.canvas_file_id].display_name,
                filename=files[item.canvas_file_id].filename,
                content_type=files[item.canvas_file_id].content_type,
                detected_type=item.detected_type,
                status=item.status,
                parser_name=item.parser_name,
                parser_version=item.parser_version,
                source_sha256=item.source_sha256,
                parsed_at=item.parsed_at,
                unit_count=item.unit_count,
                character_count=item.character_count,
                last_attempted_at=item.last_attempted_at,
                last_attempt_status=item.last_attempt_status,
                last_error_category=item.last_error_category,
                is_stale=bool(
                    files[item.canvas_file_id].downloaded_metadata_fingerprint
                    != files[item.canvas_file_id].metadata_fingerprint
                    or (
                        item.source_sha256
                        and files[item.canvas_file_id].sha256
                        and item.source_sha256 != files[item.canvas_file_id].sha256
                    )
                ),
                references=references.get(item.canvas_file_id, []),
            )
            for item in items
        ]

    def unit_views(
        self, document: AcademicDocument, units: Iterable[DocumentUnit]
    ) -> list[DocumentUnitView]:
        references = FileRepository(self._session).references_for([document.canvas_file_id]).get(
            document.canvas_file_id, []
        )
        return [
            DocumentUnitView(
                canvas_file_id=document.canvas_file_id,
                source_sha256=document.source_sha256,
                parser_name=document.parser_name,
                parser_version=document.parser_version,
                unit_type=unit.unit_type,
                unit_index=unit.unit_index,
                page_number=unit.page_number,
                slide_number=unit.slide_number,
                heading=unit.heading,
                text=unit.text,
                text_fingerprint=unit.text_fingerprint,
                character_count=unit.character_count,
                references=references,
            )
            for unit in units
        ]

    @staticmethod
    def _require_aware(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("document timestamps must be timezone-aware")
