from datetime import UTC, datetime, timedelta

import pytest
from app.assignments.models import AssignmentSnapshot
from app.canvas.exceptions import CanvasAuthenticationError
from app.courses.models import CourseSnapshot
from app.database.assignment_repository import AssignmentRepository
from app.database.course_repository import CourseRepository
from app.database.models import Assignment, Course
from app.services.assignment_sync import AssignmentSyncService
from sqlalchemy import func, select
from sqlalchemy.orm import Session


class FakeAssignmentSource:
    def __init__(self, results: dict[str, list[AssignmentSnapshot] | Exception]) -> None:
        self.results = results

    async def fetch_course_assignments(self, canvas_course_id: str) -> list[AssignmentSnapshot]:
        result = self.results[canvas_course_id]
        if isinstance(result, Exception):
            raise result
        return result


def add_course(session: Session, course_id: str, *, name: str = "Course") -> Course:
    now = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    CourseRepository(session).synchronize(
        [
            CourseSnapshot(
                canvas_course_id=course_id,
                course_name=name,
                workflow_state="available",
                enrollment_state="active",
            )
        ],
        synced_at=now,
    )
    session.commit()
    course = session.scalar(select(Course).where(Course.canvas_course_id == course_id))
    assert course is not None
    return course


def assignment(
    assignment_id: str = "501",
    *,
    course_id: str = "101",
    name: str = "Homework 1",
    due_at: datetime | None = None,
    description: str = "<p>Instructions</p>",
) -> AssignmentSnapshot:
    return AssignmentSnapshot(
        canvas_assignment_id=assignment_id,
        canvas_course_id=course_id,
        name=name,
        description_html=description,
        due_at=due_at,
        submission_types=("online_upload",),
        workflow_state="published",
        published=True,
    )


@pytest.mark.asyncio
async def test_first_sync_creates_then_identical_sync_is_idempotent(session: Session) -> None:
    add_course(session, "101")
    first_at = datetime(2026, 9, 28, 13, 0, tzinfo=UTC)
    second_at = first_at + timedelta(hours=1)
    source = FakeAssignmentSource({"101": [assignment()]})

    first = await AssignmentSyncService(
        source=source, session=session, clock=lambda: first_at
    ).synchronize()
    second = await AssignmentSyncService(
        source=source, session=session, clock=lambda: second_at
    ).synchronize()

    stored = session.scalar(select(Assignment))
    assert first.assignments_created == 1
    assert second.assignments_unchanged == 1
    assert session.scalar(select(func.count()).select_from(Assignment)) == 1
    assert stored is not None
    assert stored.first_seen_at == first_at
    assert stored.last_synced_at == second_at


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["name", "due_at", "description"])
async def test_metadata_changes_update_existing_assignment(change: str, session: Session) -> None:
    add_course(session, "101")
    source = FakeAssignmentSource({"101": [assignment()]})
    await AssignmentSyncService(source=source, session=session).synchronize()
    kwargs: dict[str, object] = {}
    if change == "name":
        kwargs["name"] = "Renamed Homework"
    elif change == "due_at":
        kwargs["due_at"] = datetime(2026, 10, 5, tzinfo=UTC)
    else:
        kwargs["description"] = "<p>Changed instructions</p>"
    source.results["101"] = [assignment(**kwargs)]  # type: ignore[arg-type]

    summary = await AssignmentSyncService(source=source, session=session).synchronize()

    assert summary.assignments_updated == 1
    stored = session.scalar(select(Assignment))
    assert stored is not None
    if change == "name":
        assert stored.name == "Renamed Homework"
    elif change == "due_at":
        assert stored.due_at == datetime(2026, 10, 5, tzinfo=UTC)
    else:
        assert stored.description_html == "<p>Changed instructions</p>"


@pytest.mark.asyncio
async def test_absent_assignment_is_not_deleted(session: Session) -> None:
    add_course(session, "101")
    source = FakeAssignmentSource({"101": [assignment()]})
    await AssignmentSyncService(source=source, session=session).synchronize()
    source.results["101"] = []

    await AssignmentSyncService(source=source, session=session).synchronize()

    assert session.scalar(select(func.count()).select_from(Assignment)) == 1


@pytest.mark.asyncio
async def test_assignments_remain_associated_with_their_courses(session: Session) -> None:
    add_course(session, "101")
    add_course(session, "102")
    source = FakeAssignmentSource(
        {
            "101": [assignment("501", course_id="101")],
            "102": [assignment("501", course_id="102")],
        }
    )

    summary = await AssignmentSyncService(source=source, session=session).synchronize()
    stored = AssignmentRepository(session).list_all()

    assert summary.assignments_created == 2
    assert {(item.canvas_course_id, item.canvas_assignment_id) for item in stored} == {
        ("101", "501"),
        ("102", "501"),
    }


@pytest.mark.asyncio
async def test_one_course_failure_does_not_rollback_another_course(
    session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    add_course(session, "101")
    add_course(session, "102")
    secret = "unit-test-secret-body"
    source = FakeAssignmentSource(
        {
            "101": CanvasAuthenticationError(
                f"Canvas rejected credential {secret} (401)", status_code=401
            ),
            "102": [assignment(course_id="102")],
        }
    )
    caplog.set_level("INFO")

    summary = await AssignmentSyncService(source=source, session=session).synchronize()

    assert summary.courses_failed == 1
    assert summary.courses_succeeded == 1
    assert summary.assignments_created == 1
    assert secret not in caplog.text
    assert secret not in summary.failures[0].message
    assert summary.failures[0].message == "Canvas authentication or authorization failed"
    assert session.scalar(select(func.count()).select_from(Assignment)) == 1


@pytest.mark.asyncio
async def test_success_logs_do_not_include_assignment_html(
    session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    add_course(session, "101")
    marker = "private-assignment-description-marker"
    source = FakeAssignmentSource({"101": [assignment(description=f"<p>{marker}</p>")]})
    caplog.set_level("INFO")

    await AssignmentSyncService(source=source, session=session).synchronize()

    assert marker not in caplog.text


@pytest.mark.asyncio
async def test_conflicting_snapshots_roll_back_that_course(session: Session) -> None:
    add_course(session, "101")
    source = FakeAssignmentSource({"101": [assignment(), assignment(name="Conflicting")]})

    summary = await AssignmentSyncService(source=source, session=session).synchronize()

    assert summary.courses_failed == 1
    assert session.scalar(select(func.count()).select_from(Assignment)) == 0


@pytest.mark.asyncio
async def test_no_courses_returns_zero_summary(session: Session) -> None:
    summary = await AssignmentSyncService(
        source=FakeAssignmentSource({}),
        session=session,
    ).synchronize()

    assert summary.courses_attempted == 0
    assert summary.assignments_received == 0
