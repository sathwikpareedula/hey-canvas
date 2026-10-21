from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.assignments.models import AssignmentSnapshot
from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasAPIError, CanvasTransportError
from app.changes.models import ChangeEventView
from app.courses.models import CourseSnapshot
from app.database.assignment_repository import AssignmentRepository
from app.database.change_repository import ChangeRecorder, ChangeRepository
from app.database.course_repository import CourseRepository
from app.database.file_repository import FileRepository, metadata_fingerprint
from app.database.models import CanvasFile, ChangeEvent, Course
from app.database.module_repository import ModuleRepository
from app.database.session import get_session
from app.files.models import CanvasFileMetadata, FileSnapshot
from app.main import app
from app.modules.models import ModuleItemSnapshot, ModuleSnapshot
from app.services.assignment_sync import AssignmentSyncService
from app.services.file_integrity import FileIntegrityService
from app.services.file_metadata_sync import FileMetadataSyncService
from app.services.module_sync import ModuleSyncService
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from tests.api.test_files import override_factory
from tests.services.test_assignment_sync import FakeAssignmentSource
from tests.services.test_file_metadata_sync import FakeFileSource
from tests.services.test_module_sync import FakeModuleSource

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def course_snapshot(name: str = "Robotics") -> CourseSnapshot:
    return CourseSnapshot(
        canvas_course_id="101",
        course_name=name,
        course_code="CSE 4360",
        term_canvas_id="fall-2026",
        term_name="Fall 2026",
        workflow_state="available",
        enrollment_state="active",
        enrollment_type="StudentEnrollment",
    )


def assignment_snapshot(**overrides: Any) -> AssignmentSnapshot:
    values: dict[str, Any] = {
        "canvas_assignment_id": "501",
        "canvas_course_id": "101",
        "name": "Homework 1",
        "description_html": "<p>Do the work.</p>",
        "due_at": datetime(2026, 10, 1, tzinfo=UTC),
        "unlock_at": datetime(2026, 9, 20, tzinfo=UTC),
        "lock_at": datetime(2026, 10, 3, tzinfo=UTC),
        "points_possible": 100.0,
        "submission_types": ("online_upload",),
        "workflow_state": "published",
        "published": True,
    }
    values.update(overrides)
    return AssignmentSnapshot(**values)


def item_snapshot(**overrides: Any) -> ModuleItemSnapshot:
    values: dict[str, Any] = {
        "canvas_module_item_id": "1001",
        "canvas_module_id": "201",
        "canvas_course_id": "101",
        "title": "Lecture 1",
        "position": 1,
        "item_type": "File",
        "content_id": "7001",
        "indent": 0,
        "published": True,
    }
    values.update(overrides)
    return ModuleItemSnapshot(**values)


def module_snapshot(**overrides: Any) -> ModuleSnapshot:
    values: dict[str, Any] = {
        "canvas_module_id": "201",
        "canvas_course_id": "101",
        "name": "Introduction",
        "position": 1,
        "workflow_state": "active",
        "state": "unlocked",
        "published": True,
        "items_count": 1,
        "items": (item_snapshot(),),
    }
    values.update(overrides)
    return ModuleSnapshot(**values)


def file_snapshot(**overrides: Any) -> FileSnapshot:
    values: dict[str, Any] = {
        "canvas_file_id": "7001",
        "display_name": "lecture.pdf",
        "filename": "lecture.pdf",
        "content_type": "application/pdf",
        "size": 4,
        "canvas_modified_at": NOW,
        "locked": False,
        "hidden": False,
        "hidden_for_user": False,
        "visibility_level": "course",
    }
    values.update(overrides)
    return FileSnapshot(**values)


def establish_course(session: Session) -> Course:
    CourseRepository(session).synchronize([course_snapshot()], synced_at=NOW)
    session.commit()
    session.execute(delete(ChangeEvent))
    session.commit()
    result = session.scalar(select(Course).where(Course.canvas_course_id == "101"))
    assert result is not None
    return result


def establish_assignment(session: Session) -> tuple[Course, AssignmentSnapshot]:
    course = establish_course(session)
    snapshot = assignment_snapshot()
    AssignmentRepository(session).synchronize_course(course, [snapshot], synced_at=NOW)
    session.commit()
    session.execute(delete(ChangeEvent))
    session.commit()
    return course, snapshot


