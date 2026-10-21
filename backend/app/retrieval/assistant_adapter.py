"""Narrow adapter from Phase 9 retrieval hits to assistant evidence contracts."""

from sqlalchemy.orm import Session

from app.assistant_provider.prompt_compact import sanitize_untrusted_text
from app.assistant_tools.models import DocumentEvidence, SourceAuthority
from app.retrieval.models import RetrievalMode
from app.retrieval.providers import SemanticSearchProvider
from app.services.retrieval import RetrievalService


class RetrievalEvidenceAdapter:
    """Expose verified local retrieval through ``RetrievalEvidenceProvider``."""

    def __init__(
        self,
        session: Session,
        *,
        semantic_provider: SemanticSearchProvider | None = None,
        mode: RetrievalMode = "lexical",
        limit: int = 8,
        excerpt_limit: int = 480,
    ) -> None:
        if not 1 <= limit <= 20:
            raise ValueError("assistant evidence limit must be between 1 and 20")
        if not 1 <= excerpt_limit <= 1000:
            raise ValueError("excerpt_limit must be between 1 and 1000")
        self._retrieval = RetrievalService(
            session,
            semantic_provider=semantic_provider,
        )
        self._mode = mode
        self._limit = limit
        self._excerpt_limit = excerpt_limit

    def evidence_for(self, *, course_id: str, query: str) -> tuple[DocumentEvidence, ...]:
        response = self._retrieval.search(
            query,
            canvas_course_id=course_id,
            limit=self._limit,
            mode=self._mode,
        )
        evidence: list[DocumentEvidence] = []
        seen: set[tuple[str, int]] = set()
        for hit in response.results:
            source = hit.evidence
            if (
                source.canvas_course_id != course_id
                or source.canvas_file_id is None
                or source.unit_type is None
                or source.unit_index is None
                or source.is_stale
            ):
                continue
            key = (source.canvas_file_id, source.unit_index)
            if key in seen:
                continue
            seen.add(key)
            references = tuple(
                item
                for item in source.module_references
                if item.canvas_course_id == course_id
            )
            excerpt = sanitize_untrusted_text(hit.snippet, limit=self._excerpt_limit)
            if not excerpt:
                continue
            evidence.append(
                DocumentEvidence(
                    authority=SourceAuthority.PROFESSOR_MATERIAL,
                    canvas_file_id=source.canvas_file_id,
                    canvas_course_id=course_id,
                    display_name=sanitize_untrusted_text(source.display_name, limit=200),
                    filename=source.filename,
                    source_sha256=source.source_sha256,
                    parser_name=source.parser_name,
                    parser_version=source.parser_version,
                    unit_type=source.unit_type,
                    unit_index=source.unit_index,
                    page_number=source.page_number,
                    slide_number=source.slide_number,
                    heading=sanitize_untrusted_text(source.heading, limit=200) or None,
                    excerpt=excerpt,
                    is_stale=source.is_stale,
                    module_references=tuple(
                        item.canvas_module_id for item in references
                    ),
                    module_item_references=tuple(
                        item.canvas_module_item_id for item in references
                    ),
                )
            )
        return tuple(evidence)
