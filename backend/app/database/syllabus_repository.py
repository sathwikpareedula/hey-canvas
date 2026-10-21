"""Persistence for course syllabi."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Course, CourseSyllabus
from app.syllabus.models import SyllabusSnapshot
from app.text.html_sanitize import html_to_plain_text


class SyllabusRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def synchronize_course(
        self,
        course: Course,
        snapshot: SyllabusSnapshot | None,
        *,
        synced_at: datetime,
    ) -> tuple[bool, bool]:
        """Return (created, updated)."""

        if synced_at.tzinfo is None or synced_at.utcoffset() is None:
            raise ValueError("synced_at must be timezone-aware")
        existing = self._session.scalar(
            select(CourseSyllabus).where(CourseSyllabus.course_id == course.id)
        )
        if snapshot is None or not (snapshot.syllabus_html or "").strip():
            if existing is None:
                row = CourseSyllabus(
                    course=course,
                    syllabus_html=None,
                    body_text=None,
                    html_url=snapshot.html_url if snapshot else None,
                    linked_resources=[],
                    canvas_updated_at=snapshot.canvas_updated_at if snapshot else None,
                    first_seen_at=synced_at,
                    last_seen_at=synced_at,
                    last_synced_at=synced_at,
                )
                self._session.add(row)
                return True, False
            changed = existing.syllabus_html is not None
            existing.syllabus_html = None
            existing.body_text = None
            existing.html_url = snapshot.html_url if snapshot else existing.html_url
            existing.linked_resources = []
            existing.canvas_updated_at = (
                snapshot.canvas_updated_at if snapshot else existing.canvas_updated_at
            )
            existing.last_seen_at = synced_at
            existing.last_synced_at = synced_at
            return False, changed

        body_text = html_to_plain_text(snapshot.syllabus_html)
        links = [item.model_dump(mode="json") for item in snapshot.linked_resources]
        if existing is None:
            self._session.add(
                CourseSyllabus(
                    course=course,
                    syllabus_html=snapshot.syllabus_html,
                    body_text=body_text or None,
                    html_url=snapshot.html_url,
                    linked_resources=links,
                    canvas_updated_at=snapshot.canvas_updated_at,
                    first_seen_at=synced_at,
                    last_seen_at=synced_at,
                    last_synced_at=synced_at,
                )
            )
            return True, False
        changed = (
            existing.syllabus_html != snapshot.syllabus_html
            or existing.body_text != (body_text or None)
            or existing.linked_resources != links
            or existing.canvas_updated_at != snapshot.canvas_updated_at
        )
        existing.syllabus_html = snapshot.syllabus_html
        existing.body_text = body_text or None
        existing.html_url = snapshot.html_url
        existing.linked_resources = links
        existing.canvas_updated_at = snapshot.canvas_updated_at
        existing.last_seen_at = synced_at
        existing.last_synced_at = synced_at
        return False, changed

    def get_for_course(self, canvas_course_id: str) -> CourseSyllabus | None:
        return self._session.scalar(
            select(CourseSyllabus)
            .join(Course)
            .where(Course.canvas_course_id == canvas_course_id)
        )
