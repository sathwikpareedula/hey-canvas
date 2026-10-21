"""Deterministic reminder plan generation for academic deadlines."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.database.models import Assignment, ReminderPreferenceRecord
from app.reminders.models import (
    ReminderOccurrence,
    ReminderPlan,
    ReminderPlanPreview,
    ReminderPreference,
    ReminderStatus,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


class ReminderPlanService:
    """Generate bounded reminder plans without external writes."""

    def __init__(
        self,
        session: Session | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_preferences(self, *, user_key: str = "local-user") -> ReminderPreference:
        if self._session is None:
            return ReminderPreference()
        record = self._session.scalar(
            select(ReminderPreferenceRecord).where(ReminderPreferenceRecord.user_key == user_key)
        )
        if record is None:
            return ReminderPreference()
        return ReminderPreference(
            enabled=record.enabled,
            lead_times_hours=tuple(record.lead_times_hours),
            timezone=record.timezone,
            course_overrides={
                key: tuple(value) for key, value in record.course_overrides.items()
            },
        )

    def save_preferences(
        self,
        preference: ReminderPreference,
        *,
        user_key: str = "local-user",
    ) -> ReminderPreference:
        try:
            ZoneInfo(preference.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        if any(value <= 0 or value > 720 for value in preference.lead_times_hours):
            raise ValueError("lead times must be between 1 and 720 hours")
        if self._session is None:
            return preference
        now = self._clock()
        record = self._session.scalar(
            select(ReminderPreferenceRecord).where(ReminderPreferenceRecord.user_key == user_key)
        )
        if record is None:
            record = ReminderPreferenceRecord(
                user_key=user_key,
                enabled=preference.enabled,
                lead_times_hours=list(preference.lead_times_hours),
                timezone=preference.timezone,
                course_overrides={
                    key: list(value) for key, value in preference.course_overrides.items()
                },
                updated_at=now,
            )
            self._session.add(record)
        else:
            record.enabled = preference.enabled
            record.lead_times_hours = list(preference.lead_times_hours)
            record.timezone = preference.timezone
            record.course_overrides = {
                key: list(value) for key, value in preference.course_overrides.items()
            }
            record.updated_at = now
        self._session.commit()
        return preference

    def preview_plan(
        self,
        assignment: Assignment,
        *,
        preference: ReminderPreference | None = None,
    ) -> ReminderPlanPreview:
        if assignment.due_at is None:
            raise ValueError("assignment due_at is required for reminder planning")
        prefs = preference or self.get_preferences()
        due_at = assignment.due_at
        course_overrides = prefs.course_overrides.get(assignment.canvas_course_id)
        lead_times = tuple(course_overrides) if course_overrides else prefs.lead_times_hours
        reminders = tuple(
            ReminderOccurrence(
                at=due_at - timedelta(hours=lead_hours),
                lead_hours=lead_hours,
                status=(
                    ReminderStatus.SCHEDULED
                    if due_at - timedelta(hours=lead_hours) > self._clock()
                    else ReminderStatus.CANCELLED
                ),
            )
            for lead_hours in lead_times
            if lead_hours > 0
        )
        plan = ReminderPlan(
            plan_id=f"plan:{assignment.canvas_course_id}:{assignment.canvas_assignment_id}",
            course_id=assignment.canvas_course_id,
            assignment_id=assignment.canvas_assignment_id,
            due_at=due_at,
            enabled=prefs.enabled,
            reminders=reminders,
        )
        summary = (
            f"{assignment.name or 'This assignment'} is due {due_at.isoformat()}; "
            f"{len(reminders)} reminder(s) are scheduled."
        )
        return ReminderPlanPreview(
            title="Assignment reminder plan",
            summary=summary,
            plan=plan,
        )
