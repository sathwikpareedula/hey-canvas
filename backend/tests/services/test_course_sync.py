from datetime import UTC, datetime, timedelta

import pytest
from app.courses.models import CourseSnapshot
from app.database.course_repository import CourseRepository
from app.database.models import Course
from app.services.course_sync import CourseSyncService
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker


class FakeCourseSource:
    def __init__(self, snapshots: list[CourseSnapshot]) -> None:
        self.snapshots = snapshots

    async def fetch_current_courses(self) -> list[CourseSnapshot]:
        return self.snapshots


def snapshot(course_id: str = "101", *, name: str = "Autonomous Robots") -> CourseSnapshot:
    return CourseSnapshot(
        canvas_course_id=course_id,
        course_code="CSE 4360",
        course_name=name,
        term_canvas_id="2026-fall",
        term_name="Fall 2026",
        start_at=datetime(2026, 8, 24, 14, 0, tzinfo=UTC),
        workflow_state="available",
        enrollment_state="active",
        enrollment_type="StudentEnrollment",
    )


@pytest.mark.asyncio
async def test_first_sync_creates_and_persists_courses(session: Session) -> None:
    now = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
    service = CourseSyncService(
        source=FakeCourseSource([snapshot("101"), snapshot("102", name="Senior Design")]),
        session=session,
        clock=lambda: now,
    )

    summary = await service.synchronize()
    courses = CourseRepository(session).list_all()

    assert summary.model_dump() == {
        "courses_received": 2,
        "courses_created": 2,
        "courses_updated": 0,
        "courses_unchanged": 0,
    }
    assert {course.canvas_course_id for course in courses} == {"101", "102"}
    assert all(course.first_seen_at == now for course in courses)


@pytest.mark.asyncio
async def test_repeated_sync_is_idempotent_and_marks_unchanged(session: Session) -> None:
    first_time = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
    second_time = first_time + timedelta(hours=1)
    source = FakeCourseSource([snapshot()])

    first = await CourseSyncService(
        source=source,
        session=session,
        clock=lambda: first_time,
    ).synchronize()
    second = await CourseSyncService(
        source=source,
        session=session,
        clock=lambda: second_time,
    ).synchronize()

    course = session.scalar(select(Course).where(Course.canvas_course_id == "101"))
    count = session.scalar(select(func.count()).select_from(Course))
    assert first.courses_created == 1
    assert second.courses_unchanged == 1
    assert second.courses_created == 0
    assert count == 1
    assert course is not None
    assert course.first_seen_at == first_time
    assert course.last_seen_at == second_time
    assert course.last_synced_at == second_time


@pytest.mark.asyncio
async def test_changed_metadata_updates_existing_course(session: Session) -> None:
    times = iter(
        [
            datetime(2026, 9, 28, 15, 0, tzinfo=UTC),
            datetime(2026, 9, 28, 16, 0, tzinfo=UTC),
        ]
    )
    source = FakeCourseSource([snapshot()])
    await CourseSyncService(source=source, session=session, clock=lambda: next(times)).synchronize()
    source.snapshots = [snapshot(name="Autonomous Robotics")]

    summary = await CourseSyncService(
        source=source,
        session=session,
        clock=lambda: next(times),
    ).synchronize()

    course = session.scalar(select(Course).where(Course.canvas_course_id == "101"))
    assert summary.courses_updated == 1
    assert summary.courses_created == 0
    assert course is not None
    assert course.course_name == "Autonomous Robotics"


@pytest.mark.asyncio
async def test_empty_or_partial_response_does_not_delete_courses(session: Session) -> None:
    now = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
    source = FakeCourseSource([snapshot("101"), snapshot("102")])
    await CourseSyncService(source=source, session=session, clock=lambda: now).synchronize()
    source.snapshots = []

    summary = await CourseSyncService(
        source=source,
        session=session,
        clock=lambda: now,
    ).synchronize()
    count = session.scalar(select(func.count()).select_from(Course))

    assert summary.courses_received == 0
    assert count == 2


@pytest.mark.asyncio
async def test_conflicting_duplicate_payloads_roll_back_atomically(session: Session) -> None:
    source = FakeCourseSource([snapshot(), snapshot(name="Conflicting Name")])

    with pytest.raises(ValueError, match="conflicting course snapshots"):
        await CourseSyncService(source=source, session=session).synchronize()

    assert session.scalar(select(func.count()).select_from(Course)) == 0


@pytest.mark.asyncio
async def test_persistence_survives_a_new_database_session(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as first_session:
        await CourseSyncService(
            source=FakeCourseSource([snapshot()]),
            session=first_session,
        ).synchronize()

    with session_factory() as second_session:
        course = second_session.scalar(select(Course).where(Course.canvas_course_id == "101"))

    assert course is not None
    assert course.course_name == "Autonomous Robots"
    assert course.start_at is not None
    assert course.start_at.tzinfo == UTC
