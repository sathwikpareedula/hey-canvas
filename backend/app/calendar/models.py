"""Provider-neutral academic calendar contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class CalendarEventStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class CalendarEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1, max_length=255)
    course_id: str = Field(min_length=1, max_length=255)
    assignment_id: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    status: CalendarEventStatus = CalendarEventStatus.PENDING
    source: str = Field(default="canvas", max_length=50)
    external_id: str | None = Field(default=None, min_length=1, max_length=255)
    provider: str = Field(default="preview", max_length=50)


class CalendarEventCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    course_id: str = Field(min_length=1, max_length=255)
    assignment_id: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    preview_only: bool = True


class CalendarEventUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    status: CalendarEventStatus | None = None


class CalendarSyncResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_only: bool = True
    created_count: int = 0
    updated_count: int = 0
    removed_count: int = 0
    skipped_count: int = 0
    preview_events: tuple[CalendarEvent, ...] = Field(default=(), max_length=20)
    messages: tuple[str, ...] = Field(default=(), max_length=20)


class CalendarLinkView(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    provider: str = Field(min_length=1, max_length=50)
    calendar_id: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=200)
    enabled: bool = True


class CalendarConfirmation(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_id: str = Field(min_length=1, max_length=255)
    confirmation_token: str = Field(min_length=1, max_length=255)


class CalendarExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_id: str
    status: CalendarEventStatus
    event: CalendarEvent
    message: str


class CalendarProvider(Protocol):
    def list_events(self, *, course_id: str | None = None) -> tuple[CalendarEvent, ...]:
        ...

    def preview_event(self, request: CalendarEventCreateRequest) -> CalendarEvent:
        ...

    def create_event(self, request: CalendarEventCreateRequest) -> CalendarEvent:
        ...

    def update_event(self, request: CalendarEventUpdateRequest) -> CalendarEvent:
        ...

    def cancel_event(self, *, event_id: str) -> CalendarEvent:
        ...


class InMemoryCalendarProvider:
    """Deterministic provider used for local execution and tests."""

    name = "memory"

    def __init__(self) -> None:
        self._events: dict[str, CalendarEvent] = {}

    def list_events(self, *, course_id: str | None = None) -> tuple[CalendarEvent, ...]:
        values = tuple(self._events.values())
        if course_id is not None:
            values = tuple(item for item in values if item.course_id == course_id)
        return values

    def preview_event(self, request: CalendarEventCreateRequest) -> CalendarEvent:
        return CalendarEvent(
            event_id=f"preview:{request.course_id}:{request.assignment_id or 'manual'}",
            course_id=request.course_id,
            assignment_id=request.assignment_id,
            summary=request.summary,
            description=request.description,
            start_at=request.start_at,
            end_at=request.end_at,
            all_day=request.all_day,
            provider=self.name,
        )

    def create_event(self, request: CalendarEventCreateRequest) -> CalendarEvent:
        event_id = f"memory:{request.course_id}:{request.assignment_id or 'manual'}"
        existing = self._events.get(event_id)
        if existing is not None:
            return existing
        event = self.preview_event(request).model_copy(
            update={
                "event_id": event_id,
                "external_id": f"memory:{len(self._events) + 1}",
                "status": CalendarEventStatus.CONFIRMED,
            }
        )
        self._events[event.event_id] = event
        return event

    def update_event(self, request: CalendarEventUpdateRequest) -> CalendarEvent:
        current = self._events.get(request.event_id)
        if current is None:
            raise LookupError("calendar event not found")
        updated = current.model_copy(
            update={
                key: value
                for key, value in {
                    "summary": request.summary,
                    "description": request.description,
                    "start_at": request.start_at,
                    "end_at": request.end_at,
                    "all_day": request.all_day,
                    "status": request.status,
                }.items()
                if value is not None
            }
        )
        self._events[request.event_id] = updated
        return updated

    def cancel_event(self, *, event_id: str) -> CalendarEvent:
        return self.update_event(
            CalendarEventUpdateRequest(event_id=event_id, status=CalendarEventStatus.CANCELLED)
        )
