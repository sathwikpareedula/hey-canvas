"""Independent per-course orchestration for assignment synchronization."""

import logging
from collections.abc import Callable, Collection
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.assignments.models import AssignmentSnapshot, AssignmentSyncFailure, AssignmentSyncSummary
from app.database.assignment_repository import AssignmentRepository
from app.database.course_repository import CourseRepository
from app.services.sync_errors import safe_sync_failure_message

logger = logging.getLogger(__name__)


class AssignmentSource(Protocol):
    async def fetch_course_assignments(
        self,
        canvas_course_id: str,
    ) -> list[AssignmentSnapshot]: ...


class AssignmentSyncService:
    """Sync every active local course, committing each successful course independently."""

    def __init__(
        self,
        *,
        source: AssignmentSource,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> AssignmentSyncSummary:
        courses = CourseRepository(self._session).list_syncable(
            canvas_course_ids=canvas_course_ids
        )
        received = created = updated = unchanged = succeeded = 0
        failures: list[AssignmentSyncFailure] = []

        for course in courses:
            try:
                snapshots = await self._source.fetch_course_assignments(course.canvas_course_id)
                counts = AssignmentRepository(self._session).synchronize_course(
                    course,
                    snapshots,
                    synced_at=self._clock(),
                )
                self._session.commit()
            except Exception as exc:
                self._session.rollback()
                failure = _safe_failure(course.canvas_course_id, exc)
                failures.append(failure)
                logger.warning(
                    "Assignment synchronization failed for one course",
                    extra={
                        "operation": "assignments.sync.course",
                        "course": course.canvas_course_id,
                        "status": "failed",
                        "error": failure.error_type,
                    },
                )
                continue

            succeeded += 1
            received += counts.assignments_received
            created += counts.assignments_created
            updated += counts.assignments_updated
            unchanged += counts.assignments_unchanged
            logger.info(
                "Assignment synchronization completed for one course",
                extra={
                    "operation": "assignments.sync.course",
                    "course": course.canvas_course_id,
                    "status": "ok",
                    **counts.model_dump(),
                },
            )

        return AssignmentSyncSummary(
            courses_attempted=len(courses),
            courses_succeeded=succeeded,
            courses_failed=len(failures),
            assignments_received=received,
            assignments_created=created,
            assignments_updated=updated,
            assignments_unchanged=unchanged,
            failures=tuple(failures),
        )


def _safe_failure(canvas_course_id: str, exc: Exception) -> AssignmentSyncFailure:
    return AssignmentSyncFailure(
        canvas_course_id=canvas_course_id,
        error_type=type(exc).__name__,
        message=safe_sync_failure_message(
            exc,
            local_message="Course assignment synchronization failed locally",
        ),
    )
