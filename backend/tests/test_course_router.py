from datetime import UTC, datetime

import pytest
from app.course_profiles.models import CourseProfileUpdate
from app.course_router.models import (
    CourseRoutingRequest,
    ResolutionEvidence,
    ResolutionOutcome,
)
from app.database.models import Assignment, Course, CourseModule, ModuleItem
from app.services.course_profiles import CourseProfileService
from app.services.course_router import CourseRouterService


def course(session, course_id: str, name: str) -> Course:
    item = Course(
        canvas_course_id=course_id,
        course_name=name,
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(item)
    session.commit()
    return item


def test_router_prefers_explicit_course_and_resolves_assignment(session):
    first = course(session, "1", "Robotics")
    second = course(session, "2", "Networks")
    session.add(
        Assignment(
            course_id=first.id,
            canvas_assignment_id="a-1",
            name="Homework",
            submission_types=[],
            first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.commit()
    router = CourseRouterService(session)

    explicit = router.resolve(CourseRoutingRequest(course_id="2", assignment_id="a-1"))
    assignment = router.resolve_for_assignment("a-1")

    assert explicit.outcome is ResolutionOutcome.RESOLVED
    assert explicit.course is not None
    assert explicit.course.course_id == "2"
    assert assignment.course is not None
    assert assignment.course.course_id == "1"
    assert ResolutionEvidence.ASSIGNMENT_MEMBERSHIP in assignment.evidence
    assert second.canvas_course_id == "2"


def test_router_matches_enabled_alias_and_rejects_disabled_alias(session):
    course(session, "1", "Robotics and Control")
    service = CourseProfileService(session)
    service.upsert("1", CourseProfileUpdate(display_alias="Robotics"))
    router = CourseRouterService(session)

    result = router.resolve_from_text(" robotics ")
    assert result.outcome is ResolutionOutcome.RESOLVED
    assert result.evidence == (ResolutionEvidence.PROFILE_ALIAS,)

    service.upsert("1", CourseProfileUpdate(display_alias="Robotics", enabled=False))
    disabled = router.resolve_from_text("Robotics")
    assert disabled.outcome is ResolutionOutcome.UNRESOLVED


def test_router_reports_ambiguous_names_and_empty_text(session):
    course(session, "1", "Systems")
    course(session, "2", "systems")
    router = CourseRouterService(session)

    assert router.resolve_from_text("systems").outcome is ResolutionOutcome.AMBIGUOUS
    assert router.resolve_from_text("   ").outcome is ResolutionOutcome.UNRESOLVED


def test_router_normalizes_unicode_and_punctuation_deterministically(session):
    course(session, "1", "Data Structures")
    router = CourseRouterService(session)

    result = router.resolve_from_text("  DATA—STRUCTURES! ")

    assert result.outcome is ResolutionOutcome.RESOLVED
    assert result.course is not None
    assert result.course.course_id == "1"


def test_router_adversarial_inputs_never_guess(session):
    course(session, "0000000000000000000000000000000000000001", "Algorithms")
    course(session, "900719925474099312345678901234567890", "Algorithms II")
    router = CourseRouterService(session)

    assert router.resolve(CourseRoutingRequest()).outcome is ResolutionOutcome.UNRESOLVED
    assert router.resolve_from_text("algorithm").outcome is ResolutionOutcome.AMBIGUOUS
    assert (
        router.resolve(CourseRoutingRequest(course_id="does-not-exist")).outcome
        is ResolutionOutcome.UNRESOLVED
    )
    assert (
        router.resolve(CourseRoutingRequest(course_id="900719925474099312345678901234567890"))
        .course.course_id
        == "900719925474099312345678901234567890"
    )
    with pytest.raises(ValueError):
        CourseRoutingRequest(course_id="   ")


def test_router_resolves_unique_human_course_reference_and_keeps_ambiguity(session):
    course(session, "1", "Autonomous Robot Design and Programming")
    course(session, "2", "Fundamentals of Machine Learning")
    router = CourseRouterService(session)

    robotics = router.resolve_from_text("make me prepared for the next robotics exam")
    assert robotics.outcome is ResolutionOutcome.RESOLVED
    assert robotics.course is not None
    assert robotics.course.course_id == "1"

    course(session, "3", "Robotic Systems Laboratory")
    ambiguous = router.resolve_from_text("help me study robotics")
    assert ambiguous.outcome is ResolutionOutcome.AMBIGUOUS


def test_router_resolves_document_provenance_and_conflicts(session):
    first = course(session, "1", "Documents")
    second = course(session, "2", "Other")
    module = CourseModule(
        course_id=first.id,
        canvas_module_id="module-1",
        prerequisite_module_ids=[],
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    module.items.append(
        ModuleItem(
            course_id=first.id,
            canvas_module_item_id="item-1",
            item_type="File",
            content_id="file-1",
            first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.add(module)
    session.commit()
    router = CourseRouterService(session)

    document = router.resolve_for_document("file-1")
    assert document.outcome is ResolutionOutcome.RESOLVED
    assert document.evidence == (ResolutionEvidence.DOCUMENT_PROVENANCE,)
    conflict = router.resolve(
        CourseRoutingRequest(document_id="file-1", course_id=second.canvas_course_id)
    )
    assert conflict.outcome is ResolutionOutcome.RESOLVED
    assert conflict.course is not None
    assert conflict.course.course_id == "2"
