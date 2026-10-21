"""Persistence operations for user-controlled course profiles."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database.models import Course, CourseProfile


class CourseProfileRepository:
    """Query and mutate profiles inside a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, course_id: str) -> CourseProfile | None:
        statement = select(CourseProfile).where(CourseProfile.course_id == course_id)
        return self._session.scalar(statement)

    def get_course(self, course_id: str) -> Course | None:
        statement = (
            select(Course)
            .options(joinedload(Course.profile))
            .where(Course.canvas_course_id == course_id)
        )
        return self._session.scalar(statement)

    def list_all(self) -> list[Course]:
        statement = (
            select(Course)
            .options(joinedload(Course.profile))
            .order_by(Course.course_name, Course.canvas_course_id)
        )
        return list(self._session.scalars(statement).unique())

    def add(self, profile: CourseProfile) -> CourseProfile:
        self._session.add(profile)
        return profile

    def delete(self, course_id: str) -> bool:
        profile = self.get(course_id)
        if profile is None:
            return False
        self._session.delete(profile)
        return True
