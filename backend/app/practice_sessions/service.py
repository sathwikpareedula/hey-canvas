"""Application-owned practice state and validation."""

from datetime import UTC, datetime
from uuid import uuid4

from app.assistant_tools.models import AssistantEvidenceReference
from app.database.models import Course, PracticeSessionRecord, PracticeTurnRecord
from app.practice_sessions.models import (
    DeterministicPracticeGenerator,
    PracticeAnswer,
    PracticeFeedback,
    PracticeGenerator,
    PracticeHint,
    PracticeQuestion,
    PracticeSessionCreate,
    PracticeSessionView,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


class PracticeSessionService:
    def __init__(self, session: Session, *, generator: PracticeGenerator | None = None) -> None:
        self._session = session
        self._generator = generator or DeterministicPracticeGenerator()

    def create(
        self,
        request: PracticeSessionCreate,
        *,
        evidence: tuple[AssistantEvidenceReference, ...] = (),
    ) -> PracticeSessionView:
        now = datetime.now(UTC)
        question = self._generator.question(topic=request.topic, evidence=evidence)
        record = PracticeSessionRecord(
            session_id=f"practice:{uuid4().hex}",
            course_id=request.course_id,
            topic=request.topic,
            study_mode=request.study_mode.value,
            question_index=0,
            total_questions=request.total_questions,
            correct_answers=0,
            status="active",
            current_question=question.model_dump(mode="json"),
            evidence_ids=[item.identifier for item in evidence],
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        self._session.commit()
        return self._view(record)

    def get(self, session_id: str) -> PracticeSessionView:
        return self._view(self._record(session_id))

    def answer(self, session_id: str, answer: PracticeAnswer) -> PracticeFeedback:
        record = self._record(session_id)
        if record.status != "active" or record.current_question is None:
            raise ValueError("practice session is not accepting answers")
        question = PracticeQuestion.model_validate(record.current_question)
        if answer.question_id is not None and answer.question_id != question.question_id:
            recorded = self._session.scalar(
                select(PracticeTurnRecord)
                .where(
                    PracticeTurnRecord.session_id == session_id,
                    PracticeTurnRecord.question_id == answer.question_id,
                )
                .order_by(PracticeTurnRecord.id.desc())
            )
            if recorded is not None and recorded.answer is not None:
                raise ValueError("answer already recorded for that practice question")
            raise ValueError("answer does not match the current practice question")

        current_turn = self._session.scalar(
            select(PracticeTurnRecord)
            .where(
                PracticeTurnRecord.session_id == session_id,
                PracticeTurnRecord.question_index == record.question_index,
            )
            .order_by(PracticeTurnRecord.id.desc())
        )
        if current_turn is not None and current_turn.answer is not None:
            raise ValueError("answer already recorded for the current practice question")

        if answer.question_id is None and record.question_index > 0:
            previous_turn = self._session.scalar(
                select(PracticeTurnRecord)
                .where(PracticeTurnRecord.session_id == session_id)
                .order_by(PracticeTurnRecord.id.desc())
            )
            if previous_turn is not None and previous_turn.answer == answer.answer:
                raise ValueError("duplicate practice answer retry rejected")
        feedback = self._generator.feedback(question=question.question, answer=answer.answer)
        feedback = feedback.model_copy(
            update={
                "progress": round((record.question_index + 1) / record.total_questions * 100),
            }
        )
        self._session.add(
            PracticeTurnRecord(
                session_id=session_id,
                question_id=question.question_id,
                question_index=record.question_index,
                question=question.question,
                answer=answer.answer,
                feedback=feedback.feedback,
                hint=feedback.hint,
                generated=question.generated,
                evidence_ids=[item.identifier for item in question.evidence],
                created_at=datetime.now(UTC),
            )
        )
        record.correct_answers += int(feedback.correct)
        record.question_index += 1
        if record.question_index >= record.total_questions:
            record.status = "completed"
            record.current_question = None
        else:
            next_question = feedback.next_question or self._generator.question(
                topic=record.topic, evidence=question.evidence
            )
            record.current_question = next_question.model_dump(mode="json")
        record.updated_at = datetime.now(UTC)
        self._session.commit()
        self._update_context(record)
        return feedback.model_copy(
            update={
                "next_question": (
                    PracticeQuestion.model_validate(record.current_question)
                    if record.current_question is not None
                    else None
                )
            }
        )

    def _update_context(self, record: PracticeSessionRecord) -> None:
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
                current_topic=record.topic,
                study_mode="practice",
                starting_point=f"practice_session:{record.session_id}",
                concepts_covered=[],
                topics_to_revisit=[record.topic],
                study_note=(
                    f"Practice progress: {record.question_index}/"
                    f"{record.total_questions}"
                ),
            ),
        )

    def hint(self, session_id: str) -> PracticeHint:
        record = self._record(session_id)
        if record.current_question is None:
            raise ValueError("practice session has no current question")
        question = PracticeQuestion.model_validate(record.current_question)
        return PracticeHint(
            session_id=session_id,
            hint="Hint: identify the central concept, then connect it to a concrete example.",
            question=question,
            progress=round(record.question_index / record.total_questions * 100),
        )

    def _record(self, session_id: str) -> PracticeSessionRecord:
        record = self._session.scalar(
            select(PracticeSessionRecord).where(PracticeSessionRecord.session_id == session_id)
        )
        if record is None:
            raise LookupError("practice session not found")
        return record

    @staticmethod
    def _view(record: PracticeSessionRecord) -> PracticeSessionView:
        return PracticeSessionView(
            session_id=record.session_id,
            course_id=record.course_id,
            topic=record.topic,
            status=record.status,
            question_index=record.question_index,
            total_questions=record.total_questions,
            correct_answers=record.correct_answers,
            question=(
                PracticeQuestion.model_validate(record.current_question)
                if record.current_question is not None
                else None
            ),
            progress=round(record.question_index / record.total_questions * 100),
        )
