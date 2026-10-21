"""Dependency-aware orchestration of the existing validated synchronization services."""

import logging
from collections.abc import Awaitable, Callable, Collection
from datetime import UTC, datetime, timedelta
from typing import Protocol, TypeVar

from sqlalchemy.orm import Session

from app.announcements.models import AnnouncementSyncSummary
from app.assignments.models import AssignmentSyncSummary
from app.courses.models import CourseSyncSummary
from app.database.change_repository import ChangeRepository
from app.database.course_repository import CourseRepository
from app.database.sync_run_repository import SyncRunRepository
from app.documents.models import KnowledgePreparationSummary
from app.files.models import FileMetadataSyncSummary
from app.modules.models import ModuleSyncSummary
from app.syllabus.models import SyllabusSyncSummary
from app.sync.context import reset_sync_run_id, set_sync_run_id
from app.sync.models import SyncRunError, SyncRunResult, SyncStageResult

logger = logging.getLogger(__name__)
T = TypeVar("T")


class CourseSyncOperation(Protocol):
    async def synchronize(self) -> CourseSyncSummary: ...


class AssignmentSyncOperation(Protocol):
    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> AssignmentSyncSummary: ...


class ModuleSyncOperation(Protocol):
    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> ModuleSyncSummary: ...


class FileMetadataSyncOperation(Protocol):
    async def synchronize(
        self,
        *,
        canvas_course_id: str | None = None,
        canvas_course_ids: Collection[str] | None = None,
    ) -> FileMetadataSyncSummary: ...


class AnnouncementSyncOperation(Protocol):
    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> AnnouncementSyncSummary: ...


class SyllabusSyncOperation(Protocol):
    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> SyllabusSyncSummary: ...


class IntegrityOperation(Protocol):
    def check(
        self,
        *,
        canvas_file_id: str | None = None,
        canvas_course_ids: Collection[str] | None = None,
    ) -> dict[str, int]: ...


class KnowledgePreparationOperation(Protocol):
    async def prepare_courses(
        self,
        canvas_course_ids: Collection[str],
        *,
        max_new_download_files: int,
        max_new_download_bytes: int,
    ) -> KnowledgePreparationSummary: ...


