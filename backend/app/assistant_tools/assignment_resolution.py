"""Resolve Canvas assignments from natural-language student queries."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Assignment, Course

TOKEN = re.compile(r"[\w'-]+", re.UNICODE)


def _score(name: str, normalized: str, query_terms: set[str]) -> int:
    folded = name.casefold()
    name_terms = set(TOKEN.findall(folded))
    if not name_terms:
        return 0
    overlap = len(query_terms & name_terms)
    if folded in normalized or normalized in folded:
        overlap += 5
    return overlap


def find_assignment_matches(
    session: Session,
    *,
    query: str,
    canvas_course_id: str | None = None,
) -> list[tuple[Course, Assignment]]:
    """Return every best-scoring assignment the query names (empty when none is clear).

    Without a course the search spans all courses, preferring active enrollments,
    so callers can tell a unique match from an ambiguous one.
    """
    normalized = " ".join(query.casefold().split())
    if not normalized:
        return []
    statement = select(Assignment, Course).join(Course, Assignment.course_id == Course.id)
    if canvas_course_id is not None:
        statement = statement.where(Course.canvas_course_id == canvas_course_id)
    rows = [(course, assignment) for assignment, course in session.execute(statement)]
    if not rows:
        return []
    query_terms = set(TOKEN.findall(normalized))
    scored = [
        (_score(assignment.name or "", normalized, query_terms), course, assignment)
        for course, assignment in rows
    ]
    best = max(score for score, _, _ in scored)
    if best < 2:
        return []
    matches = [(course, assignment) for score, course, assignment in scored if score == best]
    if canvas_course_id is None:
        active = [pair for pair in matches if pair[0].enrollment_state in {None, "active"}]
        matches = active or matches
    return matches


def find_assignment_id_for_query(
    session: Session,
    *,
    canvas_course_id: str,
    query: str,
) -> str | None:
    """Pick one assignment when the query names it (e.g. Quiz 3)."""
    matches = find_assignment_matches(session, query=query, canvas_course_id=canvas_course_id)
    if len(matches) != 1:
        return None
    return matches[0][1].canvas_assignment_id
