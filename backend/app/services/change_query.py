"""Local-only deterministic change queries and summaries."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.changes.models import ChangeEventView, ChangeSummary
from app.database.change_repository import ChangeRepository


class ChangeQueryService:
    def __init__(self, session: Session) -> None:
        self._repository = ChangeRepository(session)

    def list_changes(
        self,
        *,
        course_id: str | None = None,
        entity_type: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[ChangeEventView]:
        return self._repository.views(
            course_id=course_id,
            entity_type=entity_type,
            event_type=event_type,
            since=since,
            limit=limit,
        )

    def summary(
        self,
        *,
        course_id: str | None = None,
        since: datetime | None = None,
    ) -> ChangeSummary:
        return self._repository.summary(course_id=course_id, since=since)
