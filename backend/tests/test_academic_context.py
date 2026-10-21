from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest
from app.academic_context.models import ContextAuthority
from app.course_profiles.models import CourseProfileUpdate, TeachingDepth
from app.course_router.models import CourseRoutingRequest
from app.database.models import Course
from app.database.session import get_session
from app.main import app
from app.services.academic_context import AcademicContextService
from app.services.course_profiles import CourseProfileService
from app.services.study_context import StudyContextService
from app.study_context.models import StudyContextUpdate


def add_course(session, course_id: str = "1") -> None:
    session.add(
        Course(
            canvas_course_id=course_id,
            course_name="Context Course",
            course_code="CTX",
            first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.commit()


def test_context_composes_defaults_profile_and_study_state(session):
    add_course(session)
    CourseProfileService(session).upsert(
        "1", CourseProfileUpdate(teaching_depth=TeachingDepth.DETAILED)
    )
    StudyContextService(session).update(
        "1", StudyContextUpdate(current_topic="Composition")
    )

    context = AcademicContextService(session).build(
        CourseRoutingRequest(course_id="1")
    )

    assert context is not None
    assert context.profile_preferences.teaching_depth is TeachingDepth.DETAILED
    assert context.study_context.current_topic == "Composition"
    assert context.retrieval.available is False
    assert context.retrieval.authority is ContextAuthority.FUTURE_RETRIEVAL


def test_ambiguous_router_result_cannot_be_composed(session):
    add_course(session, "1")
    add_course(session, "2")
    session.get(Course, 2).course_name = "Context Course"
    session.commit()

    context = AcademicContextService(session).build(
        CourseRoutingRequest(text="context course")
    )

    assert context is None


@pytest.mark.asyncio
async def test_academic_context_api_exposes_stable_frontend_contract(session):
    add_course(session)
    CourseProfileService(session).upsert(
        "1", CourseProfileUpdate(display_alias="Context")
    )

    def override_session() -> Iterator:
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/academic-context/resolve",
                json={"course_id": "1"},
            )

        assert response.status_code == 200
        assert response.json() == {
            "course_id": "1",
            "course_name": "Context Course",
            "course_code": "CTX",
            "routing_evidence": ["explicit_course"],
            "profile_preferences": {
                "teaching_depth": "balanced",
                "starting_level": "course_context",
                "explanation_style": "concept_first",
                "answer_style": "balanced",
                "step_by_step": None,
                "exam_style": False,
                "visual_preference": "auto",
                "math_detail": "auto",
                "code_detail": "auto",
            },
            "course_instructions": None,
            "study_context": {
                "course_id": "1",
                "course_name": "Context Course",
                "has_context": False,
                "created_at": None,
                "updated_at": None,
                "current_topic": None,
                "assignment_id": None,
                "study_mode": "balanced",
                "starting_point": None,
                "concepts_covered": [],
                "topics_to_revisit": [],
                "study_note": None,
            },
            "retrieval": {
                "available": False,
                "authority": "future_retrieval",
            },
        }
    finally:
        app.dependency_overrides.clear()
