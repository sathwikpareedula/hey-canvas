"""Deterministic provenance-first lexical and optional local semantic retrieval."""

import hashlib
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.canvas.courses import _normalize_canvas_id
from app.database.file_repository import FileRepository
from app.database.models import AcademicDocument, CanvasFile, DocumentUnit
from app.documents.models import DocumentSearchHit
from app.files.models import FileReference
from app.retrieval.models import (
    EvidenceReference,
    ModuleSourceReference,
    RetrievalHit,
    RetrievalMode,
    RetrievalResponse,
    RetrievalSignal,
)
from app.retrieval.providers import (
    SemanticMatch,
    SemanticProviderUnavailable,
    SemanticSearchProvider,
)
from app.services.document_search import TOKEN, DocumentSearchService, make_snippet

RRF_CONSTANT = 60
MAX_CANDIDATES = 500


@dataclass
class _Candidate:
    evidence: EvidenceReference
    snippet: str
    signals: list[RetrievalSignal] = field(default_factory=list)
    fusion_score: float = 0.0


class RetrievalService:
    """Fuse inspectable lexical rank with an explicitly injected local semantic provider."""

    def __init__(
        self,
        session: Session,
        *,
        semantic_provider: SemanticSearchProvider | None = None,
    ) -> None:
        self._session = session
        self._semantic_provider = semantic_provider

    def search(
        self,
        query: str,
        *,
        canvas_course_id: str | None = None,
        canvas_file_id: str | None = None,
        limit: int = 20,
        mode: RetrievalMode = "lexical",
    ) -> RetrievalResponse:
        normalized = self._validate_query(query)
        course_id = self._normalize_optional_id(canvas_course_id, "course_id")
        file_id = self._normalize_optional_id(canvas_file_id, "file_id")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if mode not in {"lexical", "semantic", "hybrid"}:
            raise ValueError("mode must be lexical, semantic, or hybrid")
        terms = tuple(dict.fromkeys(TOKEN.findall(normalized.casefold())))
        semantic_status = "disabled" if mode == "lexical" else "unavailable"
        if not terms:
            return RetrievalResponse(
                query=normalized,
                mode=mode,
                semantic_status=semantic_status,
                results=(),
                index_limitation=None,
            )

        candidate_limit = min(MAX_CANDIDATES, max(50, limit * 10))
        candidates: dict[tuple[str, int, str], _Candidate] = {}
        if mode in {"lexical", "hybrid"}:
            lexical = DocumentSearchService(self._session).search(
                normalized,
                canvas_course_id=course_id,
                canvas_file_id=file_id,
                limit=candidate_limit,
            )
            self._add_lexical(candidates, lexical, course_id=course_id)

        if mode in {"semantic", "hybrid"} and self._semantic_provider is not None:
            try:
                matches = self._semantic_provider.search(
                    normalized,
                    canvas_course_id=course_id,
                    canvas_file_id=file_id,
                    limit=candidate_limit,
                )
            except SemanticProviderUnavailable:
                semantic_status = "unavailable"
            else:
                semantic_status = "available"
                self._add_semantic(
                    candidates,
                    matches,
                    normalized,
                    course_id=course_id,
                    file_id=file_id,
                )

        ranked = sorted(
            candidates.values(),
            key=lambda item: (
                -item.fusion_score,
                item.evidence.canvas_file_id or "",
                item.evidence.unit_index if item.evidence.unit_index is not None else -1,
            ),
        )
        results = tuple(
            RetrievalHit(
                evidence=item.evidence,
                snippet=item.snippet,
                fusion_score=round(item.fusion_score, 12),
                signals=tuple(item.signals),
            )
            for item in ranked[:limit]
        )
        limitation = None
        if not results:
            limitation = self._needs_ocr_index_limitation(
                terms, course_id=course_id, file_id=file_id
            )
        return RetrievalResponse(
            query=normalized,
            mode=mode,
            semantic_status=semantic_status,
            results=results,
            index_limitation=limitation,
        )

    def _needs_ocr_index_limitation(
        self,
        terms: tuple[str, ...],
        *,
        course_id: str | None,
        file_id: str | None,
    ) -> str | None:
        if not terms:
            return None
        statement = (
            select(CanvasFile, AcademicDocument)
            .join(
                AcademicDocument,
                AcademicDocument.canvas_file_id == CanvasFile.canvas_file_id,
            )
            .where(AcademicDocument.status == "needs_ocr")
        )
        if file_id is not None:
            statement = statement.where(CanvasFile.canvas_file_id == file_id)
        elif course_id is not None:
            allowed = FileRepository(self._session).owned_file_ids(course_id)
            if not allowed:
                return None
            statement = statement.where(CanvasFile.canvas_file_id.in_(allowed))
        else:
            return None
        matches: list[str] = []
        for file_record, _document in self._session.execute(statement.limit(200)):
            label = (file_record.display_name or file_record.filename or "").casefold()
            if any(term in label for term in terms):
                name = (
                    file_record.display_name
                    or file_record.filename
                    or file_record.canvas_file_id
                )
                matches.append(name)
        if not matches:
            return None
        preview = ", ".join(matches[:3])
        suffix = f" (+{len(matches) - 3} more)" if len(matches) > 3 else ""
        return (
            "Indexed file names match this query, but extracted text is unavailable "
            f"(OCR required): {preview}{suffix}"
        )

    def _add_lexical(
        self,
        candidates: dict[tuple[str, int, str], _Candidate],
        hits: list[DocumentSearchHit],
        *,
        course_id: str | None,
    ) -> None:
        document_ids = {hit.canvas_file_id for hit in hits}
        documents = {
            item.canvas_file_id: item
            for item in self._session.scalars(
                select(AcademicDocument).where(
                    AcademicDocument.canvas_file_id.in_(document_ids)
                )
            )
        }
        for rank, hit in enumerate(hits, start=1):
            document = documents.get(hit.canvas_file_id)
            if document is None or document.source_sha256 is None:
                continue
            evidence = document_evidence(
                canvas_file_id=hit.canvas_file_id,
                display_name=hit.display_name,
                filename=hit.filename,
                unit_type=hit.unit_type,
                unit_index=hit.unit_index,
                page_number=hit.page_number,
                slide_number=hit.slide_number,
                heading=hit.heading,
                source_sha256=document.source_sha256,
                parser_name=document.parser_name,
                parser_version=document.parser_version,
                is_stale=hit.is_stale,
                references=hit.references,
                preferred_course_id=course_id,
            )
            key = _evidence_key(evidence)
            candidate = candidates.setdefault(
                key, _Candidate(evidence=evidence, snippet=hit.snippet)
            )
            candidate.signals.append(
                RetrievalSignal(kind="lexical", rank=rank, raw_score=float(hit.score))
            )
            candidate.fusion_score += 1 / (RRF_CONSTANT + rank)

    def _add_semantic(
        self,
        candidates: dict[tuple[str, int, str], _Candidate],
        matches: list[SemanticMatch],
        query: str,
        *,
        course_id: str | None,
        file_id: str | None,
    ) -> None:
        if not matches or self._semantic_provider is None:
            return
        deduplicated: dict[tuple[str, int, str, str], SemanticMatch] = {}
        for match in matches:
            semantic_identity = (
                match.canvas_file_id,
                match.unit_index,
                match.source_sha256,
                match.text_fingerprint,
            )
            previous = deduplicated.get(semantic_identity)
            if previous is None or match.score > previous.score:
                deduplicated[semantic_identity] = match
        matches = sorted(
            deduplicated.values(),
            key=lambda item: (-item.score, item.canvas_file_id, item.unit_index),
        )[:MAX_CANDIDATES]
        file_ids = {item.canvas_file_id for item in matches}
        rows = list(
            self._session.execute(
                select(DocumentUnit, AcademicDocument, CanvasFile)
                .join(AcademicDocument, DocumentUnit.document_id == AcademicDocument.id)
                .join(CanvasFile, AcademicDocument.canvas_file_id == CanvasFile.canvas_file_id)
                .where(
                    AcademicDocument.status == "parsed",
                    AcademicDocument.canvas_file_id.in_(file_ids),
                )
            )
        )
        rows_by_key = {
            (document.canvas_file_id, unit.unit_index): (unit, document, file_record)
            for unit, document, file_record in rows
        }
        references = FileRepository(self._session).references_for(file_ids)
        first_term = TOKEN.findall(query.casefold())[0]
        semantic_rank = 0
        for match in matches:
            if file_id is not None and match.canvas_file_id != file_id:
                continue
            row = rows_by_key.get((match.canvas_file_id, match.unit_index))
            if row is None:
                continue
            unit, document, file_record = row
            if (
                document.source_sha256 != match.source_sha256
                or unit.text_fingerprint != match.text_fingerprint
            ):
                continue
            source_sha256 = document.source_sha256
            if source_sha256 is None:
                continue
            unit_references = references.get(document.canvas_file_id, [])
            if course_id is not None and not any(
                item.canvas_course_id == course_id for item in unit_references
            ):
                continue
            semantic_rank += 1
            evidence = document_evidence(
                canvas_file_id=document.canvas_file_id,
                display_name=file_record.display_name,
                filename=file_record.filename,
                unit_type=unit.unit_type,
                unit_index=unit.unit_index,
                page_number=unit.page_number,
                slide_number=unit.slide_number,
                heading=unit.heading,
                source_sha256=source_sha256,
                parser_name=document.parser_name,
                parser_version=document.parser_version,
                is_stale=bool(
                    document.source_sha256
                    and file_record.sha256
                    and document.source_sha256 != file_record.sha256
                ),
                references=unit_references,
                preferred_course_id=course_id,
            )
            evidence_key = _evidence_key(evidence)
            candidate = candidates.setdefault(
                evidence_key,
                _Candidate(
                    evidence=evidence,
                    snippet=make_snippet(unit.text, query.casefold(), first_term),
                ),
            )
            candidate.signals.append(
                RetrievalSignal(
                    kind="semantic",
                    rank=semantic_rank,
                    raw_score=match.score,
                    provider_id=self._semantic_provider.provider_id,
                    model_version=self._semantic_provider.model_version,
                )
            )
            candidate.fusion_score += 1 / (RRF_CONSTANT + semantic_rank)

    @staticmethod
    def _validate_query(query: str) -> str:
        normalized = " ".join(query.split())
        if len(normalized) > 500:
            raise ValueError("query must be at most 500 characters")
        return normalized

    @staticmethod
    def _normalize_optional_id(value: str | None, name: str) -> str | None:
        if value is None:
            return None
        return _normalize_canvas_id(value, field_name=name)


