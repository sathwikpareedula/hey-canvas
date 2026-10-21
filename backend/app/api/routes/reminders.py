"""Local reminder preference and deterministic plan APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database.models import Assignment
from app.database.session import get_session
from app.reminders.models import ReminderPlanPreview, ReminderPreference
from app.reminders.service import ReminderPlanService

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


class ReminderPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str
    assignment_id: str


@router.get("/preferences", response_model=ReminderPreference)
def get_preferences(
    session: Annotated[Session, Depends(get_session)],
) -> ReminderPreference:
    return ReminderPlanService(session).get_preferences()


@router.put("/preferences", response_model=ReminderPreference)
def save_preferences(
    preference: ReminderPreference,
    session: Annotated[Session, Depends(get_session)],
) -> ReminderPreference:
    try:
        return ReminderPlanService(session).save_preferences(preference)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/preview", response_model=ReminderPlanPreview)
def preview_reminder_plan(
    request: ReminderPlanRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ReminderPlanPreview:
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
    try:
        return ReminderPlanService(session).preview_plan(assignment)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
