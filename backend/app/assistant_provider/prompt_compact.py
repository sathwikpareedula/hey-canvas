"""Bounded prompt sections for local model providers."""

from __future__ import annotations

import json
import re
from typing import Any

from app.assistant_orchestration.models import AssistantModelInput

_INTERNAL_LABELS = re.compile(
    r"CANVAS_ASSIGNMENT_TRUTH|USER_STUDY_CONTEXT|CANVAS_VERIFIED_DATA|STUDY_EVIDENCE",
    re.IGNORECASE,
)


def sanitize_untrusted_text(value: str | None, *, limit: int) -> str:
    """Bound untrusted text and remove internal prompt markers."""
    return " ".join(_INTERNAL_LABELS.sub("", value or "").split())[:limit]


class StreamLabelSanitizer:
    """Remove internal section labels even when model tokens split a label."""

    _labels = (
        "CANVAS_ASSIGNMENT_TRUTH",
        "USER_STUDY_CONTEXT",
        "CANVAS_VERIFIED_DATA",
        "STUDY_EVIDENCE",
    )

    def __init__(self) -> None:
        self._pending = ""

    def push(self, chunk: str) -> str:
        self._pending += chunk
        self._pending = _INTERNAL_LABELS.sub("", self._pending)
        upper = self._pending.upper()
        keep = 0
        for label in self._labels:
            for size in range(min(len(upper), len(label) - 1), 0, -1):
                if upper.endswith(label[:size]):
                    keep = max(keep, size)
                    break
        if not keep:
            ready, self._pending = self._pending, ""
            return ready
        ready, self._pending = self._pending[:-keep], self._pending[-keep:]
        return ready

    def flush(self) -> str:
        ready = _INTERNAL_LABELS.sub("", self._pending)
        self._pending = ""
        return ready


def _file_evidence(item: Any, course_id: str | None) -> dict[str, Any] | None:
    """Only expose verifiable file-backed evidence from the active course."""
    if not course_id or item.canvas_course_id != course_id:
        return None
    return {
        "canvas_file_id": item.canvas_file_id,
        "unit_type": item.unit_type,
        "unit_index": item.unit_index,
        "page_number": item.page_number,
        "slide_number": item.slide_number,
        "display_name": sanitize_untrusted_text(item.display_name, limit=160),
        "heading": sanitize_untrusted_text(item.heading, limit=160),
        "excerpt": sanitize_untrusted_text(item.excerpt, limit=480),
        "is_stale": item.is_stale,
        "authority": item.authority.value,
    }


def compact_canvas_truth(model_input: AssistantModelInput) -> str:
    if model_input.context is None:
        return "No canvas truth available."
    ctx = model_input.context.context
    payload: dict[str, Any] = {
        "course_id": ctx.course_id,
        "course_code": ctx.course_code,
        "course_name": ctx.course_name,
        "course_instructions": sanitize_untrusted_text(ctx.course_instructions, limit=1200) or None,
        "retrieval_available": ctx.retrieval.available,
    }
    active_course = payload["course_id"]
    if model_input.assignment_context is not None:
        assignment_ctx = model_input.assignment_context
        assignment = assignment_ctx.assignment
        if active_course and assignment.canvas_course_id == active_course:
            payload["assignment"] = {
                "id": assignment.canvas_assignment_id,
                "name": sanitize_untrusted_text(assignment.name, limit=200),
                "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
                "points_possible": assignment.points_possible,
                "submission_types": list(assignment.submission_types)[:6],
                "description": sanitize_untrusted_text(assignment_ctx.description_text, limit=1500),
            }
            payload["related_document_count"] = sum(
                1 for item in assignment_ctx.related_documents
                if getattr(item, "canvas_course_id", None) == active_course
            )
    document_items = list(model_input.evidence)
    text_items = list(model_input.canvas_text_evidence)
    if (
        model_input.assignment_context is not None
        and model_input.assignment_context.assignment.canvas_course_id == active_course
    ):
        document_items.extend(model_input.assignment_context.retrieval_evidence)
        text_items.extend(model_input.assignment_context.canvas_text_evidence)
    docs: list[dict[str, Any]] = []
    seen_docs: set[tuple[str, int]] = set()
    for item in document_items:
        key = (item.canvas_file_id, item.unit_index)
        entry = _file_evidence(item, active_course)
        if entry is not None and key not in seen_docs:
            seen_docs.add(key)
            docs.append(entry)
        if len(docs) >= 8:
            break
    if docs:
        payload["related_document_evidence"] = docs
    texts: list[dict[str, Any]] = []
    seen_texts: set[tuple[str, str]] = set()
    for text_item in text_items:
        text_key = (text_item.authority.value, text_item.source_id)
        if text_item.canvas_course_id != active_course or text_key in seen_texts:
            continue
        seen_texts.add(text_key)
        texts.append({
            "source_id": text_item.source_id,
            "source_kind": text_item.source_kind,
            "authority": text_item.authority.value,
            "posted_at": text_item.posted_at.isoformat() if text_item.posted_at else None,
            "title": sanitize_untrusted_text(text_item.title, limit=160),
            "excerpt": sanitize_untrusted_text(text_item.excerpt, limit=600),
        })
        if len(texts) >= 8:
            break
    if texts:
        payload["canvas_text_evidence"] = texts
    return json.dumps(payload, sort_keys=True)


def compact_study_context(model_input: AssistantModelInput) -> str:
    if model_input.context is None:
        return "No study context."
    view = model_input.context.context.study_context
    study_mode = (
        view.study_mode.value if hasattr(view.study_mode, "value") else view.study_mode
    )
    payload: dict[str, Any] = {
        "current_topic": sanitize_untrusted_text(view.current_topic, limit=160),
        "assignment_id": view.assignment_id,
        "study_mode": study_mode,
        "concepts_covered": [
            sanitize_untrusted_text(v, limit=100) for v in view.concepts_covered[:8]
        ],
        "topics_to_revisit": [
            sanitize_untrusted_text(v, limit=100) for v in view.topics_to_revisit[:8]
        ],
    }
    return json.dumps(payload, sort_keys=True)
