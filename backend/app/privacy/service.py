"""Explicit privacy and course-policy persistence."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Course, CourseAIPolicy, PrivacySetting
from app.privacy.models import (
    CourseAIPolicyUpdate,
    CourseAIPolicyValue,
    CourseAIPolicyView,
    PrivacyMode,
    PrivacySettingsUpdate,
    PrivacySettingsView,
)


class PrivacyService:
    def __init__(self, session: Session, *, user_key: str = "local-user") -> None:
        if not user_key or len(user_key) > 100:
            raise ValueError("user_key is invalid")
        self._session = session
        self._user_key = user_key

    def settings(self) -> PrivacySettingsView:
        record = self._session.scalar(
            select(PrivacySetting).where(PrivacySetting.user_key == self._user_key)
        )
        if record is None:
            record = PrivacySetting(
                user_key=self._user_key,
                mode=PrivacyMode.LOCAL_ONLY.value,
                updated_at=datetime.now(UTC),
            )
            self._session.add(record)
            self._session.commit()
        return PrivacySettingsView(
            user_key=self._user_key,
            mode=PrivacyMode(record.mode),
            updated_at=record.updated_at,
        )

    def update_settings(self, request: PrivacySettingsUpdate) -> PrivacySettingsView:
        self.settings()
        record = self._session.scalar(
            select(PrivacySetting).where(PrivacySetting.user_key == self._user_key)
        )
        if record is None:
            raise RuntimeError("privacy settings could not be persisted")
        record.mode = request.mode.value
        record.updated_at = datetime.now(UTC)
        self._session.commit()
        return self.settings()

    def policy(self, course_id: str) -> CourseAIPolicyView:
        record = self._session.scalar(
            select(CourseAIPolicy).where(
                CourseAIPolicy.user_key == self._user_key,
                CourseAIPolicy.course_id == course_id,
            )
        )
        if record is None:
            return CourseAIPolicyView(
                course_id=course_id,
                policy=CourseAIPolicyValue.UNKNOWN,
                provider_mode=PrivacyMode.LOCAL_ONLY,
                notes=None,
                updated_at=datetime.now(UTC),
            )
        return self._policy_view(record)

    def set_policy(self, course_id: str, request: CourseAIPolicyUpdate) -> CourseAIPolicyView:
        if self._session.scalar(
            select(Course).where(Course.canvas_course_id == course_id)
        ) is None:
            raise LookupError("course was not found locally")
        record = self._session.scalar(
            select(CourseAIPolicy).where(
                CourseAIPolicy.user_key == self._user_key,
                CourseAIPolicy.course_id == course_id,
            )
        )
        now = datetime.now(UTC)
        if record is None:
            record = CourseAIPolicy(
                user_key=self._user_key,
                course_id=course_id,
                policy=request.policy.value,
                provider_mode=request.provider_mode.value.lower(),
                notes=request.notes,
                updated_at=now,
            )
            self._session.add(record)
        else:
            record.policy = request.policy.value
            record.provider_mode = request.provider_mode.value.lower()
            record.notes = request.notes
            record.updated_at = now
        self._session.commit()
        return self._policy_view(record)

    @staticmethod
    def _policy_view(record: CourseAIPolicy) -> CourseAIPolicyView:
        return CourseAIPolicyView(
            course_id=record.course_id,
            policy=CourseAIPolicyValue(record.policy),
            provider_mode=PrivacyMode(record.provider_mode.upper()),
            notes=record.notes,
            updated_at=record.updated_at,
        )