def establish_modules(session: Session) -> tuple[Course, ModuleSnapshot]:
    course = establish_course(session)
    snapshot = module_snapshot()
    ModuleRepository(session).synchronize_course(course, [snapshot], synced_at=NOW)
    session.commit()
    session.execute(delete(ChangeEvent))
    session.commit()
    return course, snapshot


def establish_file(session: Session) -> CanvasFile:
    establish_modules(session)
    FileRepository(session).synchronize([file_snapshot()], synced_at=NOW)
    session.commit()
    session.execute(delete(ChangeEvent))
    session.commit()
    result = FileRepository(session).get("7001")
    assert result is not None
    return result


def events(session: Session) -> list[ChangeEvent]:
    return list(session.scalars(select(ChangeEvent).order_by(ChangeEvent.id)))


@pytest.mark.parametrize("entity", ["course", "assignment", "module", "module_item", "file"])
def test_existing_rows_bootstrap_without_events(entity: str, session: Session) -> None:
    if entity == "course":
        establish_course(session)
        CourseRepository(session).synchronize(
            [course_snapshot()], synced_at=NOW + timedelta(hours=1)
        )
    elif entity == "assignment":
        course, snapshot = establish_assignment(session)
        AssignmentRepository(session).synchronize_course(
            course, [snapshot], synced_at=NOW + timedelta(hours=1)
        )
    elif entity in {"module", "module_item"}:
        course, snapshot = establish_modules(session)
        ModuleRepository(session).synchronize_course(
            course, [snapshot], synced_at=NOW + timedelta(hours=1)
        )
    else:
        establish_file(session)
        FileRepository(session).synchronize([file_snapshot()], synced_at=NOW + timedelta(hours=1))
    session.commit()
    assert events(session) == []


@pytest.mark.parametrize(
    ("field", "new_value"),
    [
        ("name", "Renamed Homework"),
        ("due_at", datetime(2026, 10, 3, tzinfo=UTC)),
        ("due_at", None),
        ("unlock_at", None),
        ("lock_at", datetime(2026, 10, 5, tzinfo=UTC)),
        ("points_possible", 125.0),
        ("workflow_state", "unpublished"),
        ("published", False),
        ("submission_types", ("online_text_entry",)),
        ("description_html", "<p>Revised private instructions.</p>"),
    ],
)
def test_assignment_field_transitions(field: str, new_value: Any, session: Session) -> None:
    course, baseline = establish_assignment(session)
    updated = baseline.model_copy(update={field: new_value})
    AssignmentRepository(session).synchronize_course(
        course, [updated], synced_at=NOW + timedelta(hours=1)
    )
    session.commit()
    result = events(session)
    assert len(result) == 1
    expected_field = "description_fingerprint" if field == "description_html" else field
    assert result[0].field_name == expected_field
    assert "Revised private instructions" not in json.dumps(result[0].new_value)


def test_due_at_null_to_value_is_exact(session: Session) -> None:
    course = establish_course(session)
    baseline = assignment_snapshot(due_at=None)
    AssignmentRepository(session).synchronize_course(course, [baseline], synced_at=NOW)
    session.commit()
    session.execute(delete(ChangeEvent))
    changed = baseline.model_copy(update={"due_at": datetime(2026, 10, 6, tzinfo=UTC)})
    AssignmentRepository(session).synchronize_course(
        course, [changed], synced_at=NOW + timedelta(hours=1)
    )
    session.commit()
    event = events(session)[0]
    assert event.old_value is None
    assert event.new_value == "2026-10-06T00:00:00Z"


@pytest.mark.asyncio
async def test_failed_assignment_sync_produces_no_events(session: Session) -> None:
    establish_assignment(session)
    source = FakeAssignmentSource({"101": RuntimeError("network failed")})
    await AssignmentSyncService(source=source, session=session).synchronize()
    assert events(session) == []


