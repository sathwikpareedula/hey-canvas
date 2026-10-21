"""Persistence for Canvas announcements."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.announcements.models import AnnouncementCourseSyncCounts, AnnouncementSnapshot
from app.database.models import CanvasAnnouncement, Course
from app.text.html_sanitize import html_to_plain_text

ANNOUNCEMENT_FIELDS = (
    "title",
    "message_html",
    "body_text",
    "posted_at",
    "delayed_post_at",
    "published",
    "html_url",
    "canvas_updated_at",
)


class AnnouncementRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def synchronize_course(
        self,
        course: Course,
        snapshots: list[AnnouncementSnapshot],
        *,
        synced_at: datetime,
    ) -> AnnouncementCourseSyncCounts:
        if synced_at.tzinfo is None or synced_at.utcoffset() is None:
            raise ValueError("synced_at must be timezone-aware")
        by_id = {item.canvas_topic_id: item for item in snapshots}
        existing = {
            row.canvas_topic_id: row
            for row in self._session.scalars(
                select(CanvasAnnouncement).where(CanvasAnnouncement.course_id == course.id)
            )
        }
        created = updated = unchanged = 0
        for topic_id, snapshot in by_id.items():
            row = existing.get(topic_id)
            body_text = html_to_plain_text(snapshot.message_html)
            if row is None:
                row = CanvasAnnouncement(
                    course=course,
                    canvas_topic_id=topic_id,
                    first_seen_at=synced_at,
                    last_seen_at=synced_at,
                    last_synced_at=synced_at,
                )
                self._apply(row, snapshot, body_text)
                self._session.add(row)
                created += 1
                continue
            changed = self._changed(row, snapshot, body_text)
            self._apply(row, snapshot, body_text)
            row.last_seen_at = synced_at
            row.last_synced_at = synced_at
            if changed:
                updated += 1
            else:
                unchanged += 1
        return AnnouncementCourseSyncCounts(
            announcements_received=len(snapshots),
            announcements_created=created,
            announcements_updated=updated,
            announcements_unchanged=unchanged,
        )

    def list_for_course(self, canvas_course_id: str) -> list[CanvasAnnouncement]:
        return list(
            self._session.scalars(
                select(CanvasAnnouncement)
                .join(Course)
                .where(Course.canvas_course_id == canvas_course_id)
                .order_by(CanvasAnnouncement.posted_at.desc())
            )
        )

    @staticmethod
    def _apply(
        row: CanvasAnnouncement, snapshot: AnnouncementSnapshot, body_text: str
    ) -> None:
        row.title = snapshot.title
        row.message_html = snapshot.message_html
        row.body_text = body_text or None
        row.posted_at = snapshot.posted_at
        row.delayed_post_at = snapshot.delayed_post_at
        row.published = snapshot.published
        row.html_url = snapshot.html_url
        row.canvas_updated_at = snapshot.canvas_updated_at

    @staticmethod
    def _changed(
        row: CanvasAnnouncement, snapshot: AnnouncementSnapshot, body_text: str
    ) -> bool:
        return any(
            getattr(row, field) != value
            for field, value in (
                ("title", snapshot.title),
                ("message_html", snapshot.message_html),
                ("body_text", body_text or None),
                ("posted_at", snapshot.posted_at),
                ("delayed_post_at", snapshot.delayed_post_at),
                ("published", snapshot.published),
                ("html_url", snapshot.html_url),
                ("canvas_updated_at", snapshot.canvas_updated_at),
            )
        )
