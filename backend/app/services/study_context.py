"""Application service for bounded personal study context."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.canvas.courses import _normalize_canvas_id
from app.database.models import Course, StudyContext
from app.database.study_context_repository import StudyContextRepository
from app.services.course_profiles import CourseNotFoundError
from app.study_context.models import StudyContextUpdate, StudyContextView, StudyMode


def _stored_study_mode(value: str | None) -> StudyMode:
    """Map a persisted mode onto the public enum; legacy values must not break chat."""
    try:
        return StudyMode(value or "")
    except ValueError:
        return StudyMode.BALANCED


class StudyContextService:
    """Persist user state without contacting Canvas or inferring anything."""

    def __init__(self, session: Session, *, clock: Callable[[], datetime] | None = None) -> None:
        self._session = session
        self._repository = StudyContextRepository(session)
        self._clock = clock or (lambda: datetime.now(UTC))

    def get(self, course_id: str) -> StudyContextView:
        course = self._course(course_id)
        return self._view(course)

    def update(self, course_id: str, payload: StudyContextUpdate) -> StudyContextView:
        course = self._course(course_id)
        now = self._aware_now()
        context = course.study_context
        if context is None:
            context = StudyContext(
                course_id=course.canvas_course_id,
                created_at=now,
                updated_at=now,
                concepts_covered=[],
                topics_to_revisit=[],
            )
            course.study_context = context
            self._repository.add(context)
        for key, value in payload.model_dump().items():
            setattr(context, key, value)
        context.updated_at = now
        self._session.commit()
        self._session.refresh(context)
        return self._view(course)

    def reset(self, course_id: str) -> None:
        course = self._course(course_id)
        if course.study_context is not None:
            self._repository.delete(course.study_context)
            course.study_context = None
            self._session.commit()

    def _course(self, course_id: str) -> Course:
        normalized = _normalize_canvas_id(course_id, field_name="course id")
        course = self._repository.get_course(normalized)
        if course is None:
            raise CourseNotFoundError(normalized)
        return course

    @staticmethod
    def _view(course: Course) -> StudyContextView:
        context = course.study_context
        values = (
            {
                "current_topic": context.current_topic,
                "assignment_id": context.assignment_id,
                "study_mode": _stored_study_mode(context.study_mode),
                "starting_point": context.starting_point,
                "concepts_covered": context.concepts_covered,
                "topics_to_revisit": context.topics_to_revisit,
                "study_note": context.study_note,
            }
            if context
            else StudyContextUpdate().model_dump()
        )
        return StudyContextView(
            course_id=course.canvas_course_id,
            course_name=course.course_name,
            has_context=context is not None,
            created_at=context.created_at if context else None,
            updated_at=context.updated_at if context else None,
            **values,
        )

    def _aware_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(UTC)
