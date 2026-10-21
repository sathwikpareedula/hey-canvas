"""Connect assignments, announcements, syllabus, and module materials."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.assistant_tools.models import CanvasTextEvidence, TopicModuleLink
from app.database.models import CourseModule, ModuleItem
from app.services.course_text_retrieval import CourseTextRetrievalService, _excerpt
from app.services.document_search import TOKEN

_TOPIC_LINE_RE = re.compile(
    r"(?:topics?|coverage|will cover|including)\s*[:\-]?\s*(.+)$",
    re.IGNORECASE,
)
_BULLET_RE = re.compile(r"^[\s]*(?:[-*•]|\d+[.)])\s+(.+)$")


def build_canvas_text_evidence(
    session: Session,
    *,
    canvas_course_id: str,
    query: str,
    assignment_name: str | None,
    limit: int = 5,
) -> tuple[CanvasTextEvidence, ...]:
    retrieval = CourseTextRetrievalService(session)
    announcements = retrieval.announcements_matching_assignment(
        canvas_course_id=canvas_course_id,
        assignment_name=assignment_name,
        query=query,
        limit=3,
    )
    evidence: list[CanvasTextEvidence] = []
    seen: set[str] = set()
    for row in announcements:
        if row.canvas_topic_id in seen:
            continue
        seen.add(row.canvas_topic_id)
        terms = tuple(TOKEN.findall((row.title or assignment_name or query).casefold()))
        excerpt = _excerpt(row.title, row.body_text, terms)
        evidence.append(
            CanvasTextEvidence(
                source_kind="announcement",
                canvas_course_id=canvas_course_id,
                source_id=row.canvas_topic_id,
                title=row.title,
                excerpt=excerpt or (row.body_text or "")[:480],
                html_url=row.html_url,
                posted_at=row.posted_at,
            )
        )
    for hit in retrieval.search(query, canvas_course_id=canvas_course_id, limit=limit):
        kind, source_id, title, raw_excerpt = hit
        excerpt = raw_excerpt or ""
        if not source_id:
            continue
        if kind == "announcement":
            if source_id in seen:
                continue
            seen.add(source_id)
            evidence.append(
                CanvasTextEvidence(
                    source_kind="announcement",
                    canvas_course_id=canvas_course_id,
                    source_id=source_id,
                    title=title,
                    excerpt=excerpt,
                    html_url=None,
                    posted_at=None,
                )
            )
        elif kind == "syllabus":
            evidence.append(
                CanvasTextEvidence(
                    source_kind="syllabus",
                    canvas_course_id=canvas_course_id,
                    source_id=source_id,
                    title=title,
                    excerpt=excerpt,
                    html_url=None,
                    posted_at=None,
                )
            )
    return tuple(evidence[:limit])


def extract_topics_from_text(*texts: str | None) -> tuple[str, ...]:
    topics: list[str] = []
    for text in texts:
        if not text:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = _TOPIC_LINE_RE.search(stripped)
            if match:
                chunk = match.group(1)
                topics.extend(_split_topic_chunk(chunk))
                continue
            bullet = _BULLET_RE.match(stripped)
            if bullet:
                topics.append(bullet.group(1).strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        key = topic.casefold()
        if not topic or key in seen or len(topic) < 3:
            continue
        seen.add(key)
        deduped.append(topic[:200])
    return tuple(deduped[:12])


def link_topics_to_module_items(
    session: Session,
    *,
    canvas_course_id: str,
    topics: tuple[str, ...],
    allowed_module_ids: tuple[str, ...] = (),
) -> tuple[TopicModuleLink, ...]:
    if not topics:
        return ()
    from app.database.models import Course

    modules = session.scalars(
        select(CourseModule)
        .options(selectinload(CourseModule.items))
        .join(Course)
        .where(Course.canvas_course_id == canvas_course_id)
    )
    links: list[TopicModuleLink] = []
    for topic in topics:
        topic_terms = [
            t for t in TOKEN.findall(topic.casefold()) if len(t) > 2
        ]
        if not topic_terms:
            continue
        best: tuple[int, ModuleItem, CourseModule] | None = None
        for module in modules:
            if allowed_module_ids and module.canvas_module_id not in allowed_module_ids:
                continue
            for item in module.items:
                if item.item_type not in {"File", "Page", "ExternalUrl", "Assignment"}:
                    continue
                label = (item.title or "").casefold()
                score = sum(1 for term in topic_terms if term in label)
                if score <= 0:
                    continue
                if best is None or score > best[0]:
                    best = (score, item, module)
        if best is None:
            continue
        _, item, module = best
        links.append(
            TopicModuleLink(
                topic=topic,
                canvas_module_id=module.canvas_module_id,
                canvas_module_item_id=item.canvas_module_item_id,
                item_title=item.title,
                item_type=item.item_type,
                content_id=item.content_id,
            )
        )
    return tuple(links)


def _split_topic_chunk(chunk: str) -> list[str]:
    parts = re.split(r"[;,]", chunk)
    return [part.strip() for part in parts if part.strip()]
