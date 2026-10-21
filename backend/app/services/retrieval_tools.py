"""Bounded local retrieval operations for later academic-assistant integration."""

from sqlalchemy.orm import Session

from app.canvas.courses import _normalize_canvas_id
from app.database.document_repository import DocumentRepository
from app.retrieval.models import (
    RetrievalMode,
    RetrievalResponse,
    SourceDetail,
    UnitContext,
    UnitNeighborhood,
)
from app.retrieval.providers import SemanticSearchProvider
from app.services.document_query import DocumentQueryService
from app.services.retrieval import RetrievalService, document_evidence


class AcademicRetrievalTools:
    """Network-free retrieval facade over authoritative Phase 8 units."""

    def __init__(
        self,
        session: Session,
        *,
        semantic_provider: SemanticSearchProvider | None = None,
    ) -> None:
        self._session = session
        self._retrieval = RetrievalService(session, semantic_provider=semantic_provider)

    def search_course_materials(
        self,
        query: str,
        *,
        canvas_course_id: str | None = None,
        limit: int = 20,
        mode: RetrievalMode = "lexical",
    ) -> RetrievalResponse:
        return self._retrieval.search(
            query,
            canvas_course_id=canvas_course_id,
            limit=limit,
            mode=mode,
        )

    def search_document(
        self,
        query: str,
        *,
        canvas_file_id: str,
        limit: int = 20,
        mode: RetrievalMode = "lexical",
    ) -> RetrievalResponse:
        return self._retrieval.search(
            query,
            canvas_file_id=canvas_file_id,
            limit=limit,
            mode=mode,
        )

    def retrieve_unit_context(
        self,
        canvas_file_id: str,
        unit_index: int,
        *,
        before: int = 1,
        after: int = 1,
        max_characters: int = 12_000,
    ) -> UnitNeighborhood | None:
        file_id = _normalize_canvas_id(canvas_file_id, field_name="file_id")
        if unit_index < 0:
            raise ValueError("unit_index must be non-negative")
        if not 0 <= before <= 10 or not 0 <= after <= 10:
            raise ValueError("before and after must be between 0 and 10")
        if not 1 <= max_characters <= 50_000:
            raise ValueError("max_characters must be between 1 and 50000")
        query = DocumentQueryService(self._session)
        documents = query.list_documents(canvas_file_id=file_id, limit=1)
        if (
            not documents
            or documents[0].status != "parsed"
            or documents[0].source_sha256 is None
        ):
            return None
        document = documents[0]
        units = query.units(file_id, limit=2000)
        if units is None or not any(item.unit_index == unit_index for item in units):
            return None
        lower = max(0, unit_index - before)
        upper = unit_index + after
        selected = [item for item in units if lower <= item.unit_index <= upper]
        remaining = max_characters
        contexts: list[UnitContext] = []
        truncated = False
        for unit in selected:
            if remaining <= 0:
                truncated = True
                break
            text = unit.text[:4000]
            if len(text) > remaining:
                text = text[:remaining]
                truncated = True
            if len(unit.text) > len(text):
                truncated = True
            contexts.append(
                UnitContext(
                    evidence=document_evidence(
                        canvas_file_id=unit.canvas_file_id,
                        display_name=document.display_name,
                        filename=document.filename,
                        unit_type=unit.unit_type,
                        unit_index=unit.unit_index,
                        page_number=unit.page_number,
                        slide_number=unit.slide_number,
                        heading=unit.heading,
                        source_sha256=unit.source_sha256 or "",
                        parser_name=document.parser_name,
                        parser_version=unit.parser_version,
                        is_stale=document.is_stale,
                        references=unit.references,
                        preferred_course_id=None,
                    ),
                    text=text,
                    text_fingerprint=unit.text_fingerprint,
                )
            )
            remaining -= len(text)
        return UnitNeighborhood(
            canvas_file_id=file_id,
            center_unit_index=unit_index,
            units=tuple(contexts),
            truncated=truncated,
        )

    def retrieve_source_detail(
        self, canvas_file_id: str, *, citation_limit: int = 100
    ) -> SourceDetail | None:
        file_id = _normalize_canvas_id(canvas_file_id, field_name="file_id")
        if not 1 <= citation_limit <= 500:
            raise ValueError("citation_limit must be between 1 and 500")
        query = DocumentQueryService(self._session)
        documents = query.list_documents(canvas_file_id=file_id, limit=1)
        if not documents or documents[0].source_sha256 is None:
            return None
        document = documents[0]
        units = query.units(file_id, limit=citation_limit) or []
        citations = tuple(
            document_evidence(
                canvas_file_id=unit.canvas_file_id,
                display_name=document.display_name,
                filename=document.filename,
                unit_type=unit.unit_type,
                unit_index=unit.unit_index,
                page_number=unit.page_number,
                slide_number=unit.slide_number,
                heading=unit.heading,
                source_sha256=unit.source_sha256 or "",
                parser_name=document.parser_name,
                parser_version=unit.parser_version,
                is_stale=document.is_stale,
                references=unit.references,
                preferred_course_id=None,
            )
            for unit in units
        )
        return SourceDetail(document=document, citations=citations)

    def authoritative_unit_count(self, canvas_file_id: str) -> int:
        file_id = _normalize_canvas_id(canvas_file_id, field_name="file_id")
        document = DocumentRepository(self._session).get(file_id)
        return document.unit_count if document is not None and document.status == "parsed" else 0
