"""Transactional orchestration for course synchronization."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.courses.models import CourseSnapshot, CourseSyncSummary
from app.database.course_repository import CourseRepository

logger = logging.getLogger(__name__)


class CourseSource(Protocol):
    """Provider boundary used by the deterministic synchronization service."""

    async def fetch_current_courses(self) -> list[CourseSnapshot]: ...


class CourseSyncService:
    """Fetch all course snapshots, then persist them in one transaction."""

    def __init__(
        self,
        *,
        source: CourseSource,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    async def synchronize(self) -> CourseSyncSummary:
        snapshots = await self._source.fetch_current_courses()
        repository = CourseRepository(self._session)
        try:
            summary = repository.synchronize(snapshots, synced_at=self._clock())
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info(
            "Course synchronization completed",
            extra={
                "operation": "courses.sync",
                "status": "ok",
                **summary.model_dump(),
            },
        )
        return summary
