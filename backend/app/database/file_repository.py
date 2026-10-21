"""Persistence, discovery, and provenance queries for Canvas files."""

import hashlib
import json
from collections.abc import Collection, Iterable
from datetime import datetime

from sqlalchemy import case, delete, select
from sqlalchemy.orm import Session

from app.database.change_repository import ChangeRecorder
from app.database.models import (
    CanvasFile,
    Course,
    CourseMaterialReference,
    CourseModule,
    ModuleItem,
)
from app.files.models import FileReference, FileSnapshot

FILE_METADATA_FIELDS = (
    "display_name",
    "filename",
    "content_type",
    "size",
    "folder_id",
    "canvas_created_at",
    "canvas_updated_at",
    "canvas_modified_at",
    "unlock_at",
    "lock_at",
    "locked",
    "hidden",
    "hidden_for_user",
    "visibility_level",
)


class FileRepository:
    """Keep global file identity separate from normalized module-item provenance."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def discover_references(
        self,
        *,
        canvas_course_id: str | None = None,
        canvas_course_ids: Collection[str] | None = None,
    ) -> list[tuple[str, str]]:
        if canvas_course_id is not None and canvas_course_ids is not None:
            raise ValueError("use canvas_course_id or canvas_course_ids, not both")
        statement = (
            select(ModuleItem.content_id, Course.canvas_course_id)
            .join(Course, ModuleItem.course_id == Course.id)
            .join(CourseModule, ModuleItem.module_id == CourseModule.id)
            .where(
                ModuleItem.item_type == "File",
                ModuleItem.content_id.is_not(None),
                ModuleItem.last_seen_at == CourseModule.last_synced_at,
            )
            .order_by(Course.canvas_course_id, ModuleItem.content_id, ModuleItem.id)
        )
        if canvas_course_id is not None:
            statement = statement.where(Course.canvas_course_id == canvas_course_id)
        elif canvas_course_ids is not None:
            statement = statement.where(Course.canvas_course_id.in_(set(canvas_course_ids)))
        references: list[tuple[str, str]] = []
        for file_id, course_id in self._session.execute(statement):
            if file_id is not None:
                references.append((file_id, course_id))
        return references

    def reconcile_course_references(
        self,
        references: Iterable[tuple[str, str]],
        *,
        canvas_course_ids: Collection[str],
    ) -> int:
        """Remove ownership that disappeared from a successfully refreshed course.

        Global file/document rows are retained so shared-file ownership and rollback
        content remain safe. Retrieval immediately loses access through the removed
        course boundary.
        """

        active: dict[str, set[str]] = {course_id: set() for course_id in canvas_course_ids}
        for file_id, course_id in references:
            if course_id in active:
                active[course_id].add(file_id)
        removed = 0
        for course_id, file_ids in active.items():
            predicate = CourseMaterialReference.course_id == course_id
            if file_ids:
                predicate = predicate & CourseMaterialReference.canvas_file_id.not_in(file_ids)
            ids = list(
                self._session.scalars(
                    select(CourseMaterialReference.id).where(predicate)
                )
            )
            if not ids:
                continue
            self._session.execute(
                delete(CourseMaterialReference).where(
                    CourseMaterialReference.id.in_(ids)
                )
            )
            removed += len(ids)
        return removed

    def synchronize(
        self,
        snapshots: Iterable[FileSnapshot],
        *,
        synced_at: datetime,
    ) -> tuple[int, int, int]:
        if synced_at.tzinfo is None or synced_at.utcoffset() is None:
            raise ValueError("synced_at must be timezone-aware")
        by_id: dict[str, FileSnapshot] = {}
        for snapshot in snapshots:
            previous = by_id.get(snapshot.canvas_file_id)
            if previous is not None and previous != snapshot:
                raise ValueError("conflicting metadata for one Canvas file")
            by_id[snapshot.canvas_file_id] = snapshot
        existing = self._find_many(list(by_id))
        recorder = ChangeRecorder(
            self._session, observed_at=synced_at, source="canvas_file_metadata"
        )
        reference_courses = self.reference_courses(list(by_id))
        created = updated = unchanged = 0
        for file_id, snapshot in by_id.items():
            fingerprint = metadata_fingerprint(snapshot)
            record = existing.get(file_id)
            if record is None:
                record = CanvasFile(
                    canvas_file_id=file_id,
                    metadata_fingerprint=fingerprint,
                    first_seen_at=synced_at,
                    last_seen_at=synced_at,
                    last_synced_at=synced_at,
                    download_state="not_downloaded",
                )
                self._apply(record, snapshot)
                self._session.add(record)
                self._record_for_courses(
                    recorder, reference_courses.get(file_id, [None]), "created", file_id
                )
                self._record_course_references(
                    file_id,
                    reference_courses.get(file_id, []),
                    synced_at=synced_at,
                )
                created += 1
                continue
            changed = record.metadata_fingerprint != fingerprint
            if changed:
                self._record_metadata_changes(
                    recorder,
                    reference_courses.get(file_id, [None]),
                    record,
                    snapshot,
                    fingerprint,
                )
            self._apply(record, snapshot)
            record.metadata_fingerprint = fingerprint
            record.last_seen_at = synced_at
            record.last_synced_at = synced_at
            if changed:
                updated += 1
            else:
                unchanged += 1
            self._record_course_references(
                file_id,
                reference_courses.get(file_id, []),
                synced_at=synced_at,
            )
        return created, updated, unchanged

    def _record_course_references(
        self,
        file_id: str,
        course_ids: list[str | None],
        *,
        synced_at: datetime,
    ) -> None:
        existing = {
            item.course_id
            for item in self._session.scalars(
                select(CourseMaterialReference).where(
                    CourseMaterialReference.canvas_file_id == file_id
                )
            )
        }
        for course_id in {item for item in course_ids if item is not None}:
            if course_id not in existing:
                self._session.add(
                    CourseMaterialReference(
                        course_id=course_id,
                        canvas_file_id=file_id,
                        first_seen_at=synced_at,
                        last_seen_at=synced_at,
                    )
                )
            else:
                self._session.query(CourseMaterialReference).filter_by(
                    course_id=course_id, canvas_file_id=file_id
                ).update({"last_seen_at": synced_at})

    def list_all(
        self,
        *,
        canvas_course_id: str | None = None,
        canvas_course_ids: Collection[str] | None = None,
        download_state: str | None = None,
        canvas_file_id: str | None = None,
    ) -> list[CanvasFile]:
        if canvas_course_id is not None and canvas_course_ids is not None:
            raise ValueError("use canvas_course_id or canvas_course_ids, not both")
        statement = select(CanvasFile)
        if canvas_course_id is not None:
            statement = (
                statement.join(
                    CourseMaterialReference,
                    CourseMaterialReference.canvas_file_id == CanvasFile.canvas_file_id,
                )
                .where(CourseMaterialReference.course_id == canvas_course_id)
                .distinct()
            )
        elif canvas_course_ids is not None:
            statement = (
                statement.join(
                    CourseMaterialReference,
                    CourseMaterialReference.canvas_file_id == CanvasFile.canvas_file_id,
                )
                .where(CourseMaterialReference.course_id.in_(set(canvas_course_ids)))
                .distinct()
            )
        if download_state is not None:
            statement = statement.where(CanvasFile.download_state == download_state)
        if canvas_file_id is not None:
            statement = statement.where(CanvasFile.canvas_file_id == canvas_file_id)
        statement = statement.order_by(
            case((CanvasFile.display_name.is_(None), 1), else_=0),
            CanvasFile.display_name,
            CanvasFile.canvas_file_id,
        )
        return list(self._session.scalars(statement))

    def course_owns_file(self, canvas_course_id: str, canvas_file_id: str) -> bool:
        """Return whether normalized Canvas provenance authorizes this course/file pair."""

        return (
            self._session.scalar(
                select(CourseMaterialReference.id).where(
                    CourseMaterialReference.course_id == canvas_course_id,
                    CourseMaterialReference.canvas_file_id == canvas_file_id,
                )
            )
            is not None
        )

    def owned_file_ids(self, canvas_course_id: str) -> set[str]:
        """Return explicit file identities owned by one Canvas course."""

        return set(
            self._session.scalars(
                select(CourseMaterialReference.canvas_file_id).where(
                    CourseMaterialReference.course_id == canvas_course_id
                )
            )
        )

    def references_for(self, file_ids: Iterable[str]) -> dict[str, list[FileReference]]:
        ids = list(set(file_ids))
        if not ids:
            return {}
        statement = (
            select(ModuleItem, Course, CourseModule)
            .join(Course, ModuleItem.course_id == Course.id)
            .join(CourseModule, ModuleItem.module_id == CourseModule.id)
            .where(ModuleItem.item_type == "File", ModuleItem.content_id.in_(ids))
            .order_by(
                Course.canvas_course_id,
                CourseModule.position,
                ModuleItem.position,
                ModuleItem.canvas_module_item_id,
            )
        )
        result: dict[str, list[FileReference]] = {}
        for item, course, module in self._session.execute(statement):
            if item.content_id is None:
                continue
            result.setdefault(item.content_id, []).append(
                FileReference(
                    canvas_course_id=course.canvas_course_id,
                    canvas_module_id=module.canvas_module_id,
                    canvas_module_item_id=item.canvas_module_item_id,
                    module_name=module.name,
                    item_title=item.title,
                )
            )
        return result

    def get(self, canvas_file_id: str) -> CanvasFile | None:
        return self._session.scalar(
            select(CanvasFile).where(CanvasFile.canvas_file_id == canvas_file_id)
        )

    def record_download_success(
        self,
        record: CanvasFile,
        *,
        downloaded_at: datetime,
        local_relative_path: str,
        sha256: str,
        local_size: int,
        http_content_type: str | None,
    ) -> None:
        old_hash = record.sha256
        record.downloaded_at = downloaded_at
        record.local_relative_path = local_relative_path
        record.sha256 = sha256
        record.local_size = local_size
        record.download_http_content_type = http_content_type
        record.downloaded_metadata_fingerprint = record.metadata_fingerprint
        record.download_state = "downloaded"
        record.last_download_error = None
        if old_hash is not None and old_hash != sha256:
            recorder = ChangeRecorder(
                self._session, observed_at=downloaded_at, source="canvas_file_download"
            )
            for course_id in self.reference_courses([record.canvas_file_id]).get(
                record.canvas_file_id, [None]
            ):
                recorder.changed(
                    entity_type="file",
                    external_id=record.canvas_file_id,
                    course_id=course_id,
                    field_name="sha256",
                    old_value=old_hash,
                    new_value=sha256,
                    event_type="file_content_changed",
                )

    @staticmethod
    def record_download_failure(record: CanvasFile, category: str) -> None:
        record.last_download_error = category
        if not (
            record.download_state == "downloaded"
            and record.local_relative_path
            and record.sha256
            and record.local_size is not None
        ):
            record.download_state = (
                category if category in {"too_large", "inaccessible"} else "failed"
            )

    def _find_many(self, ids: list[str]) -> dict[str, CanvasFile]:
        if not ids:
            return {}
        return {
            item.canvas_file_id: item
            for item in self._session.scalars(
                select(CanvasFile).where(CanvasFile.canvas_file_id.in_(ids))
            )
        }

    def reference_courses(self, ids: list[str]) -> dict[str, list[str | None]]:
        """Return deduplicated course provenance for global Canvas file identities."""
        if not ids:
            return {}
        statement = (
            select(ModuleItem.content_id, Course.canvas_course_id)
            .join(Course, ModuleItem.course_id == Course.id)
            .where(ModuleItem.item_type == "File", ModuleItem.content_id.in_(ids))
            .distinct()
            .order_by(ModuleItem.content_id, Course.canvas_course_id)
        )
        result: dict[str, list[str | None]] = {}
        for file_id, course_id in self._session.execute(statement):
            if file_id is not None:
                result.setdefault(file_id, []).append(course_id)
        return result

    @staticmethod
    def _record_for_courses(
        recorder: ChangeRecorder,
        course_ids: list[str | None],
        operation: str,
        file_id: str,
    ) -> None:
        for course_id in course_ids:
            if operation == "created":
                recorder.created("file", file_id, course_id)

    @staticmethod
    def _record_metadata_changes(
        recorder: ChangeRecorder,
        course_ids: list[str | None],
        record: CanvasFile,
        snapshot: FileSnapshot,
        fingerprint: str,
    ) -> None:
        fields = (
            "display_name",
            "filename",
            "content_type",
            "size",
            "canvas_modified_at",
            "unlock_at",
            "lock_at",
            "locked",
            "hidden",
            "hidden_for_user",
            "visibility_level",
        )
        for course_id in course_ids:
            any_field = False
            for field in fields:
                old = getattr(record, field)
                new = getattr(snapshot, field)
                if old != new:
                    any_field = True
                    recorder.changed(
                        entity_type="file",
                        external_id=record.canvas_file_id,
                        course_id=course_id,
                        field_name=field,
                        old_value=old,
                        new_value=new,
                    )
            if not any_field:
                recorder.changed(
                    entity_type="file",
                    external_id=record.canvas_file_id,
                    course_id=course_id,
                    field_name="metadata_fingerprint",
                    old_value=record.metadata_fingerprint,
                    new_value=fingerprint,
                )

    @staticmethod
    def _apply(record: CanvasFile, snapshot: FileSnapshot) -> None:
        for field in FILE_METADATA_FIELDS:
            setattr(record, field, getattr(snapshot, field))


def metadata_fingerprint(snapshot: FileSnapshot) -> str:
    """Hash stable source metadata; the ephemeral signed URL is intentionally absent."""

    payload = snapshot.model_dump(mode="json", exclude={"canvas_file_id"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
