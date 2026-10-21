"""Application service for course profiles and effective study preferences."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.canvas.courses import _normalize_canvas_id
from app.course_profiles.models import (
    CourseProfileData,
    CourseProfileUpdate,
    CourseProfileView,
    CourseStudyPreferences,
    EffectiveCourseContext,
)
from app.database.course_profile_repository import CourseProfileRepository
from app.database.models import Course, CourseProfile


class CourseNotFoundError(LookupError):
    """Raised when a profile operation targets an unknown local course."""


class CourseProfileService:
    """Typed profile operations that never contact Canvas."""

    def __init__(
        self,
        session: Session,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._repository = CourseProfileRepository(session)
        self._clock = clock or (lambda: datetime.now(UTC))

    def get(self, course_id: str) -> CourseProfileView:
        course = self._course(course_id)
        return self._view(course)

    def list(self) -> list[CourseProfileView]:
        return [self._view(course) for course in self._repository.list_all()]

    def upsert(self, course_id: str, update: CourseProfileUpdate) -> CourseProfileView:
        course = self._course(course_id)
        now = self._aware_now()
        profile = course.profile
        if profile is None:
            profile = CourseProfile(
                course_id=course.canvas_course_id,
                created_at=now,
                updated_at=now,
            )
            course.profile = profile
            self._repository.add(profile)
        values = update.model_dump()
        changed = any(getattr(profile, key) != value for key, value in values.items())
        for key, value in values.items():
            setattr(profile, key, value)
        if changed or profile.updated_at is None:
            profile.updated_at = now
        self._session.commit()
        self._session.refresh(profile)
        return self._view(course)

    def delete(self, course_id: str) -> None:
        course = self._course(course_id)
        self._repository.delete(course_id)
        course.profile = None
        self._session.commit()

    def effective_context(self, course_id: str) -> EffectiveCourseContext:
        course = self._course(course_id)
        profile = course.profile
        preferences = self._preferences(profile)
        return EffectiveCourseContext(
            course_id=course.canvas_course_id,
            course_name=course.course_name,
            course_code=course.course_code,
            preferences=preferences,
            course_instructions=profile.study_instructions if profile and profile.enabled else None,
            has_custom_profile=profile is not None,
        )

    def _course(self, course_id: str) -> Course:
        normalized = _normalize_canvas_id(course_id, field_name="course id")
        course = self._repository.get_course(normalized)
        if course is None:
            raise CourseNotFoundError(normalized)
        return course

    def _view(self, course: Course) -> CourseProfileView:
        profile = course.profile
        data = CourseProfileData.model_validate(profile, from_attributes=True) if profile else None
        preferences = self._preferences(profile)
        return CourseProfileView(
            course_id=course.canvas_course_id,
            course_name=course.course_name,
            course_code=course.course_code,
            has_custom_profile=profile is not None,
            profile=data,
            effective_preferences=preferences,
            effective_course_instructions=(
                profile.study_instructions if profile and profile.enabled else None
            ),
            created_at=profile.created_at if profile else None,
            updated_at=profile.updated_at if profile else None,
        )

    @staticmethod
    def _preferences(profile: CourseProfile | None) -> CourseStudyPreferences:
        if profile is None:
            return CourseStudyPreferences()
        return CourseStudyPreferences.model_validate(profile, from_attributes=True)

    def _aware_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(UTC)
