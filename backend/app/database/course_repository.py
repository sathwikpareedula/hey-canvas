"""Persistence operations for normalized courses."""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.courses.models import CourseSnapshot, CourseSyncSummary
from app.database.change_repository import ChangeRecorder
from app.database.models import Course

COURSE_METADATA_FIELDS = (
    "course_code",
    "course_name",
    "term_canvas_id",
    "term_name",
    "term_start_at",
    "term_end_at",
    "start_at",
    "end_at",
    "workflow_state",
    "enrollment_state",
    "enrollment_type",
    "canvas_updated_at",
)


class CourseRepository:
    """Query and upsert courses inside a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def synchronize(
        self,
        snapshots: list[CourseSnapshot],
        *,
        synced_at: datetime,
    ) -> CourseSyncSummary:
        if synced_at.tzinfo is None or synced_at.utcoffset() is None:
            raise ValueError("synced_at must be timezone-aware")

        by_id = self._deduplicate_snapshots(snapshots)
        existing = self._find_by_canvas_ids(list(by_id))
        recorder = ChangeRecorder(self._session, observed_at=synced_at, source="canvas_sync")
        created = 0
        updated = 0
        unchanged = 0

        for canvas_course_id, snapshot in by_id.items():
            course = existing.get(canvas_course_id)
            if course is None:
                course = Course(
                    canvas_course_id=canvas_course_id,
                    first_seen_at=synced_at,
                    last_seen_at=synced_at,
                    last_synced_at=synced_at,
                )
                self._apply_snapshot(course, snapshot)
                self._session.add(course)
                recorder.created("course", canvas_course_id, canvas_course_id)
                created += 1
                continue

            changed = False
            for field in COURSE_METADATA_FIELDS:
                old = getattr(course, field)
                new = getattr(snapshot, field)
                if old != new:
                    changed = True
                    if field != "canvas_updated_at":
                        recorder.changed(
                            entity_type="course",
                            external_id=canvas_course_id,
                            course_id=canvas_course_id,
                            field_name=field,
                            old_value=old,
                            new_value=new,
                        )
            self._apply_snapshot(course, snapshot)
            course.last_seen_at = synced_at
            course.last_synced_at = synced_at
            if changed:
                updated += 1
            else:
                unchanged += 1

        return CourseSyncSummary(
            courses_received=len(snapshots),
            courses_created=created,
            courses_updated=updated,
            courses_unchanged=unchanged,
        )

    def list_all(self) -> list[Course]:
        statement = select(Course).order_by(Course.course_name, Course.canvas_course_id)
        return list(self._session.scalars(statement))

    def list_syncable(
        self, *, canvas_course_ids: Collection[str] | None = None
    ) -> list[Course]:
        """Return locally known active/available courses eligible for assignment sync."""

        statement = (
            select(Course)
            .where(
                Course.workflow_state == "available",
                Course.enrollment_state == "active",
            )
            .order_by(Course.canvas_course_id)
        )
        if canvas_course_ids is not None:
            statement = statement.where(Course.canvas_course_id.in_(set(canvas_course_ids)))
        return list(self._session.scalars(statement))

    def _find_by_canvas_ids(self, canvas_ids: list[str]) -> dict[str, Course]:
        if not canvas_ids:
            return {}
        statement = select(Course).where(Course.canvas_course_id.in_(canvas_ids))
        return {course.canvas_course_id: course for course in self._session.scalars(statement)}

    @staticmethod
    def _deduplicate_snapshots(snapshots: list[CourseSnapshot]) -> dict[str, CourseSnapshot]:
        by_id: dict[str, CourseSnapshot] = {}
        for snapshot in snapshots:
            previous = by_id.get(snapshot.canvas_course_id)
            if previous is not None and previous != snapshot:
                raise ValueError(
                    f"conflicting course snapshots for Canvas ID {snapshot.canvas_course_id}"
                )
            by_id[snapshot.canvas_course_id] = snapshot
        return by_id

    @staticmethod
    def _apply_snapshot(course: Course, snapshot: CourseSnapshot) -> None:
        for field in COURSE_METADATA_FIELDS:
            setattr(course, field, getattr(snapshot, field))
