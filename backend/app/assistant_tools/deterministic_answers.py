"""Fast, verified answers from Canvas structured data (no local model)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo

from app.assistant_tools.models import (
    AssignmentContext,
    AssignmentToolRecord,
    AssistantEvidenceReference,
    AssistantResponse,
    AssistantResponseBlock,
    DeadlineToolResult,
    DocumentEvidence,
    ResponseBlockType,
    SourceAuthority,
)
from app.assistant_tools.question_intent import AcademicQuestionIntent


def format_due(
    due_at: datetime | None,
    *,
    timezone: ZoneInfo,
) -> str:
    if due_at is None:
        return "No due date is listed in Canvas."
    local = due_at.astimezone(timezone)
    time_part = local.strftime("%I:%M %p").lstrip("0")
    zone_label = local.tzname() or timezone.key
    return f"{local.strftime('%B')} {local.day}, {local.year} at {time_part} {zone_label}"


def due_clause(due_at: datetime | None, *, timezone: ZoneInfo) -> str:
    """Sentence predicate: never glues the missing-date notice onto "is due"."""
    if due_at is None:
        return "has no due date listed in Canvas"
    return f"is due {format_due(due_at, timezone=timezone)}"


def _course_label(assignment: AssignmentToolRecord, course_name: str | None) -> str:
    if course_name:
        return course_name
    return assignment.canvas_course_id


def _assignment_title(assignment: AssignmentToolRecord) -> str:
    return assignment.name or f"Assignment {assignment.canvas_assignment_id}"


def _citation_block(
    assignment: AssignmentToolRecord,
    *,
    course_name: str | None,
) -> AssistantResponseBlock:
    return AssistantResponseBlock(
        type=ResponseBlockType.ASSIGNMENT_CONTEXT,
        payload={
            "assignment": assignment.model_dump(mode="json"),
            "course": {
                "canvas_course_id": assignment.canvas_course_id,
                "course_name": course_name or assignment.canvas_course_id,
            },
        },
    )


def build_assignment_due_answer(
    ctx: AssignmentContext,
    *,
    timezone: ZoneInfo,
) -> AssistantResponse:
    assignment = ctx.assignment
    title = _assignment_title(assignment)
    course = _course_label(assignment, ctx.course.course_name)
    text = f"{title} in {course} {due_clause(assignment.due_at, timezone=timezone)}."
    if assignment.points_possible is not None:
        pts = assignment.points_possible
        label = int(pts) if pts == int(pts) else pts
        text += f" It is worth {label} point{'s' if label != 1 else ''}."
    return AssistantResponse(
        status="ok",
        blocks=(
            AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),
            _citation_block(assignment, course_name=ctx.course.course_name),
        ),
        course_id=assignment.canvas_course_id,
    )


def build_assignment_points_answer(
    ctx: AssignmentContext,
    *,
    timezone: ZoneInfo,
) -> AssistantResponse:
    assignment = ctx.assignment
    title = _assignment_title(assignment)
    if assignment.points_possible is None:
        text = f"{title} does not list a point value in Canvas."
    else:
        pts = assignment.points_possible
        label = int(pts) if pts == int(pts) else pts
        text = f"{title} is worth {label} points in Canvas."
    return AssistantResponse(
        status="ok",
        blocks=(
            AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),
            _citation_block(assignment, course_name=ctx.course.course_name),
        ),
        course_id=assignment.canvas_course_id,
    )


_BOILERPLATE_PHRASES = (
    "this is a quiz",
    "complete the quiz",
    "submit your answers",
    "no description",
)
_MIN_INFORMATIVE_CHARS = 40


def _description_is_informative(description: str | None) -> bool:
    """Treat a description as informative unless it is only generic quiz boilerplate."""
    if not description:
        return False
    remainder = " ".join(description.split()).casefold()
    for phrase in _BOILERPLATE_PHRASES:
        remainder = remainder.replace(phrase, " ")
    remainder = "".join(char for char in remainder if char.isalnum() or char.isspace())
    return len(" ".join(remainder.split())) >= _MIN_INFORMATIVE_CHARS


def build_assignment_explain_answer(
    ctx: AssignmentContext,
    *,
    timezone: ZoneInfo,
) -> AssistantResponse | None:
    """Deterministic explain answer from Canvas listing when possible."""
    assignment = ctx.assignment
    title = _assignment_title(assignment)
    course = _course_label(assignment, ctx.course.course_name)
    description = ctx.description_text or ""

    if _description_is_informative(description):
        summary = description.strip()
        if len(summary) > 900:
            summary = f"{summary[:900].rstrip()}…"
        text = (
            f"Here is what Canvas lists for {title} in {course} "
            f"({due_clause(assignment.due_at, timezone=timezone).removeprefix('is ')}):\n\n"
            f"{summary}"
        )
    else:
        text = (
            f"{title} is listed in {course} and "
            f"{due_clause(assignment.due_at, timezone=timezone)}. "
            "The available assignment details do not explain its questions or covered topics, "
            "so I can't verify what you need to study from this listing alone."
        )
    prepared_names = [
        document.display_name or document.filename or "Untitled file"
        for document in ctx.related_documents
        if document.status == "parsed"
    ]
    unprepared_names = [
        document.display_name or document.filename or "Untitled file"
        for document in ctx.related_documents
        if document.status != "parsed"
    ]
    if prepared_names:
        text += (
            "\n\nRelated module material indexed locally: "
            + ", ".join(prepared_names[:4])
            + ". This is supporting material, not a substitute for the verified "
            "Canvas assignment requirements above."
        )
    if unprepared_names:
        text += (
            "\n\nCanvas lists related module material that is not prepared locally: "
            + ", ".join(unprepared_names[:4])
            + ". I cannot verify any additional instructions inside those files yet."
        )
    blocks: list[AssistantResponseBlock] = [
        AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),
        _citation_block(assignment, course_name=ctx.course.course_name),
    ]
    return AssistantResponse(
        status="ok",
        blocks=tuple(blocks),
        course_id=assignment.canvas_course_id,
    )


def _dedupe_documents(
    documents: tuple[DocumentEvidence, ...],
) -> tuple[DocumentEvidence, ...]:
    seen: set[str] = set()
    out: list[DocumentEvidence] = []
    for item in documents:
        if item.canvas_file_id in seen:
            continue
        seen.add(item.canvas_file_id)
        out.append(item)
    return tuple(out)


def _explicit_quiz_lecture_coverage(
    ctx: AssignmentContext,
) -> tuple[str, tuple[AssistantEvidenceReference, ...]] | None:
    """Extract only a narrowly structured lecture range; never reflect raw instructions.

    Canvas announcements remain untrusted text. A parsed range is attributed
    to its original source rather than treated as authoritative quiz metadata.
    """
    assignment = ctx.assignment
    title = " ".join((assignment.name or "").split())
    if not (title and len(title) <= 100 and re.search(
        r"\b(?:quiz|exam|midterm|test)\b", title, flags=re.IGNORECASE
    )):
        return None
    pattern = re.compile(
        rf"\b{re.escape(title)}\b\s*(?:[:\--]\s*)?"
        r"(?:will\s+)?(?:cover|covers|include|includes)\s+"
        r"lectures?\s+(\d{1,2})\s*(?:-|-|to)\s*(\d{1,2})\b",
        flags=re.IGNORECASE,
    )
    matches: dict[tuple[int, int], list[str]] = {}
    for source in ctx.canvas_text_evidence:
        if (
            source.canvas_course_id != assignment.canvas_course_id
            or source.authority is not SourceAuthority.CANVAS_TRUTH
            or source.source_kind not in {"announcement", "syllabus"}
        ):
            continue
        normalized = " ".join(source.excerpt.split())
        found = pattern.search(normalized)
        if found is None:
            continue
        # A positive-looking range with an adjacent exclusion or correction
        # is not sufficient evidence for exact quiz coverage. Do not guess.
        clause = normalized[max(0, found.start() - 30):min(len(normalized), found.end() + 55)]
        if re.search(
            r"\b(?:not|no|except|exclude[ds]?|excluding|other than|instead of|"
            r"correction|withdrawn|superseded)\b",
            clause, flags=re.IGNORECASE,
        ):
            continue
        first, last = int(found.group(1)), int(found.group(2))
        if not 1 <= first <= last <= 99:
            continue
        matches.setdefault((first, last), []).append(source.source_id)
    if not matches:
        return None
    ids = sorted({source_id for source_ids in matches.values() for source_id in source_ids})
    references = tuple(
        AssistantEvidenceReference(
            authority=SourceAuthority.CANVAS_TRUTH, identifier=source_id,
        )
        for source_id in ids[:8]
    )
    if len(matches) != 1:
        return (
            "Course announcements list conflicting lecture ranges for this assessment. "
            "Check the latest announcement or the instructor before relying on either.",
            references,
        )
    first, last = next(iter(matches))
    return (
        f"A course announcement or syllabus explicitly lists Lectures {first}-{last} "
        f"for {title}. This is attributed to the course source, not independently "
        "confirmed by the quiz listing itself. Check for later updates.",
        references,
    )


def build_assignment_study_materials_answer(
    ctx: AssignmentContext,
    *,
    timezone: ZoneInfo,
) -> AssistantResponse:
    assignment = ctx.assignment
    title = _assignment_title(assignment)
    course = _course_label(assignment, ctx.course.course_name)

    seen_ids: set[str] = set()
    all_refs: list[AssistantEvidenceReference] = []

    coverage = _explicit_quiz_lecture_coverage(ctx)
    if coverage is not None:
        statement, cov_refs = coverage
        for ref in cov_refs:
            if ref.identifier not in seen_ids:
                seen_ids.add(ref.identifier)
                all_refs.append(ref)

    for item in ctx.canvas_text_evidence:
        if item.canvas_course_id == assignment.canvas_course_id and item.source_id not in seen_ids:
            seen_ids.add(item.source_id)
            all_refs.append(
                AssistantEvidenceReference(
                    authority=item.authority,
                    identifier=item.source_id,
                )
            )

    for link in ctx.topic_module_links:
        if link.canvas_module_id not in seen_ids:
            seen_ids.add(link.canvas_module_id)
            all_refs.append(
                AssistantEvidenceReference(
                    authority=SourceAuthority.CANVAS_TRUTH,
                    identifier=link.canvas_module_id,
                )
            )

    for mod_id in ctx.modules:
        if mod_id not in seen_ids:
            seen_ids.add(mod_id)
            all_refs.append(
                AssistantEvidenceReference(
                    authority=SourceAuthority.CANVAS_TRUTH,
                    identifier=mod_id,
                )
            )

    for doc in ctx.retrieval_evidence:
        if doc.canvas_file_id not in seen_ids:
            seen_ids.add(doc.canvas_file_id)
            all_refs.append(
                AssistantEvidenceReference(
                    authority=doc.authority,
                    identifier=doc.canvas_file_id,
                )
            )

    if coverage is not None:
        return AssistantResponse(
            status="ok",
            blocks=(
                AssistantResponseBlock(
                    type=ResponseBlockType.TEXT,
                    text=(
                        f"{title} in {course} "
                        f"{due_clause(assignment.due_at, timezone=timezone)}. "
                        + statement
                    ),
                    references=tuple(all_refs),
                ),
                _citation_block(assignment, course_name=ctx.course.course_name),
            ),
            course_id=assignment.canvas_course_id,
        )

    linked = _dedupe_documents(ctx.retrieval_evidence)
    related_names = [
        doc.display_name or doc.filename or "Course material" for doc in linked
    ]
    if not related_names and ctx.related_documents:
        related_names = [
            doc.display_name or doc.filename or "Course material"
            for doc in ctx.related_documents[:8]
        ]
    # A document can be shared with a module without proving that it is a
    # required or covered quiz topic. Present it only as a possible lead.
    if related_names:
        bullet = "\n".join(f"• {name}" for name in related_names[:8])
        text = (
            f"{title} in {course} {due_clause(assignment.due_at, timezone=timezone)}. "
            "I cannot verify required study materials from the quiz listing alone. "
            "The following files are associated with the assignment's Canvas module "
            "and may be useful starting points:\n\n"
            f"{bullet}\n\n"
            "These links do not confirm quiz coverage. Check the quiz instructions "
            "or a professor announcement for the actual topics."
        )
    else:
        text = (
            f"{title} in {course} {due_clause(assignment.due_at, timezone=timezone)}. "
            "Canvas does not list module-linked files for this assignment, and I could not verify "
            "which lecture PDFs apply from the assignment listing alone. "
            "Check the assignment page in Canvas or ask your instructor "
            "if materials were added elsewhere."
        )

    return AssistantResponse(
        status="ok",
        blocks=(
            AssistantResponseBlock(
                type=ResponseBlockType.TEXT,
                text=text,
                references=tuple(all_refs),
            ),
            _citation_block(assignment, course_name=ctx.course.course_name),
        ),
        course_id=assignment.canvas_course_id,
    )



def build_deadlines_answer(
    deadlines: DeadlineToolResult,
    *,
    timezone: ZoneInfo,
    window_label: str,
    course_names: Mapping[str, str | None] | None = None,
) -> AssistantResponse:
    if not deadlines.assignments:
        text = f"Nothing is due {window_label} based on your synced Canvas data."
        return AssistantResponse(
            status="ok",
            blocks=(
                AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),
                AssistantResponseBlock(
                    type=ResponseBlockType.DEADLINES,
                    payload={
                        "window": deadlines.window,
                        "assignments": [],
                        "empty": True,
                        "message": text,
                    },
                ),
            ),
        )

    header = (
        "Here is what is overdue:"
        if window_label == "as overdue work"
        else f"Here is what is due {window_label}:"
    )
    lines: list[str] = [header]
    # Names such as "Quiz 3" repeat across courses, so label items whenever more
    # than one course is involved.
    multi_course = len({item.canvas_course_id for item in deadlines.assignments}) > 1
    for item in deadlines.assignments[:15]:
        title = item.name or "Untitled assignment"
        if multi_course:
            course_name = (course_names or {}).get(item.canvas_course_id)
            if course_name:
                title = f"{title} ({course_name})"
        due = format_due(item.due_at, timezone=timezone)
        lines.append(f"• {title} — {due}")
    if len(deadlines.assignments) > 15:
        lines.append(f"…and {len(deadlines.assignments) - 15} more.")
    text = "\n".join(lines)
    return AssistantResponse(
        status="ok",
        blocks=(
            AssistantResponseBlock(type=ResponseBlockType.TEXT, text=text),
            AssistantResponseBlock(
                type=ResponseBlockType.DEADLINES,
                payload={
                    "window": deadlines.window,
                    "assignments": [
                        a.model_dump(mode="json") for a in deadlines.assignments
                    ],
                    "empty": False,
                    "message": None,
                },
            ),
        ),
    )



def try_deterministic_answer(
    *,
    intent: AcademicQuestionIntent,
    assignment_context: AssignmentContext | None,
    deadlines: DeadlineToolResult | None,
    timezone: ZoneInfo,
    deadline_window_label: str,
    course_names: Mapping[str, str | None] | None = None,
) -> AssistantResponse | None:
    if intent is AcademicQuestionIntent.ASSIGNMENT_DUE and assignment_context is not None:
        return build_assignment_due_answer(assignment_context, timezone=timezone)
    if intent is AcademicQuestionIntent.ASSIGNMENT_POINTS and assignment_context is not None:
        return build_assignment_points_answer(assignment_context, timezone=timezone)
    if (
        intent is AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS
        and assignment_context is not None
    ):
        return build_assignment_study_materials_answer(assignment_context, timezone=timezone)
    if intent is AcademicQuestionIntent.ASSIGNMENT_EXPLAIN and assignment_context is not None:
        answer = build_assignment_explain_answer(assignment_context, timezone=timezone)
        if answer is not None:
            return answer
    if intent is AcademicQuestionIntent.DEADLINES_WINDOW and deadlines is not None:
        return build_deadlines_answer(
            deadlines,
            timezone=timezone,
            window_label=deadline_window_label,
            course_names=course_names,
        )
    return None
