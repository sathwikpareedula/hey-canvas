"""Read-only Canvas announcement contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnnouncementSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    canvas_topic_id: str = Field(max_length=255)
    canvas_course_id: str = Field(max_length=255)
    title: str | None = Field(default=None, max_length=500)
    message_html: str | None = None
    posted_at: datetime | None = None
    delayed_post_at: datetime | None = None
    published: bool | None = None
    html_url: str | None = Field(default=None, max_length=2048)
    canvas_updated_at: datetime | None = None


class AnnouncementCourseSyncCounts(BaseModel):
    model_config = ConfigDict(frozen=True)

    announcements_received: int = 0
    announcements_created: int = 0
    announcements_updated: int = 0
    announcements_unchanged: int = 0


class AnnouncementSyncFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    error_type: str
    message: str = Field(max_length=300)


class AnnouncementSyncSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    courses_attempted: int
    courses_succeeded: int
    courses_failed: int
    announcements_received: int
    announcements_created: int
    announcements_updated: int
    announcements_unchanged: int
    failures: tuple[AnnouncementSyncFailure, ...] = ()
