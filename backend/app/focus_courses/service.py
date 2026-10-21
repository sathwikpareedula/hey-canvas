"""Persistent, deterministic focus-course selection."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models import Course, FocusCourse
from app.focus_courses.models import FocusCourseView


class FocusCourseService:
    def __init__(self, session: Session, *, user_key: str = "local-user") -> None:
        if not user_key or len(user_key) > 100:
            raise ValueError("user_key is invalid")
        self._session = session
        self._user_key = user_key

    def list(self) -> tuple[FocusCourseView, ...]:
        records = self._session.scalars(
            select(FocusCourse)
            .join(FocusCourse.course)
            .where(FocusCourse.user_key == self._user_key)
            .order_by(FocusCourse.position, FocusCourse.course_id)
        )
        return tuple(self._view(record) for record in records)

    def suggested(self, *, limit: int = 20) -> tuple[str, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        selected = {item.course_id for item in self.list()}
        courses = self._session.scalars(
            select(Course).order_by(Course.term_end_at.desc(), Course.last_synced_at.desc())
        )
        candidates = (
            course.canvas_course_id
            for course in courses
            if course.canvas_course_id not in selected
            and (course.enrollment_state in {None, "active"})
            and course.workflow_state in {None, "available"}
        )
        return tuple(list(candidates)[:limit])

    def replace(self, course_ids: tuple[str, ...]) -> tuple[FocusCourseView, ...]:
        normalized = self._validate_ids(course_ids)
        courses = {
            course.canvas_course_id: course
            for course in self._session.scalars(
                select(Course).where(Course.canvas_course_id.in_(normalized))
            )
        }
        missing = [course_id for course_id in normalized if course_id not in courses]
        if missing:
            raise LookupError("one or more focus courses were not found locally")
        self._session.execute(
            delete(FocusCourse).where(FocusCourse.user_key == self._user_key)
        )
        now = datetime.now(UTC)
        self._session.add_all(
            FocusCourse(
                user_key=self._user_key,
                course_id=course_id,
                position=index,
                created_at=now,
                updated_at=now,
            )
            for index, course_id in enumerate(normalized)
        )
        self._session.commit()
        return self.list()

    def add(self, course_id: str) -> FocusCourseView:
        current = [item.course_id for item in self.list()]
        if course_id in current:
            return self.list()[current.index(course_id)]
        return self.replace(tuple([*current, course_id]))[-1]

    def remove(self, course_id: str) -> tuple[FocusCourseView, ...]:
        return self.replace(
            tuple(item.course_id for item in self.list() if item.course_id != course_id)
        )

    @staticmethod
    def _validate_ids(course_ids: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(item.strip() for item in course_ids))
        if any(not item or len(item) > 255 for item in normalized):
            raise ValueError("course IDs must be non-empty and bounded")
        return normalized

    @staticmethod
    def _view(record: FocusCourse) -> FocusCourseView:
        return FocusCourseView(
            course_id=record.course_id,
            position=record.position,
            course_name=record.course.course_name,
            course_code=record.course.course_code,
            term_name=record.course.term_name,
            workflow_state=record.course.workflow_state,
            enrollment_state=record.course.enrollment_state,
            selected_at=record.created_at,
        )
