"""Deterministic mapping of Canvas assignments into calendar previews."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4

from app.calendar.models import (
    CalendarConfirmation,
    CalendarEvent,
    CalendarEventCreateRequest,
    CalendarEventStatus,
    CalendarExecutionResult,
    CalendarLinkView,
    CalendarProvider,
    CalendarSyncResult,
)
from app.database.models import Assignment, CalendarAction, CalendarLink
from sqlalchemy import select
from sqlalchemy.orm import Session


class AcademicCalendarService:
    """Preview deterministically mapped academic calendar events without external writes."""

    def __init__(
        self,
        session: Session | None = None,
        *,
        provider: CalendarProvider | None = None,
    ) -> None:
        self._session = session
        self._provider = provider

    def preview_assignment_event(
        self,
        assignment: Assignment,
        *,
        provider_name: str = "preview",
    ) -> CalendarEvent:
        if assignment.due_at is None:
            raise ValueError("assignment due_at is required for calendar preview")
        due_at = assignment.due_at
        summary = assignment.name or "Academic deadline"
        event_id = f"preview:{assignment.canvas_course_id}:{assignment.canvas_assignment_id}"
        return CalendarEvent(
            event_id=event_id,
            course_id=assignment.canvas_course_id,
            assignment_id=assignment.canvas_assignment_id,
            summary=f"{summary} due",
            description="Preview created from local Canvas assignment metadata.",
            start_at=due_at - timedelta(minutes=15),
            end_at=due_at,
            all_day=False,
            status=CalendarEventStatus.PENDING,
            source="canvas",
            provider=provider_name,
        )

    def preview_and_stage(
        self,
        assignment: Assignment,
        *,
        provider_name: str = "preview",
    ) -> tuple[CalendarEvent, CalendarConfirmation]:
        event = self.preview_assignment_event(assignment, provider_name=provider_name)
        if assignment.due_at is None:
            raise ValueError("assignment due_at is required for calendar preview")
        if self._session is None:
            raise ValueError("calendar action persistence requires a database session")
        payload = CalendarEventCreateRequest(
            course_id=event.course_id,
            assignment_id=event.assignment_id,
            summary=event.summary,
            description=event.description,
            start_at=event.start_at,
            end_at=event.end_at,
            all_day=event.all_day,
        )
        fingerprint = self._fingerprint(assignment)
        action_id = f"calendar-action:{uuid4().hex}"
        token = uuid4().hex
        self._session.add(
            CalendarAction(
                action_id=action_id,
                operation="create",
                course_id=assignment.canvas_course_id,
                assignment_id=assignment.canvas_assignment_id,
                preview_fingerprint=fingerprint,
                confirmation_token_hash=self._token_hash(token),
                request_payload=payload.model_dump(mode="json"),
                status="pending",
                created_at=datetime.now(assignment.due_at.tzinfo),
            )
        )
        self._session.commit()
        return event, CalendarConfirmation(action_id=action_id, confirmation_token=token)

    def confirm_and_execute(
        self,
        confirmation: CalendarConfirmation,
        *,
        assignment: Assignment,
        provider: CalendarProvider | None = None,
    ) -> CalendarExecutionResult:
        if self._session is None:
            raise ValueError("calendar action persistence requires a database session")
        action = self._session.scalar(
            select(CalendarAction).where(CalendarAction.action_id == confirmation.action_id)
        )
        if action is None or action.status != "pending":
            raise ValueError("confirmation is invalid or already used")
        if action.course_id != assignment.canvas_course_id or (
            action.assignment_id != assignment.canvas_assignment_id
        ):
            raise ValueError("confirmation does not match the requested assignment")
        if action.preview_fingerprint != self._fingerprint(assignment):
            raise ValueError("calendar preview is stale")
        if (
            len(confirmation.confirmation_token) < 16
            or action.confirmation_token_hash != self._token_hash(
                confirmation.confirmation_token
            )
        ):
            raise ValueError("confirmation token is invalid")
        selected_provider = provider or self._provider
        if selected_provider is None:
            raise ValueError("calendar provider is unavailable")
        request = CalendarEventCreateRequest.model_validate(action.request_payload)
        event = selected_provider.create_event(request)
        if assignment.due_at is None:
            raise ValueError("assignment due_at is required for calendar execution")
        now = datetime.now(assignment.due_at.tzinfo)
        action.status = "executed"
        action.external_event_id = event.external_id or event.event_id
        action.confirmed_at = now
        action.executed_at = now
        self._session.commit()
        return CalendarExecutionResult(
            action_id=action.action_id,
            status=event.status,
            event=event,
            message="Calendar event created after explicit confirmation.",
        )

    def link_calendar(
        self,
        *,
        provider: str,
        calendar_id: str,
        display_name: str,
    ) -> CalendarLinkView:
        if self._session is None:
            raise ValueError("calendar link persistence requires a database session")
        existing = self._session.scalar(
            select(CalendarLink).where(
                CalendarLink.provider == provider,
                CalendarLink.calendar_id == calendar_id,
            )
        )
        now = datetime.now()
        if existing is None:
            existing = CalendarLink(
                provider=provider,
                calendar_id=calendar_id,
                display_name=display_name,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
            self._session.add(existing)
        else:
            existing.display_name = display_name
            existing.enabled = True
            existing.updated_at = now
        self._session.commit()
        return CalendarLinkView.model_validate(existing)

    def list_links(self) -> tuple[CalendarLinkView, ...]:
        if self._session is None:
            return ()
        return tuple(
            CalendarLinkView.model_validate(item)
            for item in self._session.scalars(select(CalendarLink).order_by(CalendarLink.id))
        )

    @staticmethod
    def _fingerprint(assignment: Assignment) -> str:
        value = {
            "course_id": assignment.canvas_course_id,
            "assignment_id": assignment.canvas_assignment_id,
            "name": assignment.name,
            "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        }
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def preview_due_date_change(
        self,
        old_due_at: datetime | None,
        new_due_at: datetime | None,
        *,
        assignment: Assignment,
    ) -> CalendarSyncResult:
        if old_due_at is None or new_due_at is None:
            return CalendarSyncResult(
                preview_only=True,
                preview_events=(self.preview_assignment_event(assignment),),
                messages=("No concrete due-date change was available for preview.",),
            )
        preview = self.preview_assignment_event(assignment)
        return CalendarSyncResult(
            preview_only=True,
            created_count=0,
            updated_count=1,
            removed_count=0,
            skipped_count=0,
            preview_events=(preview,),
            messages=(
                "Due date change proposed from "
                f"{old_due_at.isoformat()} to {new_due_at.isoformat()}",
            ),
        )

    def confirm_create_request(
        self,
        *,
        course_id: str,
        assignment_id: str | None,
        summary: str,
        due_at: datetime,
    ) -> CalendarEventCreateRequest:
        return CalendarEventCreateRequest(
            course_id=course_id,
            assignment_id=assignment_id,
            summary=summary,
            description="User confirmation required before any external calendar write.",
            start_at=due_at - timedelta(minutes=15),
            end_at=due_at,
            all_day=False,
            preview_only=True,
        )
