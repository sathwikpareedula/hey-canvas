from datetime import UTC, datetime

import pytest
from app.database.models import Course
from app.workspaces.models import WorkspaceUpdate
from app.workspaces.service import WorkspaceService


def test_workspace_is_course_scoped_and_has_bounded_continuity(session) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session.add(
        Course(
            canvas_course_id="course-1",
            course_name="Biology",
            workflow_state="available",
            enrollment_state="active",
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
    )
    session.commit()
    service = WorkspaceService(session)

    created = service.get_or_create("biology", course_id="course-1")
    assert created.course_id == "course-1"
    updated = service.update(
        "biology",
        WorkspaceUpdate(
            recent_entities=({"kind": "assignment", "id": "a1"},),
            recent_intent="study_help",
        ),
    )
    assert updated.recent_entities[0]["id"] == "a1"
    assert service.list(course_id="course-1")[0].workspace_key == "biology"


def test_workspace_rejects_unknown_course_and_unknown_update(session) -> None:
    service = WorkspaceService(session)
    with pytest.raises(LookupError):
        service.get_or_create("missing", course_id="not-local")
    with pytest.raises(LookupError):
        service.update("missing", WorkspaceUpdate(display_name="x"))


def test_document_continuity_respects_explicit_course_scope(session) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for course_id in ("course-1", "course-2"):
        session.add(
            Course(
                canvas_course_id=course_id,
                course_name=course_id,
                workflow_state="available",
                enrollment_state="active",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            )
        )
    session.commit()
    service = WorkspaceService(session)
    service.remember_entity(
        "conversation-1",
        kind="document",
        entity_id="file-6",
        label="Lecture 6",
        course_id="course-1",
        intent="document_context",
    )

    assert service.resolve_document("conversation-1", "quiz me on it") == "file-6"
    assert (
        service.resolve_document(
            "conversation-1", "quiz me on it", course_id="course-2"
        )
        is None
    )


def test_assignment_continuity_respects_explicit_course_scope(session) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for course_id in ("course-1", "course-2"):
        session.add(
            Course(
                canvas_course_id=course_id,
                course_name=course_id,
                workflow_state="available",
                enrollment_state="active",
                first_seen_at=now,
                last_seen_at=now,
                last_synced_at=now,
            )
        )
    session.commit()
    service = WorkspaceService(session)
    service.remember_entity(
        "conversation-1",
        kind="assignment",
        entity_id="assignment-1",
        label="Project report",
        course_id="course-1",
        intent="assignment_context",
    )

    assert service.resolve_assignment("conversation-1", "that assignment") == "assignment-1"
    assert (
        service.resolve_assignment(
            "conversation-1", "that assignment", course_id="course-2"
        )
        is None
    )
