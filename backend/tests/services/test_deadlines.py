from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.assignments.models import AssignmentSnapshot
from app.database.assignment_repository import AssignmentRepository
from app.services.deadlines import DeadlineService, DeadlineWindow
from sqlalchemy.orm import Session

from tests.services.test_assignment_sync import add_course

CHICAGO = ZoneInfo("America/Chicago")
FIXED_NOW = datetime(2026, 9, 30, 15, 0, tzinfo=UTC)  # Wednesday 10:00 CDT


def persist_deadlines(
    session: Session,
    values: list[tuple[str, datetime | None]],
    *,
    course_id: str = "101",
) -> None:
    course = add_course(session, course_id)
    snapshots = [
        AssignmentSnapshot(
            canvas_assignment_id=assignment_id,
            canvas_course_id=course_id,
            name=assignment_id,
            due_at=due_at,
        )
        for assignment_id, due_at in values
    ]
    AssignmentRepository(session).synchronize_course(
        course,
        snapshots,
        synced_at=FIXED_NOW,
    )
    session.commit()


def query(
    session: Session,
    window: DeadlineWindow,
    *,
    now: datetime = FIXED_NOW,
    course_id: str | None = None,
) -> list[str]:
    results = DeadlineService(
        AssignmentRepository(session),
        academic_timezone=CHICAGO,
        clock=lambda: now,
    ).query(window, canvas_course_id=course_id)
    return [item.canvas_assignment_id for item in results]


@pytest.mark.parametrize(
    ("window", "expected"),
    [
        (DeadlineWindow.TODAY, ["today"]),
        (DeadlineWindow.TOMORROW, ["tomorrow"]),
        (DeadlineWindow.THIS_WEEK, ["week-past", "today", "tomorrow"]),
        (DeadlineWindow.NEXT_WEEK, ["next-week"]),
        (DeadlineWindow.NEXT_7_DAYS, ["today", "tomorrow", "next-week"]),
        (DeadlineWindow.THIS_MONTH, ["week-past", "today"]),
        (DeadlineWindow.NEXT_MONTH, ["tomorrow", "next-week"]),
        (DeadlineWindow.OVERDUE, ["week-past"]),
        (DeadlineWindow.UPCOMING, ["today", "tomorrow", "next-week", "later"]),
    ],
)
def test_deadline_windows(
    window: DeadlineWindow,
    expected: list[str],
    session: Session,
) -> None:
    persist_deadlines(
        session,
        [
            ("week-past", datetime(2026, 9, 29, 14, 0, tzinfo=UTC)),
            ("today", FIXED_NOW),
            ("tomorrow", datetime(2026, 10, 1, 17, 0, tzinfo=UTC)),
            ("next-week", datetime(2026, 10, 6, 17, 0, tzinfo=UTC)),
            ("later", datetime(2026, 11, 1, 17, 0, tzinfo=UTC)),
            ("no-due-date", None),
        ],
    )

    assert query(session, window) == expected


def test_today_uses_inclusive_lower_and_exclusive_upper_boundaries(session: Session) -> None:
    start_today = datetime(2026, 9, 30, 5, 0, tzinfo=UTC)
    start_tomorrow = datetime(2026, 10, 1, 5, 0, tzinfo=UTC)
    persist_deadlines(
        session,
        [
            ("lower", start_today),
            ("inside", start_tomorrow - timedelta(microseconds=1)),
            ("upper", start_tomorrow),
        ],
    )

    assert query(session, DeadlineWindow.TODAY) == ["lower", "inside"]


def test_next_seven_days_handles_dst_as_local_calendar_time(session: Session) -> None:
    now = datetime(2026, 3, 7, 18, 0, tzinfo=UTC)  # noon CST, day before spring forward
    local_upper = datetime(2026, 3, 14, 12, 0, tzinfo=CHICAGO)
    utc_upper = local_upper.astimezone(UTC)
    assert utc_upper - now == timedelta(hours=167)
    persist_deadlines(
        session,
        [
            ("inside", utc_upper - timedelta(microseconds=1)),
            ("upper", utc_upper),
        ],
    )

    assert query(session, DeadlineWindow.NEXT_7_DAYS, now=now) == ["inside"]


@pytest.mark.parametrize(
    ("now", "inside", "outside"),
    [
        (
            datetime(2026, 10, 3, 17, 0, tzinfo=UTC),
            datetime(2026, 10, 5, 5, 0, tzinfo=UTC),
            datetime(2026, 10, 12, 5, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 12, 31, 18, 0, tzinfo=UTC),
            datetime(2027, 1, 4, 6, 0, tzinfo=UTC),
            datetime(2027, 1, 11, 6, 0, tzinfo=UTC),
        ),
    ],
)
def test_next_week_uses_next_local_calendar_week(
    session: Session, now: datetime, inside: datetime, outside: datetime
) -> None:
    persist_deadlines(session, [("inside", inside), ("outside", outside)])
    assert query(session, DeadlineWindow.NEXT_WEEK, now=now) == ["inside"]


@pytest.mark.parametrize(
    ("now", "inside", "outside"),
    [
        (
            datetime(2026, 10, 3, 17, 0, tzinfo=UTC),
            datetime(2026, 10, 31, 23, 0, tzinfo=UTC),
            datetime(2026, 11, 1, 5, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 12, 15, 18, 0, tzinfo=UTC),
            datetime(2026, 12, 31, 23, 0, tzinfo=UTC),
            datetime(2027, 1, 1, 6, 0, tzinfo=UTC),
        ),
    ],
)
def test_this_month_uses_local_calendar_month(
    session: Session, now: datetime, inside: datetime, outside: datetime
) -> None:
    persist_deadlines(session, [("inside", inside), ("outside", outside)])
    assert query(session, DeadlineWindow.THIS_MONTH, now=now) == ["inside"]


def test_explicit_calendar_month_and_year_are_timezone_aware(session: Session) -> None:
    lower = datetime(2027, 2, 1, 6, 0, tzinfo=UTC)
    upper = datetime(2027, 3, 1, 6, 0, tzinfo=UTC)
    persist_deadlines(
        session,
        [
            ("inside", lower),
            ("inside-last", upper - timedelta(microseconds=1)),
            ("outside", upper),
        ],
    )
    service = DeadlineService(
        AssignmentRepository(session), academic_timezone=CHICAGO, clock=lambda: FIXED_NOW
    )
    assert [
        item.canvas_assignment_id for item in service.query_month(2027, 2)
    ] == ["inside", "inside-last"]


def test_deadline_queries_filter_by_canvas_course_id(session: Session) -> None:
    persist_deadlines(session, [("course-101", FIXED_NOW)], course_id="101")
    persist_deadlines(session, [("course-102", FIXED_NOW)], course_id="102")

    assert query(session, DeadlineWindow.TODAY, course_id="102") == ["course-102"]
