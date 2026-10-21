"""Allowlisted assistant-safe automation previews."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.automation.models import (
    AllowedAutomationOperation,
    AutomationPreview,
    AutomationRequest,
)
from app.calendar.service import AcademicCalendarService
from app.database.models import Assignment
from app.database.session import get_session
from app.notifications.service import NotificationService
from app.reminders.service import ReminderPlanService

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.post("/preview", response_model=AutomationPreview)
def preview_automation(
    request: AutomationRequest,
    session: Annotated[Session, Depends(get_session)],
) -> AutomationPreview:
    if request.operation is AllowedAutomationOperation.LIST_NOTIFICATIONS:
        result = NotificationService(session).list_notifications(course_id=request.course_id)
        return AutomationPreview(
            operation=request.operation,
            title="Academic notifications",
            summary=f"{result.total} notification(s) are available.",
            payload=result.model_dump(mode="json"),
        )
    if request.assignment_id is None or request.course_id is None:
        raise HTTPException(
            status_code=422,
            detail="course_id and assignment_id are required for this operation",
        )
    assignment = session.scalar(
        select(Assignment)
        .join(Assignment.course)
        .options(joinedload(Assignment.course))
        .where(
            Assignment.canvas_assignment_id == request.assignment_id,
            Assignment.course.has(canvas_course_id=request.course_id),
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="assignment not found")
    if request.operation is AllowedAutomationOperation.PREVIEW_REMINDER_PLAN:
        plan = ReminderPlanService(session).preview_plan(assignment)
        return AutomationPreview(
            operation=request.operation,
            title=plan.title,
            summary=plan.summary,
            payload=plan.model_dump(mode="json"),
        )
    if request.operation is AllowedAutomationOperation.PREVIEW_CALENDAR_EVENT:
        event = AcademicCalendarService().preview_assignment_event(assignment)
        return AutomationPreview(
            operation=request.operation,
            title="Calendar event preview",
            summary=(
                f"{event.summary} from {event.start_at.isoformat()} "
                f"to {event.end_at.isoformat()}"
            ),
            payload=event.model_dump(mode="json"),
            requires_confirmation=True,
            safe_to_execute=False,
        )
    raise HTTPException(
        status_code=422,
        detail="linked calendar event listing requires a provider-specific read boundary",
    )
