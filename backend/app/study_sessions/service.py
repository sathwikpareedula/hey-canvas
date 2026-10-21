"""Deterministic structured study-session planning and continuity."""

from datetime import UTC, datetime
from uuid import uuid4

from app.assistant_tools.models import AssistantEvidenceReference
from app.database.models import Course, StudySessionRecord
from app.study_sessions.models import (
    StudySessionCreate,
    StudySessionProgress,
    StudySessionStatus,
    StudySessionView,
    StudyStep,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


class StudySessionService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        request: StudySessionCreate,
        *,
        evidence: tuple[AssistantEvidenceReference, ...] = (),
    ) -> StudySessionView:
        now = datetime.now(UTC)
        steps = self._steps(request)
        record = StudySessionRecord(
            session_id=f"study:{uuid4().hex}",
            course_id=request.course_id,
            goal=request.goal,
            duration_minutes=request.duration_minutes,
            study_mode=request.study_mode.value,
            topics=list(request.topics),
            assignment_ids=list(request.assignment_ids),
            evidence_ids=[item.identifier for item in evidence],
            steps=[item.model_dump(mode="json") for item in steps],
            progress=0,
            status=StudySessionStatus.ACTIVE.value,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        self._session.commit()
        self._update_context(record)
        return self._view(record, evidence=evidence)

    def get(self, session_id: str) -> StudySessionView:
        record = self._record(session_id)
        return self._view(record)

    def continue_session(self, session_id: str) -> StudySessionView:
        record = self._record(session_id)
        if record.status == StudySessionStatus.COMPLETED.value:
            raise ValueError("completed study session cannot be continued")
        record.status = StudySessionStatus.ACTIVE.value
        record.updated_at = datetime.now(UTC)
        self._session.commit()
        self._update_context(record)
        return self._view(record)

    def _update_context(self, record: StudySessionRecord) -> None:
        course = self._session.scalar(
            select(Course).where(Course.canvas_course_id == record.course_id)
        )
        if course is None:
            return
        from app.services.study_context import StudyContextService
        from app.study_context.models import StudyContextUpdate

        StudyContextService(self._session).update(
            record.course_id,
            StudyContextUpdate(
                current_topic=record.topics[0] if record.topics else None,
                study_mode={
                    "learn": "balanced",
                    "exam_prep": "review",
                }.get(record.study_mode, record.study_mode),
                starting_point=f"study_session:{record.session_id}",
                concepts_covered=[],
                topics_to_revisit=list(record.topics),
                study_note=f"Progress: {record.progress}%",
            ),
        )

    def advance(self, session_id: str, progress: StudySessionProgress) -> StudySessionView:
        record = self._record(session_id)
        if progress.completed_step > len(record.steps):
            raise ValueError("completed step is outside this session")
        steps = [StudyStep.model_validate(item) for item in record.steps]
        updated = [
            item.model_copy(
                update={
                    "status": (
                        "complete" if item.order <= progress.completed_step else "pending"
                    )
                }
            )
            for item in steps
        ]
        record.steps = [item.model_dump(mode="json") for item in updated]
        record.progress = round(progress.completed_step / len(steps) * 100) if steps else 100
        record.status = (
            StudySessionStatus.COMPLETED.value if record.progress == 100 else record.status
        )
        record.updated_at = datetime.now(UTC)
        self._session.commit()
        self._update_context(record)
        return self._view(record)

    def _record(self, session_id: str) -> StudySessionRecord:
        record = self._session.scalar(
            select(StudySessionRecord).where(StudySessionRecord.session_id == session_id)
        )
        if record is None:
            raise LookupError("study session not found")
        return record

    @staticmethod
    def _steps(request: StudySessionCreate) -> tuple[StudyStep, ...]:
        topics = request.topics or ("course foundations",)
        per_step = max(1, request.duration_minutes // (len(topics) + 1))
        steps = [
            StudyStep(order=1, title="Set a goal and recall prior knowledge", minutes=per_step)
        ]
        steps.extend(
            StudyStep(order=index + 2, title=f"Study {topic}", minutes=per_step)
            for index, topic in enumerate(topics)
        )
        steps.append(
            StudyStep(order=len(steps) + 1, title="Review and record next steps", minutes=per_step)
        )
        return tuple(steps[:50])

    @staticmethod
    def _view(
        record: StudySessionRecord,
        *,
        evidence: tuple[AssistantEvidenceReference, ...] = (),
    ) -> StudySessionView:
        return StudySessionView(
            course_id=record.course_id,
            goal=record.goal,
            duration_minutes=record.duration_minutes,
            topics=tuple(record.topics),
            study_mode=record.study_mode,
            assignment_ids=tuple(record.assignment_ids),
            session_id=record.session_id,
            status=record.status,
            relevant_evidence=evidence,
            steps=tuple(StudyStep.model_validate(item) for item in record.steps),
            progress=record.progress,
        )
