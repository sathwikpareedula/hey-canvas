from datetime import UTC, datetime

import pytest
from app.assistant_tools.assignment_resolution import (
    find_assignment_id_for_query,
    find_assignment_matches,
)
from app.database.models import Assignment
from sqlalchemy.orm import Session

from tests.services.test_assignment_sync import add_course


def _seed_assignments(session: Session) -> None:
    course = add_course(session, "278791", name="Robotics")
    now = datetime.now(UTC)
    session.add_all(
        [
            Assignment(
                canvas_assignment_id="a-quiz-3",
                course_id=course.id,
                name="Quiz 3",
                due_at=None,
                submission_types=["online_quiz"],
                workflow_state="published",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            ),
            Assignment(
                canvas_assignment_id="a-hw-1",
                course_id=course.id,
                name="Homework 1",
                due_at=None,
                submission_types=["online_upload"],
                workflow_state="published",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            ),
        ]
    )
    session.commit()


def test_find_assignment_id_for_quiz_query(session: Session) -> None:
    _seed_assignments(session)
    resolved = find_assignment_id_for_query(
        session,
        canvas_course_id="278791",
        query="When is Robotics Quiz 3 and what topics are covered?",
    )
    assert resolved == "a-quiz-3"


@pytest.mark.parametrize(
    "title",
    (
        "Practice Problems 1",
        "Problem Set 1",
        "Worksheet 1",
        "Quiz 3",
        "Homework 2",
    ),
)
def test_exact_numbered_assignment_titles_resolve_within_course(
    session: Session, title: str
) -> None:
    course = add_course(session, "course-a", name="Algorithms")
    now = datetime.now(UTC)
    session.add_all(
        [
            Assignment(
                canvas_assignment_id="target",
                course_id=course.id,
                name=title,
                due_at=None,
                submission_types=["online_upload"],
                workflow_state="published",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            ),
            Assignment(
                canvas_assignment_id="nearby",
                course_id=course.id,
                name=f"{title}0",
                due_at=None,
                submission_types=["online_upload"],
                workflow_state="published",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            ),
        ]
    )
    session.commit()

    assert (
        find_assignment_id_for_query(
            session,
            canvas_course_id="course-a",
            query=f"Explain {title} in plain language",
        )
        == "target"
    )


def test_same_assignment_title_across_courses_requires_course_scope(session: Session) -> None:
    now = datetime.now(UTC)
    for course_id in ("course-a", "course-b"):
        course = add_course(session, course_id, name=f"Course {course_id}")
        session.add(
            Assignment(
                canvas_assignment_id=f"quiz-{course_id}",
                course_id=course.id,
                name="Quiz 3",
                due_at=None,
                submission_types=["online_quiz"],
                workflow_state="published",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            )
        )
    session.commit()

    assert len(find_assignment_matches(session, query="What is Quiz 3 about?")) == 2
    assert (
        find_assignment_id_for_query(
            session,
            canvas_course_id="course-b",
            query="What is Quiz 3 about?",
        )
        == "quiz-course-b"
    )
