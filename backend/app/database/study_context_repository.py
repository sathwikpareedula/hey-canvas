"""Persistence operations for bounded study context."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database.models import Course, StudyContext


class StudyContextRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_course(self, course_id: str) -> Course | None:
        return self._session.scalar(
            select(Course)
            .options(joinedload(Course.study_context))
            .where(Course.canvas_course_id == course_id)
        )

    def add(self, context: StudyContext) -> None:
        self._session.add(context)

    def delete(self, context: StudyContext) -> None:
        self._session.delete(context)
