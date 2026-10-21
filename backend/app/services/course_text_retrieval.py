"""Lexical retrieval over synced announcements and syllabus text."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.announcement_repository import AnnouncementRepository
from app.database.models import CanvasAnnouncement
from app.database.syllabus_repository import SyllabusRepository
from app.services.document_search import TOKEN

TOKEN_RE = TOKEN


class CourseTextRetrievalService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        query: str,
        *,
        canvas_course_id: str,
        limit: int = 5,
    ) -> list[tuple[str, str, str, str | None]]:
        """Return (source_kind, source_id, title, excerpt) tuples."""

        terms = tuple(dict.fromkeys(TOKEN_RE.findall(query.casefold())))
        if not terms or limit < 1:
            return []
        hits: list[tuple[int, str, str, str, str | None]] = []
        for row in AnnouncementRepository(self._session).list_for_course(canvas_course_id):
            score = _score_text(row.title, row.body_text, terms)
            if score <= 0:
                continue
            excerpt = _excerpt(row.title, row.body_text, terms)
            hits.append(
                (
                    score,
                    "announcement",
                    row.canvas_topic_id,
                    row.title or "Announcement",
                    excerpt,
                )
            )
        syllabus = SyllabusRepository(self._session).get_for_course(canvas_course_id)
        if syllabus is not None and syllabus.body_text:
            score = _score_text("Syllabus", syllabus.body_text, terms)
            if score > 0:
                hits.append(
                    (
                        score,
                        "syllabus",
                        f"{canvas_course_id}-syllabus",
                        "Course syllabus",
                        _excerpt("Syllabus", syllabus.body_text, terms),
                    )
                )
        hits.sort(key=lambda item: item[0], reverse=True)
        return [
            (kind, source_id, title, excerpt)
            for _, kind, source_id, title, excerpt in hits[:limit]
        ]

    def announcements_matching_assignment(
        self,
        *,
        canvas_course_id: str,
        assignment_name: str | None,
        query: str,
        limit: int = 3,
    ) -> list[CanvasAnnouncement]:
        if not assignment_name:
            return []
        name_terms = [
            term
            for term in TOKEN_RE.findall(assignment_name.casefold())
            if len(term) > 1 and term not in {"quiz", "homework", "exam", "the", "and"}
        ]
        query_terms = TOKEN_RE.findall(query.casefold())
        terms = tuple(dict.fromkeys(name_terms + query_terms))
        rows = AnnouncementRepository(self._session).list_for_course(canvas_course_id)
        scored: list[tuple[int, CanvasAnnouncement]] = []
        for row in rows:
            score = _score_text(row.title, row.body_text, terms)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored[:limit]]


def _score_text(title: str | None, body: str | None, terms: tuple[str, ...]) -> int:
    label = f"{title or ''} {body or ''}".casefold()
    return sum(1 for term in terms if term in label)


def _excerpt(title: str | None, body: str | None, terms: tuple[str, ...]) -> str:
    text = (body or title or "").strip()
    if not text:
        return ""
    lowered = text.casefold()
    anchor = 0
    for term in terms:
        index = lowered.find(term)
        if index >= 0:
            anchor = index
            break
    start = max(0, anchor - 80)
    snippet = text[start : start + 480].strip()
    if start > 0:
        snippet = f"…{snippet}"
    if start + 480 < len(text):
        snippet = f"{snippet}…"
    return snippet
