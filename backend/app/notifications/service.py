"""Deterministic notification generation from Canvas and change evidence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.changes.models import ChangeEventView
from app.database.assignment_repository import AssignmentRepository
from app.database.change_repository import ChangeRepository
from app.database.models import Assignment, NotificationRecord
from app.notifications.models import (
    NotificationCandidate,
    NotificationList,
    NotificationSeverity,
    NotificationType,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


class NotificationService:
    """Build bounded, deterministic academic notifications from local truth."""

    def __init__(
        self,
        session: Session,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    def list_notifications(
        self,
        *,
        course_id: str | None = None,
        limit: int = 100,
    ) -> NotificationList:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        assignments = AssignmentRepository(self._session).list_all(
            canvas_course_id=course_id,
        )
        events = ChangeRepository(self._session).views(
            course_id=course_id,
            limit=200,
        )
        items = self._candidate_notifications(assignments=assignments, events=events, now=now)
        self._persist_candidates(items, now=now)
        persisted = self._session.scalars(
            select(NotificationRecord)
            .where(
                NotificationRecord.course_id == course_id
                if course_id is not None
                else NotificationRecord.id > 0
            )
            .order_by(NotificationRecord.observed_at.desc(), NotificationRecord.id.desc())
            .limit(200)
        )
        items = [self._to_candidate(item) for item in persisted]
        sorted_items = sorted(
            items,
            key=lambda item: (self._sort_key(item), item.observed_at),
            reverse=True,
        )
        return NotificationList(
            items=tuple(sorted_items[:limit]),
            total=len(sorted_items),
        )

    def mark_read(self, notification_id: str, *, read: bool = True) -> NotificationCandidate:
        record = self._session.scalar(
            select(NotificationRecord).where(NotificationRecord.notification_id == notification_id)
        )
        if record is None:
            raise LookupError("notification not found")
        record.read = read
        record.updated_at = self._clock()
        self._session.commit()
        return self._to_candidate(record)

    def dismiss(self, notification_id: str) -> NotificationCandidate:
        record = self._session.scalar(
            select(NotificationRecord).where(NotificationRecord.notification_id == notification_id)
        )
        if record is None:
            raise LookupError("notification not found")
        record.dismissed = True
        record.updated_at = self._clock()
        self._session.commit()
        return self._to_candidate(record)

    def _persist_candidates(
        self, items: list[NotificationCandidate], *, now: datetime
    ) -> None:
        for item in items:
            record = self._session.scalar(
                select(NotificationRecord).where(NotificationRecord.dedupe_key == item.dedupe_key)
            )
            if record is None:
                self._session.add(
                    NotificationRecord(
                        notification_id=item.id,
                        course_id=item.course_id,
                        assignment_id=item.assignment_id,
                        notification_type=item.notification_type.value,
                        severity=item.severity.value,
                        title=item.title,
                        message=item.message,
                        due_at=item.due_at,
                        source=item.source,
                        observed_at=item.observed_at,
                        dedupe_key=item.dedupe_key,
                        read=item.read,
                        dismissed=item.dismissed,
                        created_at=now,
                        updated_at=now,
                    )
                )
        self._session.flush()
        self._session.commit()

    @staticmethod
    def _to_candidate(record: NotificationRecord) -> NotificationCandidate:
        return NotificationCandidate(
            id=record.notification_id,
            course_id=record.course_id,
            assignment_id=record.assignment_id,
            notification_type=record.notification_type,
            severity=record.severity,
            title=record.title,
            message=record.message,
            due_at=record.due_at,
            source=record.source,
            observed_at=record.observed_at,
            dedupe_key=record.dedupe_key,
            read=record.read,
            dismissed=record.dismissed,
        )

    @staticmethod
    def _sort_key(item: NotificationCandidate) -> tuple[int, int]:
        severity_rank = {
            NotificationSeverity.CRITICAL: 4,
            NotificationSeverity.HIGH: 3,
            NotificationSeverity.MEDIUM: 2,
            NotificationSeverity.LOW: 1,
        }
        return (severity_rank[item.severity], int(item.observed_at.timestamp()))

    def _candidate_notifications(
        self,
        *,
        assignments: list[Assignment],
        events: list[ChangeEventView],
        now: datetime,
    ) -> list[NotificationCandidate]:
        candidates: list[NotificationCandidate] = []
        seen: set[str] = set()

        for assignment in assignments:
            if assignment.due_at is None:
                continue
            candidates.extend(
                self._assignment_notifications(assignment=assignment, now=now, seen=seen)
            )

        for event in events:
            if event.entity_type not in {"assignment", "academic_document", "canvas_file"}:
                continue
            if event.event_type == "entity_created" and event.entity_type == "assignment":
                key = f"assignment-new:{event.entity_external_id}:{event.course_canvas_id}"
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    NotificationCandidate(
                        id=key,
                        course_id=event.course_canvas_id or "unknown",
                        assignment_id=event.entity_external_id,
                        notification_type=NotificationType.ASSIGNMENT_NEW,
                        severity=NotificationSeverity.MEDIUM,
                        title="New assignment added",
                        message="A new assignment was synced into your local course view.",
                        due_at=None,
                        source=event.source,
                        observed_at=event.observed_at,
                        dedupe_key=key,
                    )
                )
            elif event.entity_type == "assignment" and event.field_name == "due_at":
                key = (
                    f"assignment-due-change:{event.entity_external_id}:"
                    f"{event.course_canvas_id}:{event.observed_at.isoformat()}"
                )
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    NotificationCandidate(
                        id=key,
                        course_id=event.course_canvas_id or "unknown",
                        assignment_id=event.entity_external_id,
                        notification_type=NotificationType.ASSIGNMENT_DUE_DATE_CHANGED,
                        severity=NotificationSeverity.HIGH,
                        title="Assignment due date changed",
                        message="The assignment due date changed in the local Canvas sync.",
                        due_at=(event.new_value if isinstance(event.new_value, datetime) else None),
                        source=event.source,
                        observed_at=event.observed_at,
                        dedupe_key=key,
                    )
                )
            elif (
                event.entity_type in {"academic_document", "canvas_file"}
                and event.event_type == "entity_created"
            ):
                key = f"material-new:{event.entity_external_id}:{event.course_canvas_id}"
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    NotificationCandidate(
                        id=key,
                        course_id=event.course_canvas_id or "unknown",
                        assignment_id=None,
                        notification_type=NotificationType.MATERIAL_NEW,
                        severity=NotificationSeverity.MEDIUM,
                        title="New professor material available",
                        message=(
                            "A new course document or file was synced into the local "
                            "academic index."
                        ),
                        due_at=None,
                        source=event.source,
                        observed_at=event.observed_at,
                        dedupe_key=key,
                    )
                )
        return candidates

    def _assignment_notifications(
        self,
        *,
        assignment: Assignment,
        now: datetime,
        seen: set[str],
    ) -> list[NotificationCandidate]:
        if assignment.due_at is None:
            return []
        due_at = assignment.due_at
        delta = due_at - now
        notifications: list[NotificationCandidate] = []

        if delta <= timedelta(hours=3) and delta >= timedelta(0):
            key = f"due-soon:{assignment.canvas_course_id}:{assignment.canvas_assignment_id}"
            if key not in seen:
                seen.add(key)
                notifications.append(
                    NotificationCandidate(
                        id=key,
                        course_id=assignment.canvas_course_id,
                        assignment_id=assignment.canvas_assignment_id,
                        notification_type=NotificationType.ASSIGNMENT_DUE_SOON,
                        severity=NotificationSeverity.HIGH,
                        title="Assignment due soon",
                        message=(
                            f"{assignment.name or 'This assignment'} is due within "
                            "the next three hours."
                        ),
                        due_at=due_at,
                        source="canvas_sync",
                        observed_at=now,
                        dedupe_key=key,
                    )
                )
        elif delta <= timedelta(days=1) and delta > timedelta(hours=3):
            key = f"due-tomorrow:{assignment.canvas_course_id}:{assignment.canvas_assignment_id}"
            if key not in seen:
                seen.add(key)
                notifications.append(
                    NotificationCandidate(
                        id=key,
                        course_id=assignment.canvas_course_id,
                        assignment_id=assignment.canvas_assignment_id,
                        notification_type=NotificationType.ASSIGNMENT_DUE_TOMORROW,
                        severity=NotificationSeverity.MEDIUM,
                        title="Assignment due tomorrow",
                        message=f"{assignment.name or 'This assignment'} is due tomorrow.",
                        due_at=due_at,
                        source="canvas_sync",
                        observed_at=now,
                        dedupe_key=key,
                    )
                )
        elif due_at < now:
            key = f"overdue:{assignment.canvas_course_id}:{assignment.canvas_assignment_id}"
            if key not in seen:
                seen.add(key)
                notifications.append(
                    NotificationCandidate(
                        id=key,
                        course_id=assignment.canvas_course_id,
                        assignment_id=assignment.canvas_assignment_id,
                        notification_type=NotificationType.ASSIGNMENT_OVERDUE,
                        severity=(
                            NotificationSeverity.CRITICAL
                            if now - due_at > timedelta(days=2)
                            else NotificationSeverity.HIGH
                        ),
                        title="Assignment is overdue",
                        message=f"{assignment.name or 'This assignment'} is past due.",
                        due_at=due_at,
                        source="canvas_sync",
                        observed_at=now,
                        dedupe_key=key,
                    )
                )
        return notifications