def document_evidence(
    *,
    canvas_file_id: str,
    display_name: str | None,
    filename: str | None,
    unit_type: str,
    unit_index: int,
    page_number: int | None,
    slide_number: int | None,
    heading: str | None,
    source_sha256: str,
    parser_name: str | None,
    parser_version: str | None,
    is_stale: bool,
    references: list[FileReference],
    preferred_course_id: str | None,
) -> EvidenceReference:
    course_ids = sorted({item.canvas_course_id for item in references})
    course_id = preferred_course_id or (course_ids[0] if len(course_ids) == 1 else None)
    citation_material = f"{canvas_file_id}:{source_sha256}:{unit_index}"
    citation_suffix = hashlib.sha256(citation_material.encode()).hexdigest()[:20]
    return EvidenceReference(
        citation_id=f"document:{citation_suffix}",
        source_type="professor_document",
        canvas_course_id=course_id,
        canvas_file_id=canvas_file_id,
        display_name=display_name,
        filename=filename,
        unit_type=unit_type,
        unit_index=unit_index,
        page_number=page_number,
        slide_number=slide_number,
        heading=heading,
        source_sha256=source_sha256,
        parser_name=parser_name,
        parser_version=parser_version,
        is_stale=is_stale,
        module_references=tuple(
            ModuleSourceReference(**item.model_dump())
            for item in sorted(
                references,
                key=lambda value: (
                    value.canvas_course_id,
                    value.canvas_module_id,
                    value.canvas_module_item_id,
                ),
            )
        ),
    )


def _evidence_key(evidence: EvidenceReference) -> tuple[str, int, str]:
    if (
        evidence.canvas_file_id is None
        or evidence.unit_index is None
        or evidence.source_sha256 is None
    ):
        raise ValueError("evidence identity is incomplete")
    return evidence.canvas_file_id, evidence.unit_index, evidence.source_sha256
