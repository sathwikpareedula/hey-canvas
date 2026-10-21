from datetime import UTC, datetime, timedelta

import pytest
from app.calendar.models import CalendarConfirmation, InMemoryCalendarProvider
from app.calendar.service import AcademicCalendarService
from app.database.models import Assignment, Course
from app.notifications.service import NotificationService
from app.reminders.models import ReminderPreference
from app.reminders.service import ReminderPlanService
from sqlalchemy import select


def _assignment(
    session,
    *,
    due_at: datetime,
    course_id: str = "course-1",
    assignment_id: str = "assignment-1",
) -> Assignment:
    course = session.scalar(select(Course).where(Course.canvas_course_id == course_id))
    if course is None:
        course = Course(
            canvas_course_id=course_id,
            course_code="CSE 101",
            course_name="Course",
            first_seen_at=due_at,
            last_seen_at=due_at,
            last_synced_at=due_at,
        )
    assignment = Assignment(
        course=course,
        canvas_assignment_id=assignment_id,
        name="Homework",
        due_at=due_at,
        submission_types=[],
        first_seen_at=due_at,
        last_seen_at=due_at,
        last_synced_at=due_at,
    )
    session.add(assignment)
    session.commit()
    return assignment


def test_notification_generation_persists_and_deduplicates(session) -> None:
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    _assignment(session, due_at=now + timedelta(hours=20))
    service = NotificationService(session, clock=lambda: now)

    first = service.list_notifications()
    second = service.list_notifications()

    assert first.total == 1
    assert second.total == 1
    assert second.items[0].notification_type == "assignment_due_tomorrow"


def test_notification_read_and_dismiss_persist(session) -> None:
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    _assignment(session, due_at=now + timedelta(hours=20))
    service = NotificationService(session, clock=lambda: now)
    item = service.list_notifications().items[0]

    assert service.mark_read(item.id).read is True
    assert service.dismiss(item.id).dismissed is True


def test_reminder_preferences_and_plan_are_bounded(session) -> None:
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    assignment = _assignment(session, due_at=now + timedelta(days=2))
    service = ReminderPlanService(session, clock=lambda: now)
    preference = ReminderPreference(lead_times_hours=(48, 3))

    service.save_preferences(preference)
    assert service.get_preferences() == preference
    plan = service.preview_plan(assignment)
    assert [item.lead_hours for item in plan.plan.reminders] == [48, 3]

    with pytest.raises(ValueError):
        service.save_preferences(ReminderPreference(timezone="not/a-zone"))


def test_calendar_preview_confirmation_is_single_use_and_stale_safe(session) -> None:
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    assignment = _assignment(session, due_at=now + timedelta(days=1))
    provider = InMemoryCalendarProvider()
    service = AcademicCalendarService(session, provider=provider)

    event, confirmation = service.preview_and_stage(assignment)
    assert event.status == "pending"
    result = service.confirm_and_execute(confirmation, assignment=assignment)
    assert result.status == "confirmed"
    with pytest.raises(ValueError, match="already used"):
        service.confirm_and_execute(confirmation, assignment=assignment)

    changed = _assignment(
        session,
        due_at=now + timedelta(days=2),
        assignment_id="assignment-2",
    )
    _, stale_confirmation = service.preview_and_stage(changed)
    changed.due_at = now + timedelta(days=3)
    session.commit()
    with pytest.raises(ValueError, match="stale"):
        service.confirm_and_execute(stale_confirmation, assignment=changed)


def test_calendar_wrong_confirmation_is_rejected(session) -> None:
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    assignment = _assignment(session, due_at=now + timedelta(days=1))
    other = _assignment(session, due_at=now + timedelta(days=1), assignment_id="assignment-2")
    service = AcademicCalendarService(session, provider=InMemoryCalendarProvider())
    _, confirmation = service.preview_and_stage(assignment)

    with pytest.raises(ValueError, match="does not match"):
        service.confirm_and_execute(
            CalendarConfirmation(
                action_id=confirmation.action_id,
                confirmation_token=confirmation.confirmation_token,
            ),
            assignment=other,
        )
