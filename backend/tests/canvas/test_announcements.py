from datetime import UTC, datetime

from app.canvas.announcements import normalize_announcement


def test_normalize_announcement_maps_canvas_fields() -> None:
    snapshot = normalize_announcement(
        {
            "id": "9001",
            "title": "Quiz 3",
            "message": "<p>Topics: SLAM</p>",
            "posted_at": "2026-10-01T12:00:00Z",
            "html_url": "https://canvas.example/t/9001",
        },
        canvas_course_id="278791",
    )
    assert snapshot.canvas_topic_id == "9001"
    assert snapshot.title == "Quiz 3"
    assert snapshot.posted_at == datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
