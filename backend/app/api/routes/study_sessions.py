"""Structured study and practice session APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.practice_sessions.models import (
    PracticeAnswer,
    PracticeFeedback,
    PracticeSessionCreate,
    PracticeSessionView,
)
from app.practice_sessions.service import PracticeSessionService
from app.study_sessions.models import (
    StudySessionCreate,
    StudySessionProgress,
    StudySessionView,
)
from app.study_sessions.service import StudySessionService

router = APIRouter(prefix="/api/study-sessions", tags=["study-sessions"])


@router.post("", response_model=StudySessionView)
def create_study_session(
    request: StudySessionCreate,
    session: Annotated[Session, Depends(get_session)],
) -> StudySessionView:
    return StudySessionService(session).create(request)


@router.get("/{session_id}", response_model=StudySessionView)
def get_study_session(
    session_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> StudySessionView:
    try:
        return StudySessionService(session).get(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/continue", response_model=StudySessionView)
def continue_study_session(
    session_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> StudySessionView:
    try:
        return StudySessionService(session).continue_session(session_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/progress", response_model=StudySessionView)
def advance_study_session(
    session_id: str,
    progress: StudySessionProgress,
    session: Annotated[Session, Depends(get_session)],
) -> StudySessionView:
    try:
        return StudySessionService(session).advance(session_id, progress)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/practice", response_model=PracticeSessionView)
def create_practice_session(
    request: PracticeSessionCreate,
    session: Annotated[Session, Depends(get_session)],
) -> PracticeSessionView:
    return PracticeSessionService(session).create(request)


@router.get("/practice/{session_id}", response_model=PracticeSessionView)
def get_practice_session(
    session_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> PracticeSessionView:
    try:
        return PracticeSessionService(session).get(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/practice/{session_id}/answer")
def answer_practice_session(
    session_id: str,
    answer: PracticeAnswer,
    session: Annotated[Session, Depends(get_session)],
) -> PracticeFeedback:
    try:
        return PracticeSessionService(session).answer(session_id, answer)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/practice/{session_id}/hint")
def hint_practice_session(
    session_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    try:
        hint = PracticeSessionService(session).hint(session_id)
        return hint.model_dump(mode="json")
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
