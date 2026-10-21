from datetime import UTC, datetime

import pytest
from app.announcements.models import AnnouncementSnapshot
from app.database.announcement_repository import AnnouncementRepository
from app.services.announcement_sync import AnnouncementSyncService

from tests.services.test_assignment_sync import add_course


class FakeAnnouncementSource:
    def __init__(self, payload: dict[str, list[AnnouncementSnapshot]]) -> None:
        self.payload = payload

    async def fetch_course_announcements(self, canvas_course_id: str) -> list[AnnouncementSnapshot]:
        return self.payload[canvas_course_id]


@pytest.mark.asyncio
async def test_announcement_repository_is_idempotent(session) -> None:
    course = add_course(session, "278791", name="Robotics")
    now = datetime(2026, 10, 14, tzinfo=UTC)
    snapshots = [
        AnnouncementSnapshot(
            canvas_topic_id="topic-1",
            canvas_course_id="278791",
            title="Quiz 3 coverage",
            message_html="<p>Quiz 3 on Oct 20. Topics: odometry, SLAM.</p>",
            posted_at=now,
            html_url="https://canvas.example/announcements/1",
            canvas_updated_at=now,
        )
    ]
    repo = AnnouncementRepository(session)
    counts = repo.synchronize_course(course, snapshots, synced_at=now)
    session.commit()
    assert counts.announcements_created == 1
    counts2 = repo.synchronize_course(course, snapshots, synced_at=now)
    session.commit()
    assert counts2.announcements_unchanged == 1
    rows = repo.list_for_course("278791")
    assert len(rows) == 1
    assert "odometry" in (rows[0].body_text or "")


@pytest.mark.asyncio
async def test_announcement_sync_service_commits_per_course(session) -> None:
    add_course(session, "101")
    source = FakeAnnouncementSource(
        {
            "101": [
                AnnouncementSnapshot(
                    canvas_topic_id="a1",
                    canvas_course_id="101",
                    title="Quiz 3",
                    message_html="<p>Quiz 3 topics: planning</p>",
                )
            ]
        }
    )
    summary = await AnnouncementSyncService(source=source, session=session).synchronize()
    assert summary.courses_succeeded == 1
    assert summary.announcements_created == 1
