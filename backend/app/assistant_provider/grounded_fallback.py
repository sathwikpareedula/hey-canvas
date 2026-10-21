"""Deterministic assistant text when the local model fails but verified facts exist."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from app.assistant_orchestration.models import AssistantModelInput
from app.assistant_tools.deterministic_answers import format_due, try_deterministic_answer
from app.assistant_tools.models import (
    AssistantResponse,
    AssistantResponseBlock,
    DocumentEvidence,
    ResponseBlockType,
)
from app.assistant_tools.question_intent import classify_academic_question
from app.services.retrieval_query_focus import focused_retrieval_query

_EVIDENCE_OPERATIONS = frozenset(
    {
        "material_search",
        "study_help",
        "assignment_context",
        "study_guide",
        "study_plan",
    }
)

_MAX_EVIDENCE_ITEMS = 2
_MAX_EXCERPT_CHARS = 420
_MAX_RESPONSE_CHARS = 4000


def _focus_terms(query: str) -> tuple[str, ...]:
    return tuple(focused_retrieval_query(query).casefold().split())


def _evidence_relevance_score(query: str, item: DocumentEvidence) -> int:
    terms = _focus_terms(query)
    if not terms:
        return 0
    hay = " ".join(
        part
        for part in (
            item.display_name,
            item.filename,
            item.heading,
            item.excerpt,
        )
        if part
    ).casefold()
    return sum(2 for term in terms if term in hay)


def _select_relevant_evidence(
    query: str,
    evidence: tuple[DocumentEvidence, ...],
    *,
    max_items: int = _MAX_EVIDENCE_ITEMS,
) -> tuple[DocumentEvidence, ...]:
    if not evidence:
        return ()
    ranked = sorted(
        evidence,
        key=lambda item: _evidence_relevance_score(query, item),
        reverse=True,
    )
    top_score = _evidence_relevance_score(query, ranked[0])
    if top_score <= 0:
        return ()
    selected: list[DocumentEvidence] = []
    for item in ranked:
        score = _evidence_relevance_score(query, item)
        if score <= 0:
            break
        selected.append(item)
        if len(selected) >= max_items:
            break
    return tuple(selected)


def _trim_excerpt(text: str, limit: int = _MAX_EXCERPT_CHARS) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit]}…"


def _evidence_fallback_response(model_input: AssistantModelInput) -> AssistantResponse | None:
    operation = model_input.plan.operation.value
    if operation not in _EVIDENCE_OPERATIONS:
        return None
    evidence = _select_relevant_evidence(model_input.request.query, model_input.evidence)
    canvas_items = model_input.canvas_text_evidence[:2]
    if not evidence and not canvas_items:
        return None

    lines = [
        "Local AI did not finish in time, so this answer is grounded directly in your "
        "indexed course materials (not a generated paraphrase).",
        "",
    ]
    if model_input.assignment_context is not None:
        assignment = model_input.assignment_context.assignment
        due = (
            f" (due {format_due(assignment.due_at, timezone=_fallback_timezone())})"
            if assignment.due_at is not None
            else ""
        )
        lines.append(
            f"Assignment: {assignment.name or assignment.canvas_assignment_id}{due}"
        )
        lines.append("")

    for item in canvas_items:
        label = item.title or item.source_id
        excerpt = _trim_excerpt(item.excerpt or "")
        if not excerpt:
            continue
        lines.append(f"Canvas {item.source_kind}: {label}")
        lines.append(f"   {excerpt}")
        lines.append("")

    for index, document in enumerate(evidence, start=1):
        label = document.display_name or document.filename or document.canvas_file_id
        excerpt = _trim_excerpt(document.excerpt or "")
        if not excerpt:
            continue
        lines.append(f"{index}. {label}")
        if document.page_number is not None:
            lines.append(f"   (page {document.page_number})")
        lines.append(f"   {excerpt}")
        lines.append("")

    if len(lines) <= 3:
        return None

    lines.append(
        "Open the cited document in Materials to verify wording. "
        "If a PDF needs OCR, Hey Canvas cannot search its text yet."
    )
    text = "\n".join(lines).strip()[:_MAX_RESPONSE_CHARS]
    return AssistantResponse(
        status="ok",
        blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),),
        course_id=model_input.plan.course_id,
    )


def _fallback_timezone() -> ZoneInfo:
    from app.config import get_settings

    return ZoneInfo(get_settings().academic_timezone)


def grounded_assistant_response(
    model_input: AssistantModelInput,
) -> AssistantResponse | None:
    intent = classify_academic_question(
        model_input.request.query,
        assignment_id=model_input.request.assignment_id,
    )
    timezone = _fallback_timezone()
    window_label = "for this question"
    deterministic = try_deterministic_answer(
        intent=intent,
        assignment_context=model_input.assignment_context,
        deadlines=model_input.deadlines,
        timezone=timezone,
        deadline_window_label=window_label,
    )
    if deterministic is not None:
        prefix = (
            "Local AI did not finish in time. "
            "This answer uses verified Canvas data on your computer "
            "(not a generated paraphrase).\n\n"
        )
        first = deterministic.blocks[0]
        if first.text:
            merged = AssistantResponse(
                status=deterministic.status,
                blocks=(
                    AssistantResponseBlock(
                        type=ResponseBlockType.TEXT,
                        text=prefix + first.text,
                    ),
                    *deterministic.blocks[1:],
                ),
                course_id=deterministic.course_id,
            )
            return merged
        return deterministic

    evidence_response = _evidence_fallback_response(model_input)
    if evidence_response is not None:
        return evidence_response

    if not model_input.assignment_context and not model_input.deadlines:
        return None
    assignment = (
        model_input.assignment_context.assignment
        if model_input.assignment_context is not None
        else None
    )
    if assignment is not None:
        title = assignment.name or "This assignment"
        text = (
            "Local AI did not finish in time. "
            f"{title} is still listed in your synced Canvas data, but I could not "
            "generate an explanation. Open the assignment in Canvas or Materials to review details."
        )
        return AssistantResponse(
            status="ok",
            blocks=(AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),),
            course_id=assignment.canvas_course_id,
        )
    return None
