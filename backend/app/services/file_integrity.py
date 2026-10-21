"""Explicit local-only integrity checks for successfully downloaded Canvas files."""

import hashlib
from collections.abc import Callable, Collection
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.database.change_repository import ChangeRecorder
from app.database.file_repository import FileRepository
from app.files.paths import resolve_relative_path


class FileIntegrityService:
    def __init__(
        self,
        *,
        session: Session,
        storage_root: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._root = storage_root
        self._clock = clock or (lambda: datetime.now(UTC))

    def check(
        self,
        *,
        canvas_file_id: str | None = None,
        canvas_course_ids: Collection[str] | None = None,
    ) -> dict[str, int]:
        repository = FileRepository(self._session)
        records = repository.list_all(
            canvas_file_id=canvas_file_id,
            canvas_course_ids=canvas_course_ids,
            download_state="downloaded",
        )
        checked = healthy = missing = corrupt = 0
        observed_at = self._clock()
        recorder = ChangeRecorder(
            self._session, observed_at=observed_at, source="local_file_integrity"
        )
        for record in records:
            checked += 1
            status = self._status(record.local_relative_path, record.local_size, record.sha256)
            healthy += int(status == "healthy")
            missing += int(status == "missing")
            corrupt += int(status == "corrupt")
            courses = repository.reference_courses([record.canvas_file_id]).get(
                record.canvas_file_id, [None]
            )
            for course_id in courses:
                event = {
                    "missing": "local_file_missing",
                    "corrupt": "local_file_corrupt",
                    "healthy": "local_file_restored",
                }[status]
                previous = recorder.observe_status(
                    key=f"local_file:{record.canvas_file_id}:{course_id or ''}",
                    entity_type="file",
                    external_id=record.canvas_file_id,
                    course_id=course_id,
                    status=status,
                    transition_event=event,
                )
                if previous is None and status != "healthy":
                    recorder.record(
                        entity_type="file",
                        external_id=record.canvas_file_id,
                        course_id=course_id,
                        event_type=event,
                        field_name="local_integrity",
                        old_value="healthy",
                        new_value=status,
                    )
        self._session.commit()
        return {"checked": checked, "healthy": healthy, "missing": missing, "corrupt": corrupt}

    def _status(
        self,
        relative_path: str | None,
        expected_size: int | None,
        expected_hash: str | None,
    ) -> str:
        if relative_path is None or expected_size is None or expected_hash is None:
            return "corrupt"
        try:
            path = resolve_relative_path(self._root, relative_path)
        except ValueError:
            return "corrupt"
        if not path.is_file():
            return "missing"
        if path.stat().st_size != expected_size:
            return "corrupt"
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return "healthy" if digest.hexdigest() == expected_hash else "corrupt"
