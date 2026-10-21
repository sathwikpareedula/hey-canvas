from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.database.models import (
    AcademicDocument,
    CanvasFile,
    Course,
    CourseMaterialReference,
)
from app.lifecycle.models import LifecycleScope
from app.lifecycle.service import LifecycleService


def _course(session, course_id: str) -> None:
    now = datetime.now(UTC)
    session.add(
        Course(
            canvas_course_id=course_id,
            course_name=course_id,
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
    )
    session.commit()


def _file(session, file_id: str, course_ids: tuple[str, ...], relative_path: str) -> None:
    now = datetime.now(UTC)
    session.add(
        CanvasFile(
            canvas_file_id=file_id,
            metadata_fingerprint=file_id,
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
            local_relative_path=relative_path,
            download_state="downloaded",
        )
    )
    session.flush()
    session.add(
        AcademicDocument(
            canvas_file_id=file_id,
            status="parsed",
            last_attempt_status="parsed",
            last_attempted_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    session.add_all(
        CourseMaterialReference(
            course_id=course_id,
            canvas_file_id=file_id,
            first_seen_at=now,
            last_seen_at=now,
        )
        for course_id in course_ids
    )
    session.commit()


def test_course_clear_preserves_shared_material_and_removes_unique_derivative(
    session, tmp_path: Path, monkeypatch
) -> None:
    _course(session, "course-a")
    _course(session, "course-b")
    shared = "files/shared.pdf"
    unique = "files/unique.pdf"
    (tmp_path / "files").mkdir()
    (tmp_path / "files" / "shared.pdf").write_bytes(b"shared")
    (tmp_path / "files" / "unique.pdf").write_bytes(b"unique")
    _file(session, "shared", ("course-a", "course-b"), shared)
    _file(session, "unique", ("course-a",), unique)
    monkeypatch.setattr(
        "app.lifecycle.service.get_settings",
        lambda: Settings(academic_files_root=tmp_path),
    )

    result = LifecycleService(session).clear(
        LifecycleScope(course_id="course-a", include_materials=True)
    )

    assert result.materials_marked_for_removal == 1
    assert (tmp_path / "files" / "shared.pdf").exists()
    assert not (tmp_path / "files" / "unique.pdf").exists()
    assert session.query(CanvasFile).filter_by(canvas_file_id="unique").one_or_none() is None
    assert session.query(CanvasFile).filter_by(canvas_file_id="shared").one()
