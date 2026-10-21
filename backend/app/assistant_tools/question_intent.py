"""Classify student questions before retrieval or model calls."""

from __future__ import annotations

import re
from enum import StrEnum

_TOKEN = re.compile(r"[\w'-]+", re.UNICODE)

# Routing keywords that students commonly misspell ("tomorow", "pionts"). Only
# tokens that are not already valid words in this list are corrected, and only
# when the match is very close, so ordinary vocabulary is left untouched.
_ROUTING_VOCABULARY = (
    "today",
    "tomorrow",
    "deadline",
    "points",
    "homework",
    "assignment",
    "assignments",
    "materials",
    "material",
    "explain",
    "overdue",
    "upcoming",
    "synced",
    "lecture",
    "summarize",
    "problems",
    "problem",
    "practice",
    "month",
)
_ROUTING_SET = frozenset(_ROUTING_VOCABULARY)
_CALENDAR_MONTH = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\b",
    re.IGNORECASE,
)


def _one_edit_apart(a: str, b: str) -> bool:
    """True for a single insertion, deletion, substitution or adjacent swap."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]
        if len(diffs) == 1:
            return True
        return (
            len(diffs) == 2
            and diffs[1] == diffs[0] + 1
            and a[diffs[0]] == b[diffs[1]]
            and a[diffs[1]] == b[diffs[0]]
        )
    shorter, longer = sorted((a, b), key=len)
    return any(longer[:i] + longer[i + 1 :] == shorter for i in range(len(longer)))


def normalize_question(query: str) -> str:
    """Casefold, collapse whitespace and repair near-miss routing keywords."""
    pieces = re.split(r"(\W+)", " ".join(query.casefold().split()))
    repaired: list[str] = []
    for piece in pieces:
        if len(piece) >= 5 and piece.isalpha() and piece not in _ROUTING_SET:
            close = [word for word in _ROUTING_VOCABULARY if _one_edit_apart(piece, word)]
            if len(close) == 1:
                piece = close[0]
        repaired.append(piece)
    return "".join(repaired)


class AcademicQuestionIntent(StrEnum):
    ASSIGNMENT_DUE = "assignment_due"
    ASSIGNMENT_POINTS = "assignment_points"
    ASSIGNMENT_EXPLAIN = "assignment_explain"
    ASSIGNMENT_STUDY_MATERIALS = "assignment_study_materials"
    DEADLINES_WINDOW = "deadlines_window"
    LECTURE_MATERIAL = "lecture_material"
    GENERAL_STUDY = "general_study"


def _terms(query: str) -> set[str]:
    return set(_TOKEN.findall(query.casefold()))


def _mentions_assignment(query: str) -> bool:
    return bool(re.search(
        r"\b(?:quiz|homework|hw|exam|midterm|final|assignment|project|lab"
        r"|practice\s*(?:problems?|quiz|exam|assignment)?|problems?\s*#?\d+|problem\s*set\s*#?\d+|pset\s*#?\d+)"
        r"(?:\s*#?\d+)?\b",
        query.casefold(),
    ))


# A conceptual explanation must not be hijacked by a similarly named Canvas quiz.
# Keep this conservative: explicit record questions retain authoritative routing.
_CONCEPT_REQUEST = re.compile(
    r"\b(explain|teach|understand|how does|how do|what is|walk me through|"
    r"step.by.step|example of|introduction to|why do|why does|why is|why)\b",
    re.IGNORECASE,
)
_RECORD_REQUEST = re.compile(
    r"\b(when|due|deadline|points?|worth|submit|submission|"
    r"instructions?|requirements?|rubric|grad(?:e|ed|ing)|score|assigned|"
    r"what does (?:my|the) (?:quiz|assignment|homework|project|lab)|"
    r"practice\s*problems?|problem\s*set)\b",
    re.IGNORECASE,
)


def is_concept_question(query: str) -> bool:
    """Treat direct questions about an assessment as Canvas-record questions."""
    q = normalize_question(query)
    if not _CONCEPT_REQUEST.search(q) or _RECORD_REQUEST.search(q):
        return False
    assessment = (
        r"(?:quiz|assignment|homework|hw|exam|midterm|final|project|lab"
        r"|practice\s*(?:problems?|quiz)?|problem\s*set|problems?\s*#?\d+)"
        r"(?:\s*#?\d+)?\b"
    )
    if re.search(
        r"\b(?:what\s+is|explain|summarize|review|walk\s+me\s+through)"
        r"\s+(?:what\s+)?(?:my|the|this|our)?\s*" + assessment,
        q,
    ):
        return False
    if re.search(
        r"\b(?:what|which)\s+(?:is\s+)?(?:my|the|this|our)?\s*"
        + assessment + r"\s+(?:is\s+)?(?:asking|about)\b",
        q,
    ):
        return False
    return not bool(re.search(
        assessment + r"\s+(?:is\s+)?asking\b",
        q,
    ))


def classify_academic_question(
    query: str,
    *,
    assignment_id: str | None = None,
) -> AcademicQuestionIntent:
    normalized = normalize_question(query)
    has_assignment = (
        assignment_id is not None or _mentions_assignment(normalized)
    ) and not is_concept_question(query)

    if any(
        token in normalized
        for token in (
            "due today",
            "due tomorrow",
            "what do i have due",
            "due this month",
            "due for this month",
            "due for this whole month",
            "this whole month",
            "whole month",
        )
    ):
        return AcademicQuestionIntent.DEADLINES_WINDOW
    if _CALENDAR_MONTH.search(normalized) and any(
        token in normalized for token in ("due", "deadline", "assignment", "work")
    ):
        return AcademicQuestionIntent.DEADLINES_WINDOW
    if (
        any(
            token in normalized
            for token in ("soon", "upcoming", "next 7 days", "next seven days", "this month")
        )
        and any(
            token in normalized
            for token in ("assignment", "assignments", "work", "deadline", "due")
        )
    ):
        return AcademicQuestionIntent.DEADLINES_WINDOW
    # Combined requests still need a verified assignment answer, but a
    # deadline-only classification would silently drop requested study advice.
    study_material_tokens = (
        "which material",
        "materials",
        "should i study",
        "what to study",
        "study for",
        "prepare for",
        "help me prepare",
        "covered topics",
        "topics from",
        "topics for",
        "topics of",
        "quiz topics",
        "exam topics",
        "coverage",
    )
    asks_for_study_materials = has_assignment and any(
        token in normalized for token in study_material_tokens
    )
    if asks_for_study_materials and ("due" in normalized or "deadline" in normalized):
        return AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS

    if "due" in normalized or "deadline" in normalized:
        if has_assignment and not any(
            token in normalized
            for token in (
                "today",
                "tomorrow",
                "this week",
                "next week",
                "this month",
                "this whole month",
                "next month",
                "next 7 days",
                "next seven days",
                "within 7 days",
                "within seven days",
                "this month",
                "month",
                "soon",
                "overdue",
                "upcoming",
            )
        ):
            return AcademicQuestionIntent.ASSIGNMENT_DUE
        return AcademicQuestionIntent.DEADLINES_WINDOW

    if has_assignment and any(
        token in normalized for token in ("point", "points", "worth", "graded", "grading")
    ):
        return AcademicQuestionIntent.ASSIGNMENT_POINTS

    if has_assignment and any(
        token in normalized
        for token in (
            "study",
            "material",
            "materials",
            "read",
            "review",
            "prepare",
            "covered",
            "topics",
            "coverage",
            "syllabus",
        )
    ):
        return AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS

    if has_assignment and any(
        token in normalized
        for token in ("explain", "asking", "mean", "plain language", "what is", "about")
    ):
        return AcademicQuestionIntent.ASSIGNMENT_EXPLAIN

    if any(
        token in normalized
        for token in ("lecture", "slides", "reading", "chapter")
    ) and any(token in normalized for token in ("explain", "concept", "what is", "summarize")):
        return AcademicQuestionIntent.LECTURE_MATERIAL

    if "due" in normalized or "deadline" in normalized:
        return AcademicQuestionIntent.DEADLINES_WINDOW

    return AcademicQuestionIntent.GENERAL_STUDY


def intent_allows_semantic_retrieval(intent: AcademicQuestionIntent) -> bool:
    return intent in {
        AcademicQuestionIntent.LECTURE_MATERIAL,
        AcademicQuestionIntent.GENERAL_STUDY,
        AcademicQuestionIntent.ASSIGNMENT_EXPLAIN,
    }


def intent_requires_model(intent: AcademicQuestionIntent) -> bool:
    """When False, a verified deterministic answer should be attempted first."""
    return intent in {
        AcademicQuestionIntent.LECTURE_MATERIAL,
        AcademicQuestionIntent.GENERAL_STUDY,
        AcademicQuestionIntent.ASSIGNMENT_EXPLAIN,
    }