@pytest.mark.parametrize(
    ("target", "field", "new_value"),
    [
        ("module", "name", "Renamed Module"),
        ("module", "position", 4),
        ("module", "state", "locked"),
        ("module", "published", False),
        ("item", "title", "Renamed Item"),
        ("item", "position", 5),
        ("item", "indent", 2),
        ("item", "content_id", "7999"),
        ("item", "item_type", "Page"),
        ("item", "published", False),
    ],
)
def test_module_and_item_field_transitions(
    target: str, field: str, new_value: Any, session: Session
) -> None:
    course, baseline = establish_modules(session)
    if target == "module":
        changed = baseline.model_copy(update={field: new_value})
    else:
        changed_item = baseline.items[0].model_copy(update={field: new_value})
        changed = baseline.model_copy(update={"items": (changed_item,)})
    ModuleRepository(session).synchronize_course(
        course, [changed], synced_at=NOW + timedelta(hours=1)
    )
    session.commit()
    result = events(session)
    assert len(result) == 1
    assert result[0].entity_type == ("module" if target == "module" else "module_item")
    assert result[0].field_name == field


def test_module_item_move_is_one_field_change_not_delete_create(session: Session) -> None:
    course, first = establish_modules(session)
    second_module = module_snapshot(canvas_module_id="202", name="Second", items_count=0, items=())
    ModuleRepository(session).synchronize_course(
        course, [first, second_module], synced_at=NOW + timedelta(minutes=1)
    )
    session.commit()
    session.execute(delete(ChangeEvent))
    moved_item = first.items[0].model_copy(update={"canvas_module_id": "202"})
    first_empty = first.model_copy(update={"items": (), "items_count": 0})
    second_with_item = second_module.model_copy(update={"items": (moved_item,), "items_count": 1})
    ModuleRepository(session).synchronize_course(
        course, [first_empty, second_with_item], synced_at=NOW + timedelta(hours=1)
    )
    session.commit()
    result = events(session)
    assert [(event.event_type, event.field_name) for event in result] == [
        ("field_changed", "canvas_module_id")
    ]


def test_confirmed_item_absence_is_once_and_reappearance_is_reference_added(
    session: Session,
) -> None:
    course, baseline = establish_modules(session)
    ModuleRepository(session).synchronize_course(course, [baseline], synced_at=NOW)
    session.commit()
    absent = baseline.model_copy(update={"items": (), "items_count": 0})
    ModuleRepository(session).synchronize_course(
        course, [absent], synced_at=NOW + timedelta(hours=1)
    )
    ModuleRepository(session).synchronize_course(
        course, [absent], synced_at=NOW + timedelta(hours=2)
    )
    ModuleRepository(session).synchronize_course(
        course, [baseline], synced_at=NOW + timedelta(hours=3)
    )
    session.commit()
    assert [event.event_type for event in events(session)] == [
        "reference_removed",
        "reference_added",
    ]


@pytest.mark.asyncio
async def test_failed_module_sync_produces_no_events(session: Session) -> None:
    establish_modules(session)
    source = FakeModuleSource({"101": RuntimeError("partial pagination")})
    await ModuleSyncService(source=source, session=session).synchronize()
    assert events(session) == []


@pytest.mark.parametrize(
    ("field", "new_value"),
    [
        ("display_name", "lecture-renamed.pdf"),
        ("filename", "lecture-renamed.pdf"),
        ("content_type", "application/octet-stream"),
        ("size", 12),
        ("canvas_modified_at", NOW + timedelta(days=1)),
        ("locked", True),
        ("hidden", True),
        ("hidden_for_user", True),
        ("visibility_level", "institution"),
    ],
)
def test_file_metadata_transitions(field: str, new_value: Any, session: Session) -> None:
    establish_file(session)
    FileRepository(session).synchronize(
        [file_snapshot(**{field: new_value})], synced_at=NOW + timedelta(hours=1)
    )
    session.commit()
    result = events(session)
    assert len(result) == 1
    assert result[0].field_name == field
    assert result[0].event_type == "field_changed"


def test_file_content_change_requires_successful_distinct_hash(session: Session) -> None:
    record = establish_file(session)
    repository = FileRepository(session)
    repository.record_download_success(
        record,
        downloaded_at=NOW,
        local_relative_path="101/7001/lecture.pdf",
        sha256="a" * 64,
        local_size=4,
        http_content_type="application/pdf",
    )
    session.commit()
    session.execute(delete(ChangeEvent))
    repository.record_download_success(
        record,
        downloaded_at=NOW + timedelta(hours=1),
        local_relative_path="101/7001/lecture.pdf",
        sha256="b" * 64,
        local_size=4,
        http_content_type="application/pdf",
    )
    session.commit()
    result = events(session)
    assert len(result) == 1
    assert result[0].event_type == "file_content_changed"
    assert result[0].old_value == "a" * 64
    assert result[0].new_value == "b" * 64


