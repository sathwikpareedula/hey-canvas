"""Per-course Canvas syllabus synchronization."""

import logging
from collections.abc import Callable, Collection
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.canvas.exceptions import CanvasError
from app.database.course_repository import CourseRepository
from app.database.syllabus_repository import SyllabusRepository
from app.syllabus.models import SyllabusSnapshot, SyllabusSyncFailure, SyllabusSyncSummary

logger = logging.getLogger(__name__)


class SyllabusSource(Protocol):
    async def fetch_course_syllabus(self, canvas_course_id: str) -> SyllabusSnapshot | None: ...


class SyllabusSyncService:
    def __init__(
        self,
        *,
        source: SyllabusSource,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> SyllabusSyncSummary:
        courses = CourseRepository(self._session).list_syncable(
            canvas_course_ids=canvas_course_ids
        )
        received = created = updated = unchanged = succeeded = 0
        failures: list[SyllabusSyncFailure] = []
        for course in courses:
            try:
                snapshot = await self._source.fetch_course_syllabus(course.canvas_course_id)
                was_created, was_updated = SyllabusRepository(self._session).synchronize_course(
                    course,
                    snapshot,
                    synced_at=self._clock(),
                )
                self._session.commit()
            except Exception as exc:
                self._session.rollback()
                failures.append(_safe_failure(course.canvas_course_id, exc))
                continue
            succeeded += 1
            received += 1
            if was_created:
                created += 1
            elif was_updated:
                updated += 1
            else:
                unchanged += 1
        return SyllabusSyncSummary(
            courses_attempted=len(courses),
            courses_succeeded=succeeded,
            courses_failed=len(failures),
            syllabi_received=received,
            syllabi_created=created,
            syllabi_updated=updated,
            syllabi_unchanged=unchanged,
            failures=tuple(failures),
        )


def _safe_failure(canvas_course_id: str, exc: Exception) -> SyllabusSyncFailure:
    if isinstance(exc, CanvasError):
        return SyllabusSyncFailure(
            canvas_course_id=canvas_course_id,
            error_type=type(exc).__name__,
            message="Syllabus synchronization failed safely",
        )
    return SyllabusSyncFailure(
        canvas_course_id=canvas_course_id,
        error_type=type(exc).__name__,
        message="Syllabus synchronization failed safely",
    )
