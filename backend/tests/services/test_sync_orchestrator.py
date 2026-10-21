from __future__ import annotations

import json
from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.assignments.models import AssignmentSyncFailure, AssignmentSyncSummary
from app.canvas.client import CanvasClient
from app.changes.models import ChangeSummary
from app.config import Settings
from app.courses.models import CourseSnapshot, CourseSyncSummary
from app.database.change_repository import ChangeRecorder, ChangeRepository
from app.database.course_repository import CourseRepository
from app.database.models import ChangeEvent, SyncRun, SyncRunChangeEvent
from app.database.session import get_session
from app.database.sync_run_repository import SyncAlreadyRunningError, SyncRunRepository
from app.documents.models import KnowledgePreparationSummary
from app.files.downloader import ControlledFileDownloader
from app.files.models import FileMetadataSyncSummary, FileSyncFailure
from app.main import app
from app.modules.models import ModuleSyncFailure, ModuleSyncSummary
from app.services.document_ingestion import DocumentIngestionService
from app.services.sync_orchestrator import UnifiedSyncService
from app.sync.models import SyncRunResult, SyncStageResult
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.api.test_files import override_factory

NOW = datetime(2026, 9, 29, 18, 0, tzinfo=UTC)


def add_course(session: Session, course_id: str) -> None:
    CourseRepository(session).synchronize(
        [
            CourseSnapshot(
                canvas_course_id=course_id,
                course_name=f"Course {course_id}",
                workflow_state="available",
                enrollment_state="active",
            )
        ],
        synced_at=NOW,
    )
    session.commit()


class FakeCourses:
    def __init__(
        self,
        session: Session,
        *,
        course_ids: tuple[str, ...] = ("101", "102"),
        error: Exception | None = None,
        order: list[str] | None = None,
    ) -> None:
        self.session = session
        self.course_ids = course_ids
        self.error = error
        self.calls = 0
        self.order = order

    async def synchronize(self) -> CourseSyncSummary:
        self.calls += 1
        if self.order is not None:
            self.order.append("courses")
        if self.error is not None:
            raise self.error
        for course_id in self.course_ids:
            if not CourseRepository(self.session).list_syncable(canvas_course_ids=[course_id]):
                add_course(self.session, course_id)
        return CourseSyncSummary(
            courses_received=len(self.course_ids),
            courses_created=0,
            courses_updated=0,
            courses_unchanged=len(self.course_ids),
        )


class FakeAssignments:
    def __init__(
        self,
        *,
        session: Session | None = None,
        failures: tuple[AssignmentSyncFailure, ...] = (),
        error: Exception | None = None,
        event: tuple[str, str | None] | None = None,
        order: list[str] | None = None,
    ) -> None:
        self.session = session
        self.failures = failures
        self.error = error
        self.event = event
        self.calls: list[set[str] | None] = []
        self.order = order

    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> AssignmentSyncSummary:
        selected = set(canvas_course_ids) if canvas_course_ids is not None else None
        self.calls.append(selected)
        if self.order is not None:
            self.order.append("assignments")
        if self.error is not None:
            raise self.error
        if self.event is not None and self.session is not None:
            field, old = self.event
            recorder = ChangeRecorder(self.session, observed_at=NOW, source="canvas_sync")
            if field == "new_assignment":
                recorder.created("assignment", "501", "101")
            else:
                recorder.changed(
                    entity_type="assignment",
                    external_id="501",
                    course_id="101",
                    field_name=field,
                    old_value=old,
                    new_value="2026-10-03T23:59:00Z",
                )
            self.session.commit()
        attempted = len(selected or {"101", "102"})
        failed = len(self.failures)
        return AssignmentSyncSummary(
            courses_attempted=attempted,
            courses_succeeded=attempted - failed,
            courses_failed=failed,
            assignments_received=1,
            assignments_created=int(self.event is not None and self.event[0] == "new_assignment"),
            assignments_updated=int(self.event is not None and self.event[0] != "new_assignment"),
            assignments_unchanged=int(self.event is None),
            failures=self.failures,
        )


