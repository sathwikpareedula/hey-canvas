"""Per-course Canvas announcement synchronization."""

import logging
from collections.abc import Callable, Collection
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.announcements.models import (
    AnnouncementSnapshot,
    AnnouncementSyncFailure,
    AnnouncementSyncSummary,
)
from app.canvas.exceptions import CanvasError
from app.database.announcement_repository import AnnouncementRepository
from app.database.course_repository import CourseRepository

logger = logging.getLogger(__name__)


class AnnouncementSource(Protocol):
    async def fetch_course_announcements(
        self, canvas_course_id: str
    ) -> list[AnnouncementSnapshot]: ...


class AnnouncementSyncService:
    def __init__(
        self,
        *,
        source: AnnouncementSource,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> AnnouncementSyncSummary:
        courses = CourseRepository(self._session).list_syncable(
            canvas_course_ids=canvas_course_ids
        )
        received = created = updated = unchanged = succeeded = 0
        failures: list[AnnouncementSyncFailure] = []
        for course in courses:
            try:
                snapshots = await self._source.fetch_course_announcements(
                    course.canvas_course_id
                )
                counts = AnnouncementRepository(self._session).synchronize_course(
                    course,
                    snapshots,
                    synced_at=self._clock(),
                )
                self._session.commit()
            except Exception as exc:
                self._session.rollback()
                failures.append(_safe_failure(course.canvas_course_id, exc))
                continue
            succeeded += 1
            received += counts.announcements_received
            created += counts.announcements_created
            updated += counts.announcements_updated
            unchanged += counts.announcements_unchanged
        return AnnouncementSyncSummary(
            courses_attempted=len(courses),
            courses_succeeded=succeeded,
            courses_failed=len(failures),
            announcements_received=received,
            announcements_created=created,
            announcements_updated=updated,
            announcements_unchanged=unchanged,
            failures=tuple(failures),
        )


def _safe_failure(canvas_course_id: str, exc: Exception) -> AnnouncementSyncFailure:
    if isinstance(exc, CanvasError):
        return AnnouncementSyncFailure(
            canvas_course_id=canvas_course_id,
            error_type=type(exc).__name__,
            message="Announcement synchronization failed safely",
        )
    return AnnouncementSyncFailure(
        canvas_course_id=canvas_course_id,
        error_type=type(exc).__name__,
        message="Announcement synchronization failed safely",
    )
