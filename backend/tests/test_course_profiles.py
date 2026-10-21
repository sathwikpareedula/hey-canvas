from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest
from app.course_profiles.models import (
    AnswerStyle,
    CourseProfileUpdate,
    DetailPreference,
    ExplanationStyle,
    StartingLevel,
    TeachingDepth,
)
from app.database.models import Course
from app.database.session import get_session
from app.main import app
from app.services.course_profiles import (
    CourseNotFoundError,
    CourseProfileService,
)


def add_course(session, course_id: str = "9007199254740993", name: str = "Robotics") -> Course:
    course = Course(
        canvas_course_id=course_id,
        course_name=name,
        course_code="CSE-0001",
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(course)
    session.commit()
    return course


def test_absent_profile_returns_global_defaults(session):
    add_course(session)

    result = CourseProfileService(session).get("9007199254740993")

    assert result.has_custom_profile is False
    assert result.profile is None
    assert result.effective_preferences.teaching_depth is TeachingDepth.BALANCED
    assert result.effective_preferences.starting_level is StartingLevel.COURSE_CONTEXT
    assert result.effective_course_instructions is None


def test_create_update_and_persist_profile(session, session_factory):
    add_course(session)

    def clock() -> datetime:
        return datetime(2026, 2, 1, tzinfo=UTC)
    payload = CourseProfileUpdate(
        display_alias="Robotics",
        teaching_depth=TeachingDepth.DETAILED,
        starting_level=StartingLevel.ZERO_KNOWLEDGE,
        explanation_style=ExplanationStyle.STEP_BY_STEP,
        answer_style=AnswerStyle.EXAM_STYLE,
        step_by_step=True,
        exam_style=True,
        math_detail=DetailPreference.DETAILED,
        study_instructions="Use the course notation.",
    )

    created = CourseProfileService(session, clock=clock).upsert(
        "9007199254740993", payload
    )
    assert created.has_custom_profile is True
    assert created.profile is not None
    assert created.profile.display_alias == "Robotics"
    assert created.effective_preferences.starting_level is StartingLevel.ZERO_KNOWLEDGE

    with session_factory() as second_session:
        persisted = CourseProfileService(second_session).get("9007199254740993")
        assert persisted.profile is not None
        assert persisted.profile.study_instructions == "Use the course notation."


def test_equivalent_update_is_deterministic(session):
    add_course(session)
    clock_values = iter(
        [
            datetime(2026, 2, 1, tzinfo=UTC),
            datetime(2026, 2, 2, tzinfo=UTC),
        ]
    )
    payload = CourseProfileUpdate(display_alias="R")

    def clock() -> datetime:
        return next(clock_values)

    service = CourseProfileService(session, clock=clock)

    first = service.upsert("9007199254740993", payload)
    second = service.upsert("9007199254740993", payload)

    assert first.created_at == second.created_at
    assert second.updated_at == first.updated_at


def test_delete_profile_preserves_canvas_course(session):
    course = add_course(session)
    service = CourseProfileService(session)
    service.upsert("9007199254740993", CourseProfileUpdate(display_alias="R"))

    service.delete("9007199254740993")

    assert service.get("9007199254740993").has_custom_profile is False
    assert session.get(Course, course.id) is not None


def test_unknown_course_is_safe(session):
    with pytest.raises(CourseNotFoundError):
        CourseProfileService(session).get("does-not-exist")
    with pytest.raises(CourseNotFoundError):
        CourseProfileService(session).upsert("does-not-exist", CourseProfileUpdate())


def test_profile_validation_bounds_untrusted_text():
    with pytest.raises(ValueError):
        CourseProfileUpdate(display_alias="x" * 256)
    with pytest.raises(ValueError):
        CourseProfileUpdate(study_instructions="x" * 4001)


def test_effective_context_does_not_expose_disabled_instructions(session):
    add_course(session)
    service = CourseProfileService(session)
    service.upsert(
        "9007199254740993",
        CourseProfileUpdate(study_instructions="user data", enabled=False),
    )

    context = service.effective_context("9007199254740993")

    assert context.has_custom_profile is True
    assert context.course_instructions is None
    assert context.course_id == "9007199254740993"


def test_opaque_ids_remain_strings(session):
    add_course(session, "0000000000000000000000000000000000000001", "Unicode ∑ Course")

    result = CourseProfileService(session).get("0000000000000000000000000000000000000001")

    assert result.course_id == "0000000000000000000000000000000000000001"
    assert result.course_name == "Unicode ∑ Course"


@pytest.mark.asyncio
async def test_local_api_returns_defaults_and_validates_unknown_course(session):
    add_course(session)

    def override_session() -> Iterator:
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/api/course-profiles/9007199254740993")
            assert response.status_code == 200
            assert response.json()["has_custom_profile"] is False

            update = await client.put(
                "/api/course-profiles/9007199254740993",
                json={"display_alias": "Robotics", "exam_style": True},
            )
            assert update.status_code == 200
            assert update.json()["profile"]["display_alias"] == "Robotics"

            missing = await client.get("/api/course-profiles/unknown")
            assert missing.status_code == 404
    finally:
        app.dependency_overrides.clear()