class FakeModules:
    def __init__(
        self,
        *,
        session: Session | None = None,
        failures: tuple[ModuleSyncFailure, ...] = (),
        error: Exception | None = None,
        make_event: bool = False,
        order: list[str] | None = None,
    ) -> None:
        self.session = session
        self.failures = failures
        self.error = error
        self.make_event = make_event
        self.calls: list[set[str] | None] = []
        self.order = order

    async def synchronize(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> ModuleSyncSummary:
        selected = set(canvas_course_ids) if canvas_course_ids is not None else None
        self.calls.append(selected)
        if self.order is not None:
            self.order.append("modules")
        if self.error is not None:
            raise self.error
        if self.make_event and self.session is not None:
            ChangeRecorder(self.session, observed_at=NOW, source="canvas_sync").changed(
                entity_type="module_item",
                external_id="1001",
                course_id="101",
                field_name="position",
                old_value=1,
                new_value=2,
            )
            self.session.commit()
        attempted = len(selected or {"101", "102"})
        failed = len(self.failures)
        return ModuleSyncSummary(
            courses_attempted=attempted,
            courses_succeeded=attempted - failed,
            courses_failed=failed,
            modules_received=2,
            modules_created=0,
            modules_updated=0,
            modules_unchanged=2,
            items_received=3,
            items_created=0,
            items_updated=int(self.make_event),
            items_unchanged=3 - int(self.make_event),
            failures=self.failures,
        )


class FakeFiles:
    def __init__(
        self,
        *,
        session: Session | None = None,
        failures: tuple[FileSyncFailure, ...] = (),
        error: Exception | None = None,
        make_event: bool = False,
        order: list[str] | None = None,
    ) -> None:
        self.session = session
        self.failures = failures
        self.error = error
        self.make_event = make_event
        self.calls: list[set[str] | None] = []
        self.order = order

    async def synchronize(
        self,
        *,
        canvas_course_id: str | None = None,
        canvas_course_ids: Collection[str] | None = None,
    ) -> FileMetadataSyncSummary:
        assert canvas_course_id is None
        selected = set(canvas_course_ids) if canvas_course_ids is not None else None
        self.calls.append(selected)
        if self.order is not None:
            self.order.append("files")
        if self.error is not None:
            raise self.error
        if self.make_event and self.session is not None:
            ChangeRecorder(self.session, observed_at=NOW, source="canvas_file_metadata").changed(
                entity_type="file",
                external_id="7001",
                course_id="101",
                field_name="size",
                old_value=1,
                new_value=2,
            )
            self.session.commit()
        failed = len(self.failures)
        return FileMetadataSyncSummary(
            references_seen=2,
            unique_file_ids=2,
            metadata_succeeded=2 - failed,
            metadata_failed=failed,
            files_created=0,
            files_updated=int(self.make_event),
            files_unchanged=2 - failed - int(self.make_event),
            failures=self.failures,
        )


class FakeIntegrity:
    def __init__(self, *, missing: int = 0, error: Exception | None = None) -> None:
        self.missing = missing
        self.error = error
        self.calls: list[set[str] | None] = []

    def check(
        self,
        *,
        canvas_file_id: str | None = None,
        canvas_course_ids: Collection[str] | None = None,
    ) -> dict[str, int]:
        assert canvas_file_id is None
        self.calls.append(set(canvas_course_ids) if canvas_course_ids is not None else None)
        if self.error is not None:
            raise self.error
        return {"checked": 3, "healthy": 3 - self.missing, "missing": self.missing, "corrupt": 0}


class FakeKnowledge:
    def __init__(self, *, failed: int = 0) -> None:
        self.failed = failed
        self.calls: list[tuple[tuple[str, ...], int, int]] = []

    async def prepare_courses(
        self,
        canvas_course_ids: Collection[str],
        *,
        max_new_download_files: int,
        max_new_download_bytes: int,
    ) -> KnowledgePreparationSummary:
        self.calls.append(
            (
                tuple(canvas_course_ids),
                max_new_download_files,
                max_new_download_bytes,
            )
        )
        return KnowledgePreparationSummary(
            courses_selected=len(canvas_course_ids),
            files_considered=4,
            files_prepared=2,
            files_unchanged=1,
            files_deferred=1,
            files_failed=self.failed,
            files_needing_ocr=0,
            files_unsupported=0,
            files_downloaded=2,
            downloaded_bytes=20,
        )


def service(
    session: Session,
    *,
    courses: FakeCourses | None = None,
    assignments: FakeAssignments | None = None,
    modules: FakeModules | None = None,
    files: FakeFiles | None = None,
    integrity: FakeIntegrity | None = None,
    clock: Any = None,
) -> tuple[UnifiedSyncService, FakeCourses, FakeAssignments, FakeModules, FakeFiles, FakeIntegrity]:
    # A unified run observes an already-established Phase 0-6 baseline. Seed the
    # fake current courses before the run context is active so an unchanged
    # course refresh does not manufacture entity-created events.
    for course_id in ("101", "102"):
        if not CourseRepository(session).list_syncable(canvas_course_ids=[course_id]):
            add_course(session, course_id)
    course_op = courses or FakeCourses(session)
    assignment_op = assignments or FakeAssignments(session=session)
    module_op = modules or FakeModules(session=session)
    file_op = files or FakeFiles(session=session)
    integrity_op = integrity or FakeIntegrity()
    return (
        UnifiedSyncService(
            session=session,
            courses=course_op,
            assignments=assignment_op,
            modules=module_op,
            files=file_op,
            integrity=integrity_op,
            clock=clock or (lambda: NOW),
        ),
        course_op,
        assignment_op,
        module_op,
        file_op,
        integrity_op,
    )


@pytest.mark.asyncio
async def test_successful_run_lifecycle_persists_aware_timestamps(session: Session) -> None:
    orchestrator, *_ = service(session)
    result = await orchestrator.run_sync()
    stored = session.get(SyncRun, result.run_id)
    assert result.status == "succeeded"
    assert result.started_at.tzinfo is not None and result.finished_at is not None
    assert result.finished_at.tzinfo is not None
    assert result.duration_seconds == 0.0
    assert stored is not None and stored.status == "succeeded"
    assert stored.active_lock_key is None


@pytest.mark.asyncio
async def test_successful_metadata_sync_runs_bounded_persisted_knowledge_stage(
    session: Session,
) -> None:
    for course_id in ("101", "102"):
        add_course(session, course_id)
    knowledge = FakeKnowledge()
    orchestrator = UnifiedSyncService(
        session=session,
        courses=FakeCourses(session),
        assignments=FakeAssignments(session=session),
        modules=FakeModules(session=session),
        files=FakeFiles(session=session),
        integrity=FakeIntegrity(),
        knowledge=knowledge,
        knowledge_max_download_files=3,
        knowledge_max_download_bytes=99,
        clock=lambda: NOW,
    )

    result = await orchestrator.run_sync()
    stored = session.get(SyncRun, result.run_id)

    assert result.stages["knowledge"].status == "succeeded"
    assert result.stages["knowledge"].counts["files_prepared"] == 2
    assert knowledge.calls == [(('101', '102'), 3, 99)]
    assert stored is not None
    assert stored.stage_results["knowledge"]["counts"]["files_deferred"] == 1


def _assignment_failure(course_id: str = "102") -> AssignmentSyncFailure:
    return AssignmentSyncFailure(
        canvas_course_id=course_id,
        error_type="CanvasTransportError",
        message="Course assignment synchronization failed safely",
    )


def _module_failure(course_id: str = "102") -> ModuleSyncFailure:
    return ModuleSyncFailure(
        canvas_course_id=course_id,
        error_type="CanvasAPIError",
        message="Course module synchronization failed safely",
    )


def _file_failure() -> FileSyncFailure:
    return FileSyncFailure(
        canvas_file_id="7002",
        error_type="CanvasTransportError",
        message="File metadata synchronization failed safely",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stage", "expected_status"),
    [
        ("assignments", "partially_succeeded"),
        ("modules", "partially_succeeded"),
        ("files", "partially_succeeded"),
    ],
)
async def test_partial_stage_makes_run_partial(
    stage: str, expected_status: str, session: Session
) -> None:
    kwargs: dict[str, Any] = {}
    if stage == "assignments":
        kwargs[stage] = FakeAssignments(failures=(_assignment_failure(),))
    elif stage == "modules":
        kwargs[stage] = FakeModules(failures=(_module_failure(),))
    else:
        kwargs[stage] = FakeFiles(failures=(_file_failure(),))
    orchestrator, *_ = service(session, **kwargs)
    result = await orchestrator.run_sync()
    assert result.status == expected_status
    assert result.stages[stage].status == expected_status
    assert len(result.errors) == 1


@pytest.mark.asyncio
async def test_course_failure_marks_run_failed_and_skips_dependents(session: Session) -> None:
    orchestrator, _, assignments, modules, files, integrity = service(
        session, courses=FakeCourses(session, error=RuntimeError("secret request body"))
    )
    result = await orchestrator.run_sync(check_local_files=True)
    assert result.status == "failed"
    assert result.stages["courses"].status == "failed"
    assert all(
        result.stages[name].status == "skipped"
        for name in ("assignments", "modules", "files", "integrity")
    )
    assert assignments.calls == modules.calls == files.calls == integrity.calls == []
    assert "secret request body" not in json.dumps(result.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_stage_order_is_dependency_aware(session: Session) -> None:
    order: list[str] = []
    orchestrator, *_ = service(
        session,
        courses=FakeCourses(session, order=order),
        assignments=FakeAssignments(order=order),
        modules=FakeModules(order=order),
        files=FakeFiles(order=order),
    )
    await orchestrator.run_sync()
    assert order == ["courses", "assignments", "modules", "files"]


@pytest.mark.asyncio
async def test_repeated_runs_create_distinct_history_without_changes(session: Session) -> None:
    orchestrator, *_ = service(session)
    first = await orchestrator.run_sync()
    second = await orchestrator.run_sync()
    assert first.run_id != second.run_id
    assert first.change_events_created == second.change_events_created == 0
    assert session.scalar(select(func.count()).select_from(SyncRun)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event", "summary_field"),
    [
        (("due_at", "2026-10-01T23:59:00Z"), "deadline_changes"),
        (("new_assignment", None), "new_assignments"),
    ],
)
async def test_assignment_changes_are_exactly_associated(
    event: tuple[str, str | None], summary_field: str, session: Session
) -> None:
    ChangeRecorder(session, observed_at=NOW - timedelta(days=1), source="prior").created(
        "assignment", "old", "101"
    )
    session.commit()
    orchestrator, *_ = service(
        session, assignments=FakeAssignments(session=session, event=event)
    )
    historical_count = session.scalar(select(func.count()).select_from(ChangeEvent)) or 0
    result = await orchestrator.run_sync()
    assert result.change_events_created == 1
    assert result.changes[summary_field] == 1
    assert len(ChangeRepository(session).list_for_run(result.run_id)) == 1
    assert session.scalar(select(func.count()).select_from(ChangeEvent)) == historical_count + 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stage", "summary_field"),
    [("modules", "module_item_changes"), ("files", "file_metadata_changes")],
)
async def test_module_and_file_changes_are_associated(
    stage: str, summary_field: str, session: Session
) -> None:
    kwargs: dict[str, Any] = {
        stage: FakeModules(session=session, make_event=True)
        if stage == "modules"
        else FakeFiles(session=session, make_event=True)
    }
    orchestrator, *_ = service(session, **kwargs)
    result = await orchestrator.run_sync()
    assert result.change_events_created == 1
    assert result.changes[summary_field] == 1


@pytest.mark.asyncio
async def test_subsequent_event_is_not_associated_with_completed_run(session: Session) -> None:
    orchestrator, *_ = service(session)
    result = await orchestrator.run_sync()
    ChangeRecorder(session, observed_at=NOW, source="later").created("assignment", "later", "101")
    session.commit()
    assert ChangeRepository(session).list_for_run(result.run_id) == []


@pytest.mark.asyncio
async def test_scoped_run_skips_global_course_refresh_and_avoids_unrelated_course(
    session: Session,
) -> None:
    for course_id in ("101", "102", "103"):
        add_course(session, course_id)
    courses = FakeCourses(session)
    orchestrator, _, assignments, modules, files, _ = service(session, courses=courses)
    result = await orchestrator.run_sync(course_ids=["102", "101", "102"])
    assert result.status == "succeeded"
    assert result.scope_course_ids == ["101", "102"]
    assert result.stages["courses"].status == "skipped"
    assert courses.calls == 0
    assert assignments.calls == modules.calls == files.calls == [{"101", "102"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("course_ids", [["999"], ["1"]])
async def test_unknown_or_internal_course_id_fails_without_downstream_calls(
    course_ids: list[str], session: Session
) -> None:
    add_course(session, "101")
    orchestrator, courses, assignments, modules, files, _ = service(session)
    result = await orchestrator.run_sync(course_ids=course_ids)
    assert result.status == "failed"
    assert courses.calls == 0
    assert assignments.calls == modules.calls == files.calls == []
    assert result.errors[0].error_type == "UnknownCourse"


@pytest.mark.asyncio
async def test_module_failure_prunes_only_failed_course_from_file_stage(session: Session) -> None:
    modules = FakeModules(failures=(_module_failure("102"),))
    orchestrator, _, _, _, files, _ = service(session, modules=modules)
    result = await orchestrator.run_sync()
    assert result.status == "partially_succeeded"
    assert files.calls == [{"101"}]


@pytest.mark.asyncio
async def test_all_module_failures_skip_file_metadata(session: Session) -> None:
    modules = FakeModules(failures=(_module_failure("101"), _module_failure("102")))
    orchestrator, _, _, _, files, _ = service(session, modules=modules)
    result = await orchestrator.run_sync()
    assert result.stages["modules"].status == "failed"
    assert result.stages["files"].status == "skipped"
    assert files.calls == []


@pytest.mark.asyncio
async def test_default_does_not_hash_and_optional_integrity_is_local(session: Session) -> None:
    integrity = FakeIntegrity(missing=1)
    orchestrator, *_ = service(session, integrity=integrity)
    first = await orchestrator.run_sync()
    second = await orchestrator.run_sync(check_local_files=True)
    assert first.stages["integrity"].status == "skipped"
    assert integrity.calls == [{"101", "102"}]
    assert second.stages["integrity"].counts["missing"] == 1


@pytest.mark.asyncio
async def test_sync_all_never_invokes_binary_downloader(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fail(*_: object, **__: object) -> object:
        raise AssertionError("unified sync must never download binary content")

    monkeypatch.setattr(ControlledFileDownloader, "download", fail)
    monkeypatch.setattr(DocumentIngestionService, "ingest_course", fail)
    orchestrator, *_ = service(session)
    result = await orchestrator.run_sync()
    assert result.status == "succeeded"


def test_overlap_is_rejected_without_duplicate_run(session: Session) -> None:
    repository = SyncRunRepository(session)
    repository.begin(
        started_at=NOW,
        trigger="test",
        course_ids=[],
        check_local_files=False,
        stale_after=timedelta(minutes=30),
    )
    with pytest.raises(SyncAlreadyRunningError):
        repository.begin(
            started_at=NOW + timedelta(minutes=1),
            trigger="test",
            course_ids=[],
            check_local_files=False,
            stale_after=timedelta(minutes=30),
        )
    assert session.scalar(select(func.count()).select_from(SyncRun)) == 1


def test_stale_run_is_interrupted_before_new_run(session: Session) -> None:
    repository = SyncRunRepository(session)
    old = repository.begin(
        started_at=NOW,
        trigger="test",
        course_ids=[],
        check_local_files=False,
        stale_after=timedelta(minutes=30),
    )
    new = repository.begin(
        started_at=NOW + timedelta(minutes=31),
        trigger="test",
        course_ids=[],
        check_local_files=False,
        stale_after=timedelta(minutes=30),
    )
    session.refresh(old)
    assert old.status == "interrupted"
    assert old.finished_at == NOW + timedelta(minutes=31)
    assert old.active_lock_key is None
    assert new.status == "running"


def test_fresh_heartbeat_prevents_false_stale_recovery(session: Session) -> None:
    repository = SyncRunRepository(session)
    run = repository.begin(
        started_at=NOW,
        trigger="test",
        course_ids=[],
        check_local_files=False,
        stale_after=timedelta(minutes=30),
    )
    repository.heartbeat(run, at=NOW + timedelta(minutes=20))
    with pytest.raises(SyncAlreadyRunningError):
        repository.begin(
            started_at=NOW + timedelta(minutes=31),
            trigger="test",
            course_ids=[],
            check_local_files=False,
            stale_after=timedelta(minutes=30),
        )
    assert run.status == "running"


@pytest.mark.parametrize("minutes", [0, 1441])
def test_stale_configuration_is_bounded(minutes: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 1440"):
        Settings(sync_run_stale_minutes=minutes)


def _completed_result(run_id: int, *, status: str = "succeeded") -> SyncRunResult:
    return SyncRunResult(
        run_id=run_id,
        status=status,
        trigger="test",
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=2),
        duration_seconds=2.0,
        scope_course_ids=[],
        check_local_files=False,
        stages={"courses": SyncStageResult(status="succeeded")},
        change_events_created=0,
        changes=ChangeSummary().model_dump(),
        errors=[],
    )


def create_completed_run(session: Session, *, started_at: datetime = NOW) -> SyncRun:
    repository = SyncRunRepository(session)
    run = repository.begin(
        started_at=started_at,
        trigger="test",
        course_ids=[],
        check_local_files=False,
        stale_after=timedelta(minutes=30),
    )
    result = _completed_result(run.id).model_copy(
        update={
            "started_at": started_at,
            "finished_at": started_at + timedelta(seconds=2),
        }
    )
    repository.finish(run, result)
    return run


@pytest.mark.parametrize("limit", [0, 201])
def test_run_query_rejects_invalid_limit(limit: int, session: Session) -> None:
    with pytest.raises(ValueError, match="between 1 and 200"):
        SyncRunRepository(session).list_runs(limit=limit)


def test_run_query_is_newest_first_and_filters_status(session: Session) -> None:
    older = create_completed_run(session, started_at=NOW)
    newer = create_completed_run(session, started_at=NOW + timedelta(minutes=1))
    results = SyncRunRepository(session).list_runs(status="succeeded")
    assert [item.id for item in results] == [newer.id, older.id]


@pytest.mark.asyncio
async def test_sync_run_api_is_local_only_and_safe(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_factory() as session:
        run = create_completed_run(session)
        run_id = run.id

    async def fail(*_: object, **__: object) -> object:
        raise AssertionError("sync history GET API must not contact Canvas")

    monkeypatch.setattr(CanvasClient, "get_json", fail)
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            listing = await client.get("/api/sync-runs", params={"status": "succeeded"})
            detail = await client.get(f"/api/sync-runs/{run_id}")
            missing = await client.get("/api/sync-runs/99999")
            invalid_limit = await client.get("/api/sync-runs", params={"limit": 0})
            invalid_status = await client.get("/api/sync-runs", params={"status": "secret"})
    finally:
        app.dependency_overrides.clear()
    assert listing.status_code == detail.status_code == 200
    assert missing.status_code == 404
    assert invalid_limit.status_code == invalid_status.status_code == 422
    payload = json.dumps(detail.json()).lower()
    assert "authorization" not in payload and "signed" not in payload and "token" not in payload


@pytest.mark.asyncio
async def test_event_association_row_commits_with_event(session: Session) -> None:
    orchestrator, *_ = service(
        session, assignments=FakeAssignments(session=session, event=("new_assignment", None))
    )
    result = await orchestrator.run_sync()
    assert session.scalar(select(func.count()).select_from(SyncRunChangeEvent)) == 1
    assert len(ChangeRepository(session).list_for_run(result.run_id)) == 1


def test_event_and_association_rollback_together(session: Session) -> None:
    from app.sync.context import reset_sync_run_id, set_sync_run_id

    run = create_completed_run(session)
    token = set_sync_run_id(run.id)
    try:
        ChangeRecorder(session, observed_at=NOW, source="test").created(
            "assignment", "rollback", "101"
        )
        session.rollback()
    finally:
        reset_sync_run_id(token)
    assert session.scalar(select(func.count()).select_from(SyncRunChangeEvent)) == 0


@pytest.mark.parametrize(
    "bad_text",
    [
        "CANVAS_" + "TOKEN=synthetic-fixture",
        "Authorization: Bearer " + "synthetic-fixture",
        "X-Amz-" + "Signature=synthetic-fixture",
    ],
)
@pytest.mark.asyncio
async def test_unexpected_errors_never_persist_or_return_sensitive_text(
    bad_text: str, session: Session
) -> None:
    orchestrator, *_ = service(
        session, assignments=FakeAssignments(error=RuntimeError(bad_text))
    )
    result = await orchestrator.run_sync()
    payload = json.dumps(result.model_dump(mode="json"))
    stored = json.dumps(session.get(SyncRun, result.run_id).errors)  # type: ignore[union-attr]
    assert bad_text not in payload
    assert bad_text not in stored


@pytest.mark.asyncio
async def test_cli_missing_credentials_fails_before_canvas(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.sync import all_cli

    async def fail(*_: object, **__: object) -> object:
        raise AssertionError("missing credentials must fail before Canvas work")

    monkeypatch.setattr(CanvasClient, "__aenter__", fail)
    settings = Settings(canvas_base_url=None, canvas_token=None)
    with pytest.raises(Exception, match="CANVAS_BASE_URL and CANVAS_TOKEN"):
        await all_cli.synchronize_all(settings, course_ids=[], check_local_files=False)
    assert "secret" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_cli_summary_is_deterministic_and_safe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    session_factory: sessionmaker[Session],
) -> None:
    from app.sync import all_cli

    fixed = _completed_result(7)

    class FakeUnified:
        def __init__(self, **_: object) -> None: pass

        async def run_sync(self, **_: object) -> SyncRunResult:
            return fixed

    class FakeClient:
        def __init__(self, **_: object) -> None: pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *_: object) -> None: return None

    monkeypatch.setattr(all_cli, "UnifiedSyncService", FakeUnified)
    monkeypatch.setattr(all_cli, "CanvasClient", FakeClient)
    monkeypatch.setattr(all_cli, "initialize_database", lambda: None)
    monkeypatch.setattr(all_cli, "get_session_factory", lambda: session_factory)
    settings = Settings(
        canvas_base_url="https://canvas.example.edu", canvas_token=SecretStr("fake-test-token")
    )
    assert await all_cli.synchronize_all(
        settings, course_ids=[], check_local_files=False
    ) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["run_id"] == 7
    assert "fake-test-token" not in output
    assert "X-Amz-Signature" not in output


@pytest.mark.parametrize(
    "status",
    ["running", "succeeded", "partially_succeeded", "failed", "interrupted"],
)
def test_status_filter_contract_accepts_all_machine_statuses(status: str) -> None:
    from app.sync.models import SyncRunView

    payload = {
        "id": 1,
        "started_at": NOW,
        "finished_at": None,
        "heartbeat_at": NOW,
        "status": status,
        "trigger": "test",
        "scope_course_ids": [],
        "check_local_files": False,
        "stage_results": {},
        "change_summary": {},
        "change_events_created": 0,
        "error_count": 0,
        "errors": [],
        "created_at": NOW,
    }
    assert SyncRunView.model_validate(payload).status == status


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


@pytest.mark.asyncio
async def test_duration_uses_aware_clock_boundaries(session: Session) -> None:
    clock = SequenceClock(NOW, NOW + timedelta(seconds=2), NOW + timedelta(seconds=5))
    orchestrator, *_ = service(session, clock=clock)
    result = await orchestrator.run_sync()
    assert result.duration_seconds == 5.0
    assert result.finished_at == NOW + timedelta(seconds=5)


@pytest.mark.asyncio
async def test_naive_orchestrator_clock_is_rejected(session: Session) -> None:
    orchestrator, *_ = service(session, clock=lambda: datetime(2026, 9, 29, 18, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        await orchestrator.run_sync()
    assert session.scalar(select(func.count()).select_from(SyncRun)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["cli", "future_agent", "manual_test"])
async def test_trigger_is_persisted_verbatim(trigger: str, session: Session) -> None:
    orchestrator, *_ = service(session)
    result = await orchestrator.run_sync(trigger=trigger)
    stored = session.get(SyncRun, result.run_id)
    assert result.trigger == trigger
    assert stored is not None and stored.trigger == trigger


@pytest.mark.asyncio
async def test_assignment_course_failure_preserves_other_stages(session: Session) -> None:
    assignments = FakeAssignments(failures=(_assignment_failure("102"),))
    orchestrator, _, _, modules, files, _ = service(session, assignments=assignments)
    result = await orchestrator.run_sync()
    assert result.stages["assignments"].status == "partially_succeeded"
    assert modules.calls == files.calls == [{"101", "102"}]
    assert result.status == "partially_succeeded"


@pytest.mark.asyncio
async def test_assignment_stage_exception_does_not_block_independent_stages(
    session: Session,
) -> None:
    assignments = FakeAssignments(error=RuntimeError("hostile body"))
    orchestrator, _, _, modules, files, _ = service(session, assignments=assignments)
    result = await orchestrator.run_sync()
    assert result.stages["assignments"].status == "failed"
    assert modules.calls == files.calls == [{"101", "102"}]
    assert result.status == "partially_succeeded"


@pytest.mark.asyncio
async def test_module_stage_exception_skips_dependent_file_stage(session: Session) -> None:
    modules = FakeModules(error=RuntimeError("unsafe URL?signature=secret"))
    orchestrator, _, _, _, files, _ = service(session, modules=modules)
    result = await orchestrator.run_sync()
    assert result.stages["modules"].status == "failed"
    assert result.stages["files"].status == "skipped"
    assert files.calls == []


@pytest.mark.asyncio
async def test_file_failure_does_not_block_requested_local_integrity(session: Session) -> None:
    files = FakeFiles(error=RuntimeError("temporary file metadata failure"))
    integrity = FakeIntegrity(missing=1)
    orchestrator, *_ = service(session, files=files, integrity=integrity)
    result = await orchestrator.run_sync(check_local_files=True)
    assert result.stages["files"].status == "failed"
    assert result.stages["integrity"].status == "succeeded"
    assert integrity.calls == [{"101", "102"}]


@pytest.mark.asyncio
async def test_integrity_failure_is_partial_and_remains_local(session: Session) -> None:
    integrity = FakeIntegrity(error=RuntimeError("C:\\private\\absolute\\path"))
    orchestrator, *_ = service(session, integrity=integrity)
    result = await orchestrator.run_sync(check_local_files=True)
    assert result.status == "partially_succeeded"
    assert result.stages["integrity"].status == "failed"
    assert "absolute" not in json.dumps(result.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_failed_run_does_not_fabricate_associated_changes(session: Session) -> None:
    orchestrator, *_ = service(session, courses=FakeCourses(session, error=TimeoutError()))
    result = await orchestrator.run_sync()
    assert result.status == "failed"
    assert result.change_events_created == 0
    assert ChangeRepository(session).list_for_run(result.run_id) == []


@pytest.mark.asyncio
async def test_retry_after_stage_failure_creates_one_new_run_without_false_changes(
    session: Session,
) -> None:
    assignments = FakeAssignments(error=TimeoutError())
    orchestrator, *_ = service(session, assignments=assignments)
    failed = await orchestrator.run_sync()
    assignments.error = None
    retried = await orchestrator.run_sync()
    assert failed.status == "partially_succeeded"
    assert retried.status == "succeeded"
    assert failed.run_id != retried.run_id
    assert failed.change_events_created == retried.change_events_created == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("course_id", ["101", "102"])
async def test_single_course_scope_uses_canvas_external_id(
    course_id: str, session: Session
) -> None:
    orchestrator, courses, assignments, modules, files, _ = service(session)
    result = await orchestrator.run_sync(course_ids=[course_id])
    assert result.scope_course_ids == [course_id]
    assert courses.calls == 0
    assert assignments.calls == modules.calls == files.calls == [{course_id}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stage", "count_name", "expected"),
    [
        ("courses", "courses_received", 2),
        ("assignments", "assignments_received", 1),
        ("modules", "modules_received", 2),
        ("modules", "items_received", 3),
        ("files", "references_seen", 2),
        ("files", "unique_file_ids", 2),
    ],
)
async def test_stage_summaries_preserve_validated_service_counts(
    stage: str, count_name: str, expected: int, session: Session
) -> None:
    orchestrator, *_ = service(session)
    result = await orchestrator.run_sync()
    assert result.stages[stage].counts[count_name] == expected


def test_stored_errors_are_bounded(session: Session) -> None:
    repository = SyncRunRepository(session)
    run = repository.begin(
        started_at=NOW,
        trigger="test",
        course_ids=[],
        check_local_files=False,
        stale_after=timedelta(minutes=30),
    )
    from app.sync.models import SyncRunError

    for index in range(120):
        repository.add_error(
            run,
            SyncRunError(
                stage="test",
                error_type="BoundedFailure",
                message=f"safe failure {index}",
            ),
        )
    assert run.error_count == 100
    assert len(run.errors) == 100


@pytest.mark.asyncio
async def test_sync_history_api_has_no_state_changing_trigger_route(
    session_factory: sessionmaker[Session],
) -> None:
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/api/sync-runs")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 405
