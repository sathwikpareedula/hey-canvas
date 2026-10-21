"""Persistence and local query operations for assignments."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.assignments.models import AssignmentCourseSyncCounts, AssignmentSnapshot
from app.database.change_repository import ChangeRecorder, text_fingerprint
from app.database.models import Assignment, Course

ASSIGNMENT_METADATA_FIELDS = (
    "name",
    "description_html",
    "due_at",
    "unlock_at",
    "lock_at",
    "points_possible",
    "workflow_state",
    "html_url",
    "published",
    "has_submitted_submissions",
    "canvas_updated_at",
    "rubric",
)


class AssignmentRepository:
    """Upsert and query assignments inside caller-owned transactions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def synchronize_course(
        self,
        course: Course,
        snapshots: list[AssignmentSnapshot],
        *,
        synced_at: datetime,
    ) -> AssignmentCourseSyncCounts:
        if synced_at.tzinfo is None or synced_at.utcoffset() is None:
            raise ValueError("synced_at must be timezone-aware")
        by_id = self._deduplicate(course, snapshots)
        existing = self._find_for_course(course.id, list(by_id))
        recorder = ChangeRecorder(self._session, observed_at=synced_at, source="canvas_sync")
        created = updated = unchanged = 0

        for assignment_id, snapshot in by_id.items():
            assignment = existing.get(assignment_id)
            if assignment is None:
                assignment = Assignment(
                    course=course,
                    canvas_assignment_id=assignment_id,
                    first_seen_at=synced_at,
                    last_seen_at=synced_at,
                    last_synced_at=synced_at,
                    submission_types=list(snapshot.submission_types),
                )
                self._apply_snapshot(assignment, snapshot)
                self._session.add(assignment)
                recorder.created("assignment", assignment_id, course.canvas_course_id)
                created += 1
                continue

            changed = self._is_changed(assignment, snapshot)
            self._record_changes(recorder, course.canvas_course_id, assignment, snapshot)
            self._apply_snapshot(assignment, snapshot)
            assignment.last_seen_at = synced_at
            assignment.last_synced_at = synced_at
            if changed:
                updated += 1
            else:
                unchanged += 1

        return AssignmentCourseSyncCounts(
            assignments_received=len(snapshots),
            assignments_created=created,
            assignments_updated=updated,
            assignments_unchanged=unchanged,
        )

    def list_all(
        self,
        *,
        canvas_course_id: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> list[Assignment]:
        statement = select(Assignment).join(Course).options(joinedload(Assignment.course))
        if canvas_course_id is not None:
            statement = statement.where(Course.canvas_course_id == canvas_course_id)
        if from_at is not None:
            statement = statement.where(Assignment.due_at >= from_at)
        if to_at is not None:
            statement = statement.where(Assignment.due_at < to_at)
        statement = statement.order_by(Assignment.due_at, Assignment.name, Assignment.id)
        return list(self._session.scalars(statement))

    def query_due(
        self,
        *,
        lower: datetime | None,
        upper: datetime | None,
        canvas_course_id: str | None = None,
    ) -> list[Assignment]:
        return self.list_all(
            canvas_course_id=canvas_course_id,
            from_at=lower,
            to_at=upper,
        )

    def _find_for_course(self, course_id: int, ids: list[str]) -> dict[str, Assignment]:
        if not ids:
            return {}
        statement = select(Assignment).where(
            Assignment.course_id == course_id,
            Assignment.canvas_assignment_id.in_(ids),
        )
        return {
            assignment.canvas_assignment_id: assignment
            for assignment in self._session.scalars(statement)
        }

    @staticmethod
    def _deduplicate(
        course: Course,
        snapshots: list[AssignmentSnapshot],
    ) -> dict[str, AssignmentSnapshot]:
        by_id: dict[str, AssignmentSnapshot] = {}
        for snapshot in snapshots:
            if snapshot.canvas_course_id != course.canvas_course_id:
                raise ValueError("assignment snapshot course does not match database course")
            previous = by_id.get(snapshot.canvas_assignment_id)
            if previous is not None and previous != snapshot:
                raise ValueError("conflicting assignment snapshots for one Canvas assignment")
            by_id[snapshot.canvas_assignment_id] = snapshot
        return by_id

    @staticmethod
    def _is_changed(assignment: Assignment, snapshot: AssignmentSnapshot) -> bool:
        return any(
            getattr(assignment, field) != getattr(snapshot, field)
            for field in ASSIGNMENT_METADATA_FIELDS
        ) or assignment.submission_types != list(snapshot.submission_types)

    @staticmethod
    def _apply_snapshot(assignment: Assignment, snapshot: AssignmentSnapshot) -> None:
        for field in ASSIGNMENT_METADATA_FIELDS:
            setattr(assignment, field, getattr(snapshot, field))
        assignment.submission_types = list(snapshot.submission_types)

    @staticmethod
    def _record_changes(
        recorder: ChangeRecorder,
        course_id: str,
        assignment: Assignment,
        snapshot: AssignmentSnapshot,
    ) -> None:
        fields = (
            "name",
            "due_at",
            "unlock_at",
            "lock_at",
            "points_possible",
            "workflow_state",
            "published",
        )
        for field in fields:
            recorder.changed(
                entity_type="assignment",
                external_id=assignment.canvas_assignment_id,
                course_id=course_id,
                field_name=field,
                old_value=getattr(assignment, field),
                new_value=getattr(snapshot, field),
            )
        recorder.changed(
            entity_type="assignment",
            external_id=assignment.canvas_assignment_id,
            course_id=course_id,
            field_name="submission_types",
            old_value=assignment.submission_types,
            new_value=list(snapshot.submission_types),
        )
        recorder.changed(
            entity_type="assignment",
            external_id=assignment.canvas_assignment_id,
            course_id=course_id,
            field_name="description_fingerprint",
            old_value=text_fingerprint(assignment.description_html),
            new_value=text_fingerprint(snapshot.description_html),
        )
