"""Transactional event recording, observation status, and local change queries."""

import hashlib
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.changes.models import ChangeEventView, ChangeSummary
from app.database.models import ChangeEvent, EntityObservation, SyncRunChangeEvent
from app.sync.context import current_sync_run_id


def serialize_change_value(value: Any) -> Any:
    """Convert approved small values to deterministic JSON-compatible values."""

    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("change-event datetimes must be timezone-aware")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, tuple | list):
        return [serialize_change_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_change_value(value[key]) for key in sorted(value)}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"unsupported change-event value type: {type(value).__name__}")


def text_fingerprint(value: str | None) -> str | None:
    return None if value is None else hashlib.sha256(value.encode()).hexdigest()


class ChangeRecorder:
    """Record transitions in the caller's current database transaction."""

    def __init__(self, session: Session, *, observed_at: datetime, source: str) -> None:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        self._session = session
        self._observed_at = observed_at
        self._source = source

    def created(self, entity_type: str, external_id: str, course_id: str | None) -> None:
        self.record(
            entity_type=entity_type,
            external_id=external_id,
            course_id=course_id,
            event_type="entity_created",
        )

    def changed(
        self,
        *,
        entity_type: str,
        external_id: str,
        course_id: str | None,
        field_name: str,
        old_value: Any,
        new_value: Any,
        event_type: str = "field_changed",
        context: dict[str, Any] | None = None,
    ) -> None:
        old_serialized = serialize_change_value(old_value)
        new_serialized = serialize_change_value(new_value)
        if old_serialized == new_serialized:
            return
        self.record(
            entity_type=entity_type,
            external_id=external_id,
            course_id=course_id,
            event_type=event_type,
            field_name=field_name,
            old_value=old_serialized,
            new_value=new_serialized,
            context=context,
        )

    def record(
        self,
        *,
        entity_type: str,
        external_id: str,
        course_id: str | None,
        event_type: str,
        field_name: str | None = None,
        old_value: Any = None,
        new_value: Any = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        event = ChangeEvent(
                entity_type=entity_type,
                entity_external_id=external_id,
                course_canvas_id=course_id,
                event_type=event_type,
                field_name=field_name,
                old_value=serialize_change_value(old_value),
                new_value=serialize_change_value(new_value),
                observed_at=self._observed_at,
                source=self._source,
                context=serialize_change_value(context) if context is not None else None,
                created_at=self._observed_at,
            )
        self._session.add(event)
        run_id = current_sync_run_id()
        if run_id is not None:
            self._session.add(SyncRunChangeEvent(sync_run_id=run_id, change_event=event))

    def observe_status(
        self,
        *,
        key: str,
        entity_type: str,
        external_id: str,
        course_id: str | None,
        status: str,
        transition_event: str | None,
        details: dict[str, Any] | None = None,
    ) -> str | None:
        observation = self._session.scalar(
            select(EntityObservation).where(EntityObservation.observation_key == key)
        )
        previous = observation.status if observation is not None else None
        if observation is None:
            observation = EntityObservation(
                observation_key=key,
                entity_type=entity_type,
                entity_external_id=external_id,
                course_canvas_id=course_id,
                status=status,
                details=details,
                last_observed_at=self._observed_at,
            )
            self._session.add(observation)
        else:
            observation.status = status
            observation.details = details
            observation.last_observed_at = self._observed_at
        if previous is not None and previous != status and transition_event is not None:
            self.changed(
                entity_type=entity_type,
                external_id=external_id,
                course_id=course_id,
                field_name="status",
                old_value=previous,
                new_value=status,
                event_type=transition_event,
                context=details,
            )
        return previous


class ChangeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_events(
        self,
        *,
        course_id: str | None = None,
        entity_type: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[ChangeEvent]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        statement = self._statement(
            course_id=course_id,
            entity_type=entity_type,
            event_type=event_type,
            since=since,
        )
        statement = statement.order_by(ChangeEvent.observed_at.desc(), ChangeEvent.id.desc()).limit(
            limit
        )
        return list(self._session.scalars(statement))

    @staticmethod
    def _statement(
        *,
        course_id: str | None,
        entity_type: str | None,
        event_type: str | None,
        since: datetime | None,
    ) -> Select[tuple[ChangeEvent]]:
        statement: Select[tuple[ChangeEvent]] = select(ChangeEvent)
        if course_id is not None:
            statement = statement.where(ChangeEvent.course_canvas_id == course_id)
        if entity_type is not None:
            statement = statement.where(ChangeEvent.entity_type == entity_type)
        if event_type is not None:
            statement = statement.where(ChangeEvent.event_type == event_type)
        if since is not None:
            if since.tzinfo is None or since.utcoffset() is None:
                raise ValueError("since must be timezone-aware")
            statement = statement.where(ChangeEvent.observed_at >= since)
        return statement

    def views(self, **filters: Any) -> list[ChangeEventView]:
        return [ChangeEventView.model_validate(event) for event in self.list_events(**filters)]

    def summary(self, **filters: Any) -> ChangeSummary:
        statement = self._statement(
            course_id=filters.get("course_id"),
            entity_type=filters.get("entity_type"),
            event_type=filters.get("event_type"),
            since=filters.get("since"),
        ).order_by(ChangeEvent.id)
        events = cast(list[ChangeEvent], list(self._session.scalars(statement)))
        return ChangeSummary(
            new_assignments=sum(
                event.entity_type == "assignment" and event.event_type == "entity_created"
                for event in events
            ),
            deadline_changes=sum(
                event.entity_type == "assignment"
                and event.event_type == "field_changed"
                and event.field_name == "due_at"
                for event in events
            ),
            module_changes=sum(event.entity_type == "module" for event in events),
            module_item_changes=sum(event.entity_type == "module_item" for event in events),
            file_metadata_changes=sum(
                event.entity_type == "file"
                and event.event_type in {"entity_created", "field_changed"}
                for event in events
            ),
            file_content_changes=sum(
                event.event_type == "file_content_changed" for event in events
            ),
            local_file_integrity_issues=sum(
                event.event_type in {"local_file_missing", "local_file_corrupt"}
                for event in events
            ),
        )

    def list_for_run(self, run_id: int) -> list[ChangeEvent]:
        statement = (
            select(ChangeEvent)
            .join(SyncRunChangeEvent, SyncRunChangeEvent.change_event_id == ChangeEvent.id)
            .where(SyncRunChangeEvent.sync_run_id == run_id)
            .order_by(ChangeEvent.observed_at, ChangeEvent.id)
        )
        return list(self._session.scalars(statement))

    def summary_for_run(self, run_id: int) -> ChangeSummary:
        events = self.list_for_run(run_id)
        return self._summarize(events)

    @staticmethod
    def _summarize(events: list[ChangeEvent]) -> ChangeSummary:
        return ChangeSummary(
            new_assignments=sum(
                event.entity_type == "assignment" and event.event_type == "entity_created"
                for event in events
            ),
            deadline_changes=sum(
                event.entity_type == "assignment"
                and event.event_type == "field_changed"
                and event.field_name == "due_at"
                for event in events
            ),
            module_changes=sum(event.entity_type == "module" for event in events),
            module_item_changes=sum(event.entity_type == "module_item" for event in events),
            file_metadata_changes=sum(
                event.entity_type == "file"
                and event.event_type in {"entity_created", "field_changed"}
                for event in events
            ),
            file_content_changes=sum(
                event.event_type == "file_content_changed" for event in events
            ),
            local_file_integrity_issues=sum(
                event.event_type in {"local_file_missing", "local_file_corrupt"}
                for event in events
            ),
        )
