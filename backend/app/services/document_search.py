"""Bounded deterministic lexical search over local parsed document units."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.file_repository import FileRepository
from app.database.models import AcademicDocument, CanvasFile, DocumentUnit
from app.documents.models import DocumentSearchHit
from app.services.retrieval_query_focus import GENERIC_RETRIEVAL_TERMS

TOKEN = re.compile(r"[\w'-]+", re.UNICODE)
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "is",
        "are",
        "any",
        "not",
        "no",
        "our",
        "this",
        "that",
        "with",
        "from",
        "how",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "do",
        "does",
        "did",
        "be",
        "by",
        "or",
        "and",
        "as",
        "it",
        "its",
    }
)


class DocumentSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        query: str,
        *,
        canvas_course_id: str | None = None,
        canvas_file_id: str | None = None,
        limit: int = 20,
    ) -> list[DocumentSearchHit]:
        normalized_query = " ".join(TOKEN.findall(query.casefold()))
        terms = tuple(
            dict.fromkeys(
                term
                for term in TOKEN.findall(normalized_query)
                if term not in STOPWORDS and (len(term) > 1 or term.isdigit())
            )
        )
        if not terms:
            return []
        subject_terms = tuple(term for term in terms if term not in GENERIC_RETRIEVAL_TERMS)
        statement = (
            select(DocumentUnit, AcademicDocument, CanvasFile)
            .join(AcademicDocument, DocumentUnit.document_id == AcademicDocument.id)
            .join(CanvasFile, AcademicDocument.canvas_file_id == CanvasFile.canvas_file_id)
            .where(AcademicDocument.status == "parsed")
            .order_by(AcademicDocument.canvas_file_id, DocumentUnit.unit_index)
        )
        if canvas_file_id is not None:
            statement = statement.where(AcademicDocument.canvas_file_id == canvas_file_id)
        allowed_ids: set[str] | None = None
        if canvas_course_id is not None:
            allowed_ids = FileRepository(self._session).owned_file_ids(canvas_course_id)
            if not allowed_ids:
                return []
            statement = statement.where(AcademicDocument.canvas_file_id.in_(allowed_ids))
        rows = list(self._session.execute(statement.limit(5000)))
        references = FileRepository(self._session).references_for(
            document.canvas_file_id for _, document, _ in rows
        )
        ranked: list[DocumentSearchHit] = []
        for unit, document, file_record in rows:
            folded = unit.text.casefold()
            counts = [_occurrences(folded, term) for term in terms]
            if not any(count > 0 for count in counts):
                continue
            # A hit that only matches generic words ("lecture", "slides") says nothing
            # about the subject the student asked about.
            if subject_terms and not any(_occurrences(folded, term) > 0 for term in subject_terms):
                continue
            matched_terms = sum(1 for count in counts if count > 0)
            phrase_count = folded.count(normalized_query)
            score = phrase_count * 10 + sum(counts) + matched_terms
            ranked.append(
                DocumentSearchHit(
                    canvas_file_id=document.canvas_file_id,
                    display_name=file_record.display_name,
                    filename=file_record.filename,
                    unit_type=unit.unit_type,
                    unit_index=unit.unit_index,
                    page_number=unit.page_number,
                    slide_number=unit.slide_number,
                    heading=unit.heading,
                    snippet=make_snippet(unit.text, normalized_query, terms[0]),
                    score=score,
                    source_sha256=document.source_sha256 or "",
                    is_stale=bool(
                        file_record.downloaded_metadata_fingerprint
                        != file_record.metadata_fingerprint
                        or (
                            document.source_sha256
                            and file_record.sha256
                            and document.source_sha256 != file_record.sha256
                        )
                    ),
                    references=references.get(document.canvas_file_id, []),
                )
            )
        ranked.sort(key=lambda item: (-item.score, item.canvas_file_id, item.unit_index))
        return ranked[:limit]


def _occurrences(folded: str, term: str) -> int:
    """Count a term; a lone digit ("lecture 4") must match as a whole number."""
    if len(term) == 1 and term.isdigit():
        return len(re.findall(rf"(?<!\w){term}(?!\w)", folded))
    return folded.count(term)


def make_snippet(text: str, phrase: str, fallback: str, *, radius: int = 180) -> str:
    folded = text.casefold()
    position = folded.find(phrase)
    if position < 0:
        position = folded.find(fallback)
    start = max(0, position - radius)
    end = min(len(text), position + len(phrase) + radius)
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"
