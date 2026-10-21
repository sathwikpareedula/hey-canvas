"""Tests for knowledge coverage summary and preparation status."""

from sqlalchemy.orm import Session

from app.focus_courses.service import FocusCourseService
from app.services.knowledge_coverage import (
    KnowledgeCoverageService,
    get_preparation_status,
)
from tests.services.test_assignment_sync import add_course


def test_knowledge_coverage_summary_empty(session: Session) -> None:
    service = KnowledgeCoverageService(session)
    summary = service.get_coverage()
    assert summary.courses_total == 0
    assert summary.assignments_total == 0
    assert summary.files_total == 0


def test_knowledge_coverage_with_course_and_assignments(session: Session) -> None:
    add_course(session, "cse-4360", name="Autonomous Robotics")
    FocusCourseService(session).replace(["cse-4360"])

    service = KnowledgeCoverageService(session)
    summary = service.get_coverage(course_id="cse-4360")
    assert summary.courses_total == 1
    assert summary.focus_courses_total == 1
    assert len(summary.courses) == 1
    c = summary.courses[0]
    assert c.course_id == "cse-4360"
    assert c.is_focus is True
    assert c.files_total == 0
    assert c.has_syllabus is False


def test_preparation_status_and_trigger() -> None:
    status = get_preparation_status()
    assert status.is_preparing is False