def test_same_hash_and_download_failure_do_not_create_content_event(session: Session) -> None:
    record = establish_file(session)
    repository = FileRepository(session)
    repository.record_download_success(
        record,
        downloaded_at=NOW,
        local_relative_path="101/7001/lecture.pdf",
        sha256="a" * 64,
        local_size=4,
        http_content_type=None,
    )
    session.commit()
    session.execute(delete(ChangeEvent))
    repository.record_download_success(
        record,
        downloaded_at=NOW,
        local_relative_path="101/7001/lecture.pdf",
        sha256="a" * 64,
        local_size=4,
        http_content_type=None,
    )
    repository.record_download_failure(record, "timeout")
    session.commit()
    assert events(session) == []


@pytest.mark.parametrize(
    ("condition", "expected_event"),
    [
        ("missing", "local_file_missing"),
        ("corrupt_size", "local_file_corrupt"),
        ("corrupt_hash", "local_file_corrupt"),
    ],
)
def test_explicit_integrity_events_are_local_and_deduplicated(
    condition: str, expected_event: str, session: Session, tmp_path: Path
) -> None:
    record = establish_file(session)
    relative = "7001/lecture.pdf"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    if condition != "missing":
        path.write_bytes(b"bad" if condition == "corrupt_size" else b"data")
    repository = FileRepository(session)
    repository.record_download_success(
        record,
        downloaded_at=NOW,
        local_relative_path=relative,
        sha256=(
            hashlib.sha256(b"different").hexdigest()
            if condition == "corrupt_hash"
            else hashlib.sha256(b"data").hexdigest()
        ),
        local_size=4,
        http_content_type="application/pdf",
    )
    session.commit()
    session.execute(delete(ChangeEvent))
    service = FileIntegrityService(session=session, storage_root=tmp_path, clock=lambda: NOW)
    service.check()
    service.check()
    result = events(session)
    assert len(result) == 1
    assert result[0].event_type == expected_event
    assert result[0].source == "local_file_integrity"


def test_healthy_integrity_check_creates_no_event(session: Session, tmp_path: Path) -> None:
    record = establish_file(session)
    path = tmp_path / "7001/lecture.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"data")
    FileRepository(session).record_download_success(
        record,
        downloaded_at=NOW,
        local_relative_path="7001/lecture.pdf",
        sha256=hashlib.sha256(b"data").hexdigest(),
        local_size=4,
        http_content_type=None,
    )
    session.commit()
    session.execute(delete(ChangeEvent))
    FileIntegrityService(session=session, storage_root=tmp_path, clock=lambda: NOW).check()
    assert events(session) == []


def test_change_query_filters_order_limit_and_summary(session: Session) -> None:
    recorder = ChangeRecorder(session, observed_at=NOW, source="test")
    recorder.created("assignment", "501", "101")
    recorder.changed(
        entity_type="assignment",
        external_id="501",
        course_id="101",
        field_name="due_at",
        old_value=None,
        new_value=NOW,
    )
    recorder.record(
        entity_type="file",
        external_id="7001",
        course_id="101",
        event_type="file_content_changed",
    )
    session.commit()
    repository = ChangeRepository(session)
    assert len(repository.list_events(course_id="101")) == 3
    assert len(repository.list_events(entity_type="assignment")) == 2
    assert len(repository.list_events(event_type="field_changed")) == 1
    assert len(repository.list_events(since=NOW + timedelta(seconds=1))) == 0
    assert len(repository.list_events(limit=1)) == 1
    summary = repository.summary(course_id="101")
    assert summary.new_assignments == 1
    assert summary.deadline_changes == 1
    assert summary.file_content_changes == 1


@pytest.mark.parametrize("limit", [0, 501])
def test_change_query_rejects_invalid_limit(limit: int, session: Session) -> None:
    with pytest.raises(ValueError, match="between 1 and 500"):
        ChangeRepository(session).list_events(limit=limit)


def test_rollback_prevents_orphan_event(session: Session) -> None:
    ChangeRecorder(session, observed_at=NOW, source="test").created("assignment", "501", "101")
    session.rollback()
    assert events(session) == []