class UnifiedSyncService:
    """Run one deterministic, non-downloading Canvas observation pipeline."""

    def __init__(
        self,
        *,
        session: Session,
        courses: CourseSyncOperation,
        assignments: AssignmentSyncOperation,
        modules: ModuleSyncOperation,
        files: FileMetadataSyncOperation,
        integrity: IntegrityOperation,
        announcements: AnnouncementSyncOperation | None = None,
        syllabus: SyllabusSyncOperation | None = None,
        knowledge: KnowledgePreparationOperation | None = None,
        knowledge_max_download_files: int = 0,
        knowledge_max_download_bytes: int = 0,
        stale_after: timedelta = timedelta(minutes=30),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._courses = courses
        self._assignments = assignments
        self._modules = modules
        self._files = files
        self._integrity = integrity
        self._announcements = announcements
        self._syllabus = syllabus
        self._knowledge = knowledge
        self._knowledge_max_download_files = knowledge_max_download_files
        self._knowledge_max_download_bytes = knowledge_max_download_bytes
        self._stale_after = stale_after
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run_sync(
        self,
        *,
        course_ids: Collection[str] | None = None,
        check_local_files: bool = False,
        trigger: str = "cli",
    ) -> SyncRunResult:
        scope = sorted(set(course_ids or ()))
        started_at = self._now()
        repository = SyncRunRepository(self._session)
        run = repository.begin(
            started_at=started_at,
            trigger=trigger,
            course_ids=scope,
            check_local_files=check_local_files,
            stale_after=self._stale_after,
        )
        logger.info(
            "Unified Canvas synchronization started",
            extra={"operation": "sync.run", "entity": run.id, "status": "running"},
        )
        token = set_sync_run_id(run.id)
        stages: dict[str, SyncStageResult] = {}
        errors: list[SyncRunError] = []
        try:
            selected = await self._course_stage(scope, stages, errors)
            if selected is None:
                self._skip(stages, "assignments", "course prerequisite failed")
                self._skip(stages, "modules", "course prerequisite failed")
                self._skip(stages, "files", "module prerequisite was not attempted")
                self._skip(
                    stages,
                    "integrity",
                    "course prerequisite failed" if check_local_files else "not requested",
                )
            else:
                await self._assignment_stage(selected, stages, errors)
                if self._announcements is not None:
                    await self._announcement_stage(selected, stages, errors)
                if self._syllabus is not None:
                    await self._syllabus_stage(selected, stages, errors)
                successful_modules = await self._module_stage(selected, stages, errors)
                await self._file_stage(successful_modules, stages, errors)
                if self._knowledge is not None and stages["files"].status != "failed":
                    await self._knowledge_stage(successful_modules, stages, errors)
                else:
                    self._skip(stages, "knowledge", "not configured or file metadata failed")
                if check_local_files:
                    self._integrity_stage(selected, stages, errors)
                else:
                    self._skip(stages, "integrity", "not requested")
            repository.heartbeat(run, at=self._now())
            changes = ChangeRepository(self._session).summary_for_run(run.id)
            event_count = len(ChangeRepository(self._session).list_for_run(run.id))
            finished_at = self._now()
            result = SyncRunResult(
                run_id=run.id,
                status=_overall_status(stages),
                trigger=trigger,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=max(0.0, (finished_at - started_at).total_seconds()),
                scope_course_ids=scope,
                check_local_files=check_local_files,
                stages=stages,
                change_events_created=event_count,
                changes=changes.model_dump(),
                errors=errors[:100],
            )
            repository.finish(run, result)
        finally:
            reset_sync_run_id(token)
        logger.info(
            "Unified Canvas synchronization completed",
            extra={
                "operation": "sync.run",
                "entity": run.id,
                "status": result.status,
                "duration_ms": round((result.duration_seconds or 0.0) * 1000, 2),
                "error_count": len(result.errors),
                "change_events": result.change_events_created,
            },
        )
        return result

    async def _course_stage(
        self,
        scope: list[str],
        stages: dict[str, SyncStageResult],
        errors: list[SyncRunError],
    ) -> set[str] | None:
        if scope:
            known = {
                course.canvas_course_id
                for course in CourseRepository(self._session).list_syncable(canvas_course_ids=scope)
            }
            missing = sorted(set(scope) - known)
            if missing:
                stages["courses"] = SyncStageResult(
                    status="failed",
                    counts={
                        "requested": len(scope),
                        "eligible": len(known),
                        "failed": len(missing),
                    },
                    reason="one or more requested Canvas course IDs are not active locally",
                )
                errors.extend(
                    SyncRunError(
                        stage="courses",
                        course_id=course_id,
                        error_type="UnknownCourse",
                        message="Requested Canvas course ID is not an active local course",
                    )
                    for course_id in missing
                )
                return None
            stages["courses"] = SyncStageResult(
                status="skipped",
                counts={"requested": len(scope), "eligible": len(known)},
                reason="scoped run uses already persisted active courses",
            )
            return known
        try:
            summary = await self._run_stage("courses", self._courses.synchronize)
        except Exception as exc:
            stages["courses"] = SyncStageResult(status="failed", counts={"failed": 1})
            errors.append(_safe_error("courses", exc))
            return None
        stages["courses"] = SyncStageResult(status="succeeded", counts=summary.model_dump())
        return {
            course.canvas_course_id for course in CourseRepository(self._session).list_syncable()
        }

    async def _assignment_stage(
        self,
        selected: set[str],
        stages: dict[str, SyncStageResult],
        errors: list[SyncRunError],
    ) -> None:
        try:
            summary = await self._run_stage(
                "assignments",
                lambda: self._assignments.synchronize(canvas_course_ids=selected),
            )
        except Exception as exc:
            stages["assignments"] = SyncStageResult(status="failed", counts={"failed": 1})
            errors.append(_safe_error("assignments", exc))
            return
        status = _failure_status(summary.courses_succeeded, summary.courses_failed)
        stages["assignments"] = SyncStageResult(
            status=status, counts=summary.model_dump(exclude={"failures"})
        )
        errors.extend(
            _reported_error("assignments", failure.error_type, failure.canvas_course_id)
            for failure in summary.failures
        )

    async def _announcement_stage(
        self,
        selected: set[str],
        stages: dict[str, SyncStageResult],
        errors: list[SyncRunError],
    ) -> None:
        announcements = self._announcements
        if announcements is None:
            return
        try:
            summary = await self._run_stage(
                "announcements",
                lambda: announcements.synchronize(canvas_course_ids=selected),
            )
        except Exception as exc:
            stages["announcements"] = SyncStageResult(status="failed", counts={"failed": 1})
            errors.append(_safe_error("announcements", exc))
            return
        status = _failure_status(summary.courses_succeeded, summary.courses_failed)
        stages["announcements"] = SyncStageResult(
            status=status, counts=summary.model_dump(exclude={"failures"})
        )
        errors.extend(
            _reported_error("announcements", failure.error_type, failure.canvas_course_id)
            for failure in summary.failures
        )

    async def _syllabus_stage(
        self,
        selected: set[str],
        stages: dict[str, SyncStageResult],
        errors: list[SyncRunError],
    ) -> None:
        syllabus = self._syllabus
        if syllabus is None:
            return
        try:
            summary = await self._run_stage(
                "syllabus",
                lambda: syllabus.synchronize(canvas_course_ids=selected),
            )
        except Exception as exc:
            stages["syllabus"] = SyncStageResult(status="failed", counts={"failed": 1})
            errors.append(_safe_error("syllabus", exc))
            return
        status = _failure_status(summary.courses_succeeded, summary.courses_failed)
        stages["syllabus"] = SyncStageResult(
            status=status, counts=summary.model_dump(exclude={"failures"})
        )
        errors.extend(
            _reported_error("syllabus", failure.error_type, failure.canvas_course_id)
            for failure in summary.failures
        )

    async def _module_stage(
        self,
        selected: set[str],
        stages: dict[str, SyncStageResult],
        errors: list[SyncRunError],
    ) -> set[str]:
        try:
            summary = await self._run_stage(
                "modules", lambda: self._modules.synchronize(canvas_course_ids=selected)
            )
        except Exception as exc:
            stages["modules"] = SyncStageResult(status="failed", counts={"failed": 1})
            errors.append(_safe_error("modules", exc))
            return set()
        status = _failure_status(summary.courses_succeeded, summary.courses_failed)
        stages["modules"] = SyncStageResult(
            status=status, counts=summary.model_dump(exclude={"failures"})
        )
        errors.extend(
            _reported_error("modules", failure.error_type, failure.canvas_course_id)
            for failure in summary.failures
        )
        failed = {failure.canvas_course_id for failure in summary.failures}
        return selected - failed

    async def _file_stage(
        self,
        selected: set[str],
        stages: dict[str, SyncStageResult],
        errors: list[SyncRunError],
    ) -> None:
        if not selected:
            self._skip(stages, "files", "no course completed the module prerequisite")
            return
        try:
            summary = await self._run_stage(
                "files", lambda: self._files.synchronize(canvas_course_ids=selected)
            )
        except Exception as exc:
            stages["files"] = SyncStageResult(status="failed", counts={"failed": 1})
            errors.append(_safe_error("files", exc))
            return
        succeeded = summary.metadata_succeeded
        status = _failure_status(succeeded, summary.metadata_failed)
        stages["files"] = SyncStageResult(
            status=status, counts=summary.model_dump(exclude={"failures"})
        )
        errors.extend(
            _reported_error("files", failure.error_type)
            for failure in summary.failures
        )

    def _integrity_stage(
        self,
        selected: set[str],
        stages: dict[str, SyncStageResult],
        errors: list[SyncRunError],
    ) -> None:
        try:
            counts = self._integrity.check(canvas_course_ids=selected)
            stages["integrity"] = SyncStageResult(status="succeeded", counts=counts)
        except Exception as exc:
            stages["integrity"] = SyncStageResult(status="failed", counts={"failed": 1})
            errors.append(_safe_error("integrity", exc))

    async def _knowledge_stage(
        self,
        selected: set[str],
        stages: dict[str, SyncStageResult],
        errors: list[SyncRunError],
    ) -> None:
        knowledge = self._knowledge
        if knowledge is None or not selected:
            self._skip(stages, "knowledge", "no eligible courses")
            return
        try:
            summary = await self._run_stage(
                "knowledge",
                lambda: knowledge.prepare_courses(
                    sorted(selected),
                    max_new_download_files=self._knowledge_max_download_files,
                    max_new_download_bytes=self._knowledge_max_download_bytes,
                ),
            )
        except Exception as exc:
            stages["knowledge"] = SyncStageResult(status="failed", counts={"failed": 1})
            errors.append(_safe_error("knowledge", exc))
            return
        status = "partially_succeeded" if summary.files_failed else "succeeded"
        stages["knowledge"] = SyncStageResult(status=status, counts=summary.model_dump())

    async def _run_stage(self, name: str, operation: Callable[[], Awaitable[T]]) -> T:
        logger.info(
            "Unified synchronization stage started",
            extra={"operation": "sync.stage", "entity": name, "status": "running"},
        )
        try:
            result = await operation()
        except Exception:
            logger.warning(
                "Unified synchronization stage failed",
                extra={"operation": "sync.stage", "entity": name, "status": "failed"},
            )
            raise
        logger.info(
            "Unified synchronization stage completed",
            extra={"operation": "sync.stage", "entity": name, "status": "ok"},
        )
        return result

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sync orchestrator clock must return timezone-aware datetimes")
        return value.astimezone(UTC)

    @staticmethod
    def _skip(stages: dict[str, SyncStageResult], name: str, reason: str) -> None:
        stages[name] = SyncStageResult(status="skipped", reason=reason)


def _failure_status(succeeded: int, failed: int) -> str:
    if failed == 0:
        return "succeeded"
    return "partially_succeeded" if succeeded else "failed"


def _overall_status(stages: dict[str, SyncStageResult]) -> str:
    statuses = [stage.status for stage in stages.values()]
    has_problem = any(status in {"failed", "partially_succeeded"} for status in statuses)
    if not has_problem:
        return "succeeded"
    has_success = any(status in {"succeeded", "partially_succeeded"} for status in statuses)
    return "partially_succeeded" if has_success else "failed"


def _safe_error(stage: str, exc: Exception) -> SyncRunError:
    return SyncRunError(
        stage=stage,
        error_type=type(exc).__name__,
        message=f"{stage.capitalize()} synchronization failed safely",
    )


def _reported_error(
    stage: str, error_type: str, course_id: str | None = None
) -> SyncRunError:
    """Convert already-sanitized service failures into a bounded generic record.

    The orchestrator deliberately does not trust or persist downstream message
    text.  That keeps request URLs, signed query strings, and hostile response
    fragments out of durable run history even if a future service regresses.
    """

    return SyncRunError(
        stage=stage,
        course_id=course_id,
        error_type=error_type[:100],
        message=f"{stage.capitalize()} synchronization failed safely",
    )
