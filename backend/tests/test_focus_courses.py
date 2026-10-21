from datetime import UTC, datetime

import pytest
from app.database.models import Course
from app.focus_courses.service import FocusCourseService


def _course(session, course_id: str, *, state: str = "available") -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session.add(
        Course(
            canvas_course_id=course_id,
            course_name=f"Course {course_id}",
            workflow_state=state,
            enrollment_state="active",
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
    )
    session.commit()


def test_focus_courses_replace_add_remove_and_empty_state(session) -> None:
    _course(session, "course-1")
    _course(session, "course-2")
    service = FocusCourseService(session)

    assert service.list() == ()
    selected = service.replace(("course-2", "course-1", "course-2"))
    assert [item.course_id for item in selected] == ["course-2", "course-1"]
    assert service.add("course-1").course_id == "course-1"
    assert [item.course_id for item in service.remove("course-2")] == ["course-1"]
    assert service.remove("course-1") == ()


def test_focus_course_selection_rejects_missing_course_without_losing_existing(session) -> None:
    _course(session, "course-1")
    service = FocusCourseService(session)
    service.replace(("course-1",))

    with pytest.raises(LookupError):
        service.replace(("missing",))
    assert [item.course_id for item in service.list()] == ["course-1"]


def test_focus_suggestions_are_bounded_and_exclude_selected(session) -> None:
    _course(session, "course-1")
    _course(session, "course-2")
    _course(session, "closed", state="completed")
    service = FocusCourseService(session)
    service.replace(("course-1",))

    assert service.suggested() == ("course-2",)
