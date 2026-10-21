"""Preview-first calendar APIs with explicit confirmation for writes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.calendar.models import (
    CalendarConfirmation,
    CalendarEvent,
    CalendarExecutionResult,
    CalendarLinkView,
    InMemoryCalendarProvider,
)
from app.calendar.service import AcademicCalendarService
from app.database.models import Assignment, CalendarAction
from app.database.session import get_session

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


class CalendarPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str
    assignment_id: str


class CalendarPreviewResponse(BaseModel):
    event: CalendarEvent
    confirmation: CalendarConfirmation


class CalendarLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    calendar_id: str
    display_name: str


def _assignment(session: Session, course_id: str, assignment_id: str) -> Assignment:
    assignment = session.scalar(
        select(Assignment)
        .join(Assignment.course)
        .options(joinedload(Assignment.course))
        .where(
            Assignment.canvas_assignment_id == assignment_id,
            Assignment.course.has(canvas_course_id=course_id),
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="assignment not found")
    return assignment


@router.get("/links", response_model=tuple[CalendarLinkView, ...])
def list_calendar_links(
    session: Annotated[Session, Depends(get_session)],
) -> tuple[CalendarLinkView, ...]:
    return AcademicCalendarService(session).list_links()


@router.post("/links", response_model=CalendarLinkView)
def link_calendar(
    request: CalendarLinkRequest,
    session: Annotated[Session, Depends(get_session)],
) -> CalendarLinkView:
    return AcademicCalendarService(session).link_calendar(
        provider=request.provider,
        calendar_id=request.calendar_id,
        display_name=request.display_name,
    )


@router.post("/preview", response_model=CalendarPreviewResponse)
def preview_calendar_event(
    request: CalendarPreviewRequest,
    session: Annotated[Session, Depends(get_session)],
) -> CalendarPreviewResponse:
    assignment = _assignment(session, request.course_id, request.assignment_id)
    try:
        event, confirmation = AcademicCalendarService(session).preview_and_stage(assignment)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CalendarPreviewResponse(event=event, confirmation=confirmation)


@router.post("/confirm", response_model=CalendarExecutionResult)
def confirm_calendar_event(
    confirmation: CalendarConfirmation,
    session: Annotated[Session, Depends(get_session)],
) -> CalendarExecutionResult:
    service = AcademicCalendarService(session, provider=InMemoryCalendarProvider())
    action = session.scalar(
        select(CalendarAction).where(CalendarAction.action_id == confirmation.action_id)
    )
    if action is None:
        raise HTTPException(status_code=404, detail="calendar action not found")
    assignment = _assignment(session, action.course_id, action.assignment_id or "")
    try:
        return service.confirm_and_execute(confirmation, assignment=assignment)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
