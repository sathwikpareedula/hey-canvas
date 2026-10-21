"""Generic catalog sizes — no institution-specific course ids."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.assignments.models import AssignmentSnapshot
from app.database.assignment_repository import AssignmentRepository
from app.services.deadlines import DeadlineService, DeadlineWindow
from sqlalchemy.orm import Session

from tests.services.test_assignment_sync import add_course

CHICAGO = ZoneInfo("America/Chicago")
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _seed_course_assignments(
    session: Session, course_id: str, count: int, *, due: datetime
) -> None:
    course = add_course(session, course_id)
    snapshots = [
        AssignmentSnapshot(
            canvas_assignment_id=f"{course_id}-asg-{i}",
            canvas_course_id=course_id,
            name=f"Work {i}",
            due_at=due + timedelta(hours=i),
        )
        for i in range(count)
    ]
    AssignmentRepository(session).synchronize_course(course, snapshots, synced_at=NOW)
    session.commit()


@pytest.mark.parametrize("active_count", [1, 3, 5, 8, 20])
def test_deadline_windows_scale_with_catalog_size(session: Session, active_count: int) -> None:
    for i in range(active_count):
        _seed_course_assignments(session, f"generic-{active_count}-{i}", 1, due=NOW)
    service = DeadlineService(
        AssignmentRepository(session),
        academic_timezone=CHICAGO,
        clock=lambda: NOW,
    )
    rows = service.query(DeadlineWindow.TODAY)
    assert len(rows) >= 1
    assert all(r.canvas_course_id.startswith("generic-") for r in rows)


def test_course_scoped_deadlines_never_include_other_course(session: Session) -> None:
    _seed_course_assignments(session, "generic-a", 1, due=NOW)
    _seed_course_assignments(session, "generic-b", 1, due=NOW)
    service = DeadlineService(
        AssignmentRepository(session),
        academic_timezone=CHICAGO,
        clock=lambda: NOW,
    )
    scoped = service.query(DeadlineWindow.TODAY, canvas_course_id="generic-a")
    assert scoped
    assert all(row.canvas_course_id == "generic-a" for row in scoped)