@pytest.mark.asyncio
async def test_changes_api_is_local_only_safe_and_validates_filters(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_factory() as session:
        ChangeRecorder(session, observed_at=NOW, source="test").changed(
            entity_type="assignment",
            external_id="501",
            course_id="101",
            field_name="due_at",
            old_value=None,
            new_value=NOW,
        )
        session.commit()

    async def fail(*_: object, **__: object) -> object:
        raise AssertionError("local changes API must not contact Canvas")

    monkeypatch.setattr(CanvasClient, "get_json", fail)
    app.dependency_overrides[get_session] = override_factory(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/api/changes", params={"course_id": "101"})
            invalid_limit = await client.get("/api/changes", params={"limit": 0})
            invalid_since = await client.get("/api/changes", params={"since": "2026-09-29"})
            summary = await client.get("/api/changes/summary")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["field_name"] == "due_at"
    assert "token" not in json.dumps(payload).lower()
    assert "url" not in json.dumps(payload).lower()
    assert invalid_limit.status_code == 422
    assert invalid_since.status_code == 422
    assert summary.status_code == 200


def test_event_view_never_contains_internal_fields(session: Session) -> None:
    ChangeRecorder(session, observed_at=NOW, source="test").created("file", "7001", "101")
    session.commit()
    view = ChangeEventView.model_validate(events(session)[0]).model_dump()
    assert set(view) == {
        "id",
        "entity_type",
        "entity_external_id",
        "course_canvas_id",
        "event_type",
        "field_name",
        "old_value",
        "new_value",
        "observed_at",
        "source",
        "context",
        "created_at",
    }


def test_changes_cli_uses_only_local_database(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.sync import changes_cli

    with session_factory() as session:
        ChangeRecorder(session, observed_at=NOW, source="test").created("assignment", "501", "101")
        session.commit()
    monkeypatch.setattr(changes_cli, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(changes_cli, "initialize_database", lambda: None)
    monkeypatch.setattr(changes_cli, "configure_logging", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["academic-changes", "--course-id", "101"])
    assert changes_cli.run() == 0
    output = capsys.readouterr().out
    assert "entity_created" in output
    assert "CANVAS_TOKEN" not in output


def test_signed_url_is_not_part_of_file_fingerprint() -> None:
    snapshot = file_snapshot()
    assert metadata_fingerprint(snapshot) == metadata_fingerprint(snapshot.model_copy())


def test_change_events_do_not_store_binary_content(session: Session) -> None:
    establish_file(session)
    columns = {column.name for column in ChangeEvent.__table__.columns}
    assert "content" not in columns
    assert "binary" not in columns


def test_new_course_after_baseline_records_created(session: Session) -> None:
    CourseRepository(session).synchronize([course_snapshot()], synced_at=NOW)
    session.commit()
    event = events(session)[0]
    assert (event.entity_type, event.event_type) == ("course", "entity_created")


def test_new_assignment_after_course_baseline_records_created(session: Session) -> None:
    course = establish_course(session)
    AssignmentRepository(session).synchronize_course(
        course, [assignment_snapshot()], synced_at=NOW + timedelta(hours=1)
    )
    session.commit()
    event = events(session)[0]
    assert (event.entity_type, event.event_type) == ("assignment", "entity_created")


def test_new_module_and_item_after_course_baseline_record_created(session: Session) -> None:
    course = establish_course(session)
    ModuleRepository(session).synchronize_course(
        course, [module_snapshot()], synced_at=NOW + timedelta(hours=1)
    )
    session.commit()
    assert [(event.entity_type, event.event_type) for event in events(session)] == [
        ("module", "entity_created"),
        ("module_item", "entity_created"),
    ]


def test_new_file_after_module_baseline_records_created(session: Session) -> None:
    establish_modules(session)
    FileRepository(session).synchronize([file_snapshot()], synced_at=NOW)
    session.commit()
    assert [(event.entity_type, event.event_type) for event in events(session)] == [
        ("file", "entity_created")
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("course_name", "Renamed Robotics"),
        ("course_code", "CSE 9999"),
        ("term_name", "Fall 2026 Updated"),
        ("workflow_state", "completed"),
        ("enrollment_state", "completed"),
        ("start_at", datetime(2026, 8, 25, tzinfo=UTC)),
        ("end_at", datetime(2026, 12, 20, tzinfo=UTC)),
    ],
)
def test_course_meaningful_field_changes(field: str, value: Any, session: Session) -> None:
    establish_course(session)
    CourseRepository(session).synchronize(
        [course_snapshot().model_copy(update={field: value})],
        synced_at=NOW + timedelta(hours=1),
    )
    session.commit()
    result = events(session)
    assert len(result) == 1
    assert result[0].field_name == field


def test_canvas_updated_at_only_does_not_create_academic_event(session: Session) -> None:
    establish_course(session)
    changed = course_snapshot().model_copy(update={"canvas_updated_at": NOW})
    summary = CourseRepository(session).synchronize([changed], synced_at=NOW + timedelta(hours=1))
    session.commit()
    assert summary.courses_updated == 1
    assert events(session) == []


@pytest.mark.asyncio
async def test_inaccessible_file_records_event_but_timeout_does_not(session: Session) -> None:
    establish_file(session)
    inaccessible = FakeFileSource(
        {"7001": CanvasAPIError("Canvas returned 404 for GET /api/v1/files/7001", status_code=404)}
    )
    await FileMetadataSyncService(
        source=inaccessible, session=session, clock=lambda: NOW + timedelta(hours=1)
    ).synchronize()
    assert [event.event_type for event in events(session)] == ["entity_became_inaccessible"]
    session.execute(delete(ChangeEvent))
    session.commit()
    timeout = FakeFileSource({"7001": CanvasTransportError("bounded timeout")})
    await FileMetadataSyncService(
        source=timeout, session=session, clock=lambda: NOW + timedelta(hours=2)
    ).synchronize()
    assert events(session) == []


@pytest.mark.asyncio
async def test_file_access_recovery_is_a_separate_status_transition(session: Session) -> None:
    establish_file(session)
    inaccessible = FakeFileSource(
        {"7001": CanvasAPIError("Canvas returned 403 for GET /api/v1/files/7001", status_code=403)}
    )
    await FileMetadataSyncService(source=inaccessible, session=session).synchronize()
    session.execute(delete(ChangeEvent))
    session.commit()
    source = FakeFileSource({"7001": CanvasFileMetadata(snapshot=file_snapshot())})
    await FileMetadataSyncService(source=source, session=session).synchronize()
    result = events(session)
    assert len(result) == 1
    assert result[0].field_name == "status"
    assert (result[0].old_value, result[0].new_value) == ("inaccessible", "accessible")


def test_summary_is_not_truncated_at_api_result_limit(session: Session) -> None:
    recorder = ChangeRecorder(session, observed_at=NOW, source="test")
    for index in range(501):
        recorder.created("assignment", str(index), "101")
    session.commit()
    assert ChangeRepository(session).summary().new_assignments == 501


def test_integrity_restoration_is_distinct(session: Session, tmp_path: Path) -> None:
    record = establish_file(session)
    FileRepository(session).record_download_success(
        record,
        downloaded_at=NOW,
        local_relative_path="7001/lecture.pdf",
        sha256=hashlib.sha256(b"data").hexdigest(),
        local_size=4,
        http_content_type=None,
    )
    session.commit()
    session.execute(delete(ChangeEvent))
    service = FileIntegrityService(session=session, storage_root=tmp_path, clock=lambda: NOW)
    service.check()
    path = tmp_path / "7001/lecture.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"data")
    service.check()
    assert [event.event_type for event in events(session)] == [
        "local_file_missing",
        "local_file_restored",
    ]


@pytest.mark.asyncio
async def test_one_course_failure_preserves_other_course_event(session: Session) -> None:
    establish_course(session)
    CourseRepository(session).synchronize(
        [course_snapshot().model_copy(update={"canvas_course_id": "102"})], synced_at=NOW
    )
    session.commit()
    session.execute(delete(ChangeEvent))
    session.commit()
    source = FakeAssignmentSource(
        {
            "101": [assignment_snapshot(name="Changed")],
            "102": RuntimeError("failed course"),
        }
    )
    summary = await AssignmentSyncService(source=source, session=session).synchronize()
    assert summary.courses_succeeded == 1
    assert summary.courses_failed == 1
    assert [event.entity_external_id for event in events(session)] == ["501"]
