from datetime import UTC, datetime

import pytest
from app.course_profiles.models import CourseProfileUpdate
from app.database.models import Course
from app.services.course_profiles import CourseNotFoundError, CourseProfileService
from app.services.study_context import StudyContextService
from app.study_context.models import StudyContextUpdate, StudyMode
from sqlalchemy import text


def add_course(session, course_id: str = "9007199254740993") -> None:
    session.add(
        Course(
            canvas_course_id=course_id,
            course_name="Study Course",
            first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.commit()


def test_absent_context_has_safe_defaults(session):
    add_course(session)

    result = StudyContextService(session).get("9007199254740993")

    assert result.has_context is False
    assert result.study_mode is StudyMode.BALANCED
    assert result.concepts_covered == []


def test_update_persists_and_reset_preserves_course(session, session_factory):
    add_course(session)
    payload = StudyContextUpdate(
        current_topic="Backpropagation",
        study_mode=StudyMode.PRACTICE,
        concepts_covered=["gradients", "epochs"],
        topics_to_revisit=["activation functions"],
        study_note="Review the chain rule.",
    )

    result = StudyContextService(session).update("9007199254740993", payload)
    assert result.has_context is True
    assert result.study_mode is StudyMode.PRACTICE

    with session_factory() as second:
        persisted = StudyContextService(second).get("9007199254740993")
        assert persisted.study_note == "Review the chain rule."

    StudyContextService(session).reset("9007199254740993")
    assert StudyContextService(session).get("9007199254740993").has_context is False


def test_update_replaces_previous_state_and_preserves_opaque_unicode_values(session):
    add_course(session)
    service = StudyContextService(
        session, clock=lambda: datetime(2026, 2, 1, 12, tzinfo=UTC)
    )
    service.update(
        "9007199254740993",
        StudyContextUpdate(
            current_topic="Eigenvalues ∑",
            concepts_covered=["矩阵", "gradients"],
            topics_to_revisit=["proofs"],
        ),
    )
    updated = StudyContextService(
        session, clock=lambda: datetime(2026, 2, 2, 12, tzinfo=UTC)
    ).update(
        "9007199254740993",
        StudyContextUpdate(current_topic="Fourier", concepts_covered=["signals"]),
    )

    assert updated.current_topic == "Fourier"
    assert updated.concepts_covered == ["signals"]
    assert updated.topics_to_revisit == []
    assert updated.created_at == datetime(2026, 2, 1, 12, tzinfo=UTC)
    assert updated.updated_at == datetime(2026, 2, 2, 12, tzinfo=UTC)
    assert updated.model_dump(mode="json") == StudyContextService(
        session
    ).get("9007199254740993").model_dump(mode="json")


def test_course_delete_cascades_profile_and_study_context(session):
    add_course(session)

    CourseProfileService(session).upsert(
        "9007199254740993", CourseProfileUpdate(display_alias="Study")
    )
    StudyContextService(session).update(
        "9007199254740993", StudyContextUpdate(current_topic="Cascade")
    )

    session.delete(session.query(Course).one())
    session.commit()

    assert session.query(Course).count() == 0
    assert session.execute(text("SELECT COUNT(*) FROM course_profiles")).scalar_one() == 0
    assert session.execute(text("SELECT COUNT(*) FROM study_contexts")).scalar_one() == 0


def test_unknown_and_over_bound_context_are_rejected(session):
    with pytest.raises(CourseNotFoundError):
        StudyContextService(session).get("missing")
    with pytest.raises(ValueError):
        StudyContextUpdate(concepts_covered=[str(index) for index in range(21)])
    with pytest.raises(ValueError):
        StudyContextUpdate(study_note="x" * 2001)


def test_duplicate_items_and_invalid_mode_are_rejected():
    with pytest.raises(ValueError):
        StudyContextUpdate(concepts_covered=["same", "same"])
    with pytest.raises(ValueError):
        StudyContextUpdate(study_mode="invented")
