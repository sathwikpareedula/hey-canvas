"""Independent per-course orchestration for coherent module synchronization."""

import logging
from collections.abc import Callable, Collection
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.database.course_repository import CourseRepository
from app.database.module_repository import ModuleRepository
from app.modules.models import ModuleSnapshot, ModuleSyncFailure, ModuleSyncSummary
from app.services.sync_errors import safe_sync_failure_message

logger = logging.getLogger(__name__)


class ModuleSource(Protocol):
    async def fetch_course_modules(self, canvas_course_id: str) -> list[ModuleSnapshot]: ...


class ModuleSyncService:
    """Sync complete course structures with independent course transactions."""

    def __init__(
        self,
        *,
        source: ModuleSource,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> ModuleSyncSummary:
        courses = CourseRepository(self._session).list_syncable(
            canvas_course_ids=canvas_course_ids
        )
        succeeded = 0
        module_received = module_created = module_updated = module_unchanged = 0
        item_received = item_created = item_updated = item_unchanged = 0
        failures: list[ModuleSyncFailure] = []

        for course in courses:
            try:
                snapshots = await self._source.fetch_course_modules(course.canvas_course_id)
                counts = ModuleRepository(self._session).synchronize_course(
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
                    "Module synchronization failed for one course",
                    extra={
                        "operation": "modules.sync.course",
                        "course": course.canvas_course_id,
                        "status": "failed",
                        "error": failure.error_type,
                    },
                )
                continue

            succeeded += 1
            module_received += counts.modules_received
            module_created += counts.modules_created
            module_updated += counts.modules_updated
            module_unchanged += counts.modules_unchanged
            item_received += counts.items_received
            item_created += counts.items_created
            item_updated += counts.items_updated
            item_unchanged += counts.items_unchanged
            logger.info(
                "Module synchronization completed for one course",
                extra={
                    "operation": "modules.sync.course",
                    "course": course.canvas_course_id,
                    "status": "ok",
                    **counts.model_dump(),
                },
            )

        return ModuleSyncSummary(
            courses_attempted=len(courses),
            courses_succeeded=succeeded,
            courses_failed=len(failures),
            modules_received=module_received,
            modules_created=module_created,
            modules_updated=module_updated,
            modules_unchanged=module_unchanged,
            items_received=item_received,
            items_created=item_created,
            items_updated=item_updated,
            items_unchanged=item_unchanged,
            failures=tuple(failures),
        )


def _safe_failure(canvas_course_id: str, exc: Exception) -> ModuleSyncFailure:
    return ModuleSyncFailure(
        canvas_course_id=canvas_course_id,
        error_type=type(exc).__name__,
        message=safe_sync_failure_message(
            exc,
            local_message="Course module synchronization failed locally",
        ),
    )
