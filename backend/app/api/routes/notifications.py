"""Local notification APIs backed by deterministic Canvas/change evidence."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.notifications.models import NotificationCandidate, NotificationList
from app.notifications.service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
def list_notifications(
    session: Annotated[Session, Depends(get_session)],
    course_id: Annotated[str | None, Query(max_length=255)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> NotificationList:
    return NotificationService(session).list_notifications(course_id=course_id, limit=limit)


@router.post("/{notification_id}/read", response_model=NotificationCandidate)
def mark_notification_read(
    notification_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> NotificationCandidate:
    try:
        return NotificationService(session).mark_read(notification_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{notification_id}/dismiss", response_model=NotificationCandidate)
def dismiss_notification(
    notification_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> NotificationCandidate:
    try:
        return NotificationService(session).dismiss(notification_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
