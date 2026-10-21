"""Tests for managed local storage inspection, metrics, and safe maintenance."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database.models import (
    AcademicDocument,
    Base,
    CanvasFile,
    Course,
    CourseMaterialReference,
    DocumentUnit,
    SyncRun,
)
from app.main import app
from app.services.storage_service import StorageManagementService


@pytest.fixture
def storage_session(tmp_path: Path) -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)

    # 1. Course
    c1 = Course(
        canvas_course_id="robotics",
        course_name="Autonomous Robotics",
        course_code="ROB-101",
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )
    session.add(c1)
    session.flush()

    # 2. Files
    f_down = CanvasFile(
        canvas_file_id="file-down-1",
        display_name="lecture1.pdf",
        filename="lecture1.pdf",
        size=1024,
        local_size=1024,
        local_relative_path="file-down-1/lecture1.pdf",
        download_state="downloaded",
        metadata_fingerprint="fp1",
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )
    f_meta = CanvasFile(
        canvas_file_id="file-meta-2",
        display_name="syllabus.pdf",
        filename="syllabus.pdf",
        size=2048,
        download_state="not_downloaded",
        metadata_fingerprint="fp2",
        first_seen_at=now,
        last_seen_at=now,
        last_synced_at=now,
    )
    session.add_all([f_down, f_meta])
    session.flush()

    # Course References
    session.add(CourseMaterialReference(
        course_id="robotics", canvas_file_id="file-down-1", first_seen_at=now, last_seen_at=now
    ))
    session.add(CourseMaterialReference(
        course_id="robotics", canvas_file_id="file-meta-2", first_seen_at=now, last_seen_at=now
    ))

    # 3. Academic Document & Units
    doc = AcademicDocument(
        canvas_file_id="file-down-1",
        status="parsed",
        detected_type="pdf",
        created_at=now,
        updated_at=now,
        last_attempted_at=now,
        last_attempt_status="success",
    )
    session.add(doc)
    session.flush()

    session.add(DocumentUnit(
        document_id=doc.id,
        unit_type="page",
        unit_index=1,
        page_number=1,
        text="Sample indexed text",
        text_fingerprint="fp-unit-1",
        character_count=19,
    ))

    # 4. Sync Run
    sync = SyncRun(
        status="success",
        trigger="manual",
        started_at=now,
        finished_at=now,
        heartbeat_at=now,
        scope_course_ids=[],
        check_local_files=False,
        stage_results={},
        change_summary={},
        errors=[],
        created_at=now,
    )
    session.add(sync)
    session.commit()
    return session


def test_storage_summary_and_preview(storage_session: Session, tmp_path: Path) -> None:
    files_root = tmp_path / "files"
    files_root.mkdir()

    # Create cached file on disk matching CanvasFile
    file_dir = files_root / "file-down-1"
    file_dir.mkdir()
    valid_file = file_dir / "lecture1.pdf"
    valid_file.write_bytes(b"x" * 1024)

    # Create temporary .part file
    temp_file = file_dir / ".canvas-download-abc.part"
    temp_file.write_bytes(b"temp" * 10)

    # Create orphan file
    orphan_file = files_root / "orphan.txt"
    orphan_file.write_bytes(b"orphan" * 5)

    test_settings = Settings(
        academic_files_root=files_root,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
    )
    # Write dummy sqlite file so db_bytes > 0
    (tmp_path / "test.db").write_bytes(b"SQLITE" * 100)

    service = StorageManagementService(storage_session, test_settings)
    summary = service.get_summary()

    assert summary.database_bytes == 600
    assert summary.cached_files_count == 1
    assert summary.cached_files_bytes == 1024
    assert summary.temp_files_count == 1
    assert summary.temp_files_bytes == 40
    assert summary.orphaned_files_count == 1
    assert summary.orphaned_files_bytes == 30
    assert summary.metadata_only_files_count == 1
    assert summary.indexed_documents_count == 1
    assert summary.indexed_units_count == 1
    assert summary.last_sync_status == "success"

    # Preview for course
    preview = service.course_preview("robotics")
    assert preview.canvas_course_id == "robotics"
    assert preview.total_files == 2
    assert preview.downloaded_files == 1
    assert preview.not_downloaded_files == 1
    assert preview.total_file_bytes == 3072
    assert preview.estimated_new_download_bytes == 2048


def test_storage_cleanup_safety(storage_session: Session, tmp_path: Path) -> None:
    files_root = tmp_path / "files"
    files_root.mkdir()

    file_dir = files_root / "file-down-1"
    file_dir.mkdir()
    valid_file = file_dir / "lecture1.pdf"
    valid_file.write_bytes(b"valid")

    temp_file = file_dir / ".canvas-download-abc.part"
    temp_file.write_bytes(b"part-data")

    orphan_file = files_root / "orphan.txt"
    orphan_file.write_bytes(b"orphan-data")

    test_settings = Settings(
        academic_files_root=files_root,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
    )
    service = StorageManagementService(storage_session, test_settings)

    # Dry run
    dry_result = service.cleanup(remove_temp_files=True, remove_orphans=True, confirm=False)
    assert dry_result.is_dry_run is True
    assert dry_result.files_removed == 2
    assert temp_file.exists()
    assert orphan_file.exists()
    assert valid_file.exists()

    # Confirmed cleanup: temp files only
    result = service.cleanup(remove_temp_files=True, remove_orphans=False, confirm=True)
    assert result.is_dry_run is False
    assert result.files_removed == 1
    assert not temp_file.exists()
    assert orphan_file.exists()  # Kept because remove_orphans=False
    assert valid_file.exists()    # Kept because valid


def test_configurable_data_root(tmp_path: Path) -> None:
    custom_root = tmp_path / "custom_app_data"
    s = Settings(
        _env_file=None,
        database_url="sqlite:///./data/uta_academic_copilot.db",
        academic_files_root=Path("data/files"),
        hey_canvas_data_dir=custom_root,
    )
    assert s.database_url.endswith("uta_academic_copilot.db")
    assert "custom_app_data" in s.database_url
    assert s.academic_files_root == custom_root.resolve() / "files"


def test_storage_api_endpoints(storage_session: Session, tmp_path: Path) -> None:
    from app.database.session import get_session
    from app.config import get_settings

    test_settings = Settings(
        academic_files_root=tmp_path / "files",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
    )
    (tmp_path / "files").mkdir()
    (tmp_path / "test.db").write_bytes(b"sqlite-data")

    app.dependency_overrides[get_session] = lambda: storage_session
    app.dependency_overrides[get_settings] = lambda: test_settings

    try:
        client = TestClient(app)

        # GET /api/storage/summary
        resp = client.get("/api/storage/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_storage_bytes" in data
        assert "metadata_only_files_count" in data
        assert data["indexed_documents_count"] == 1

        # GET /api/storage/preview/robotics
        preview_resp = client.get("/api/storage/preview/robotics")
        assert preview_resp.status_code == 200
        pdata = preview_resp.json()
        assert pdata["total_files"] == 2
        assert pdata["estimated_new_download_bytes"] == 2048

        # POST /api/storage/cleanup (dry run)
        clean_resp = client.post(
            "/api/storage/cleanup",
            json={"confirm": False, "remove_temp_files": True},
        )
        assert clean_resp.status_code == 200
        assert clean_resp.json()["is_dry_run"] is True
    finally:
        app.dependency_overrides.clear()
