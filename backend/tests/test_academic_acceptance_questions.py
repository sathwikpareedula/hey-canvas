"""Deterministic acceptance questions (no live Ollama)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_provider.synthetic import SyntheticAcademicModelProvider
from app.assistant_tools.models import AssistantRequest
from app.assistant_tools.service import AcademicToolService
from app.database.models import Assignment
from sqlalchemy.orm import Session

from tests.services.test_assignment_sync import add_course


def _seed_quiz3(session: Session) -> tuple[str, str]:
    course = add_course(session, "278791", name="Autonomous Robots")
    due = datetime(2026, 10, 20, 21, 0, tzinfo=UTC)  # 4pm Central
    now = datetime.now(UTC)
    session.add(
        Assignment(
            canvas_assignment_id="2393399",
            course_id=course.id,
            name="Quiz 3",
            due_at=due,
            description_html="<p></p>",
            submission_types=["online_quiz"],
            workflow_state="published",
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
    )
    session.commit()
    return course.canvas_course_id, "2393399"


@pytest.fixture
def orchestrator(session: Session) -> AcademicAssistantOrchestrator:
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("America/Chicago"))
    return AcademicAssistantOrchestrator(
        tools,
        SyntheticAcademicModelProvider(),
        retrieval=None,
    )


def test_when_is_quiz3_due_is_fast_and_human(
    session: Session, orchestrator: AcademicAssistantOrchestrator
) -> None:
    course_id, _ = _seed_quiz3(session)
    response = orchestrator.run(
        AssistantRequest(
            query="When is Quiz 3 due?",
            course_id=course_id,
            operation="answer",
        )
    )
    assert response.status == "ok"
    text = response.blocks[0].text or ""
    assert "Quiz 3" in text
    assert "October" in text
    assert "2026" in text
    assert "T" not in text[:40] or "2026-10" not in text


def test_explain_quiz_without_instructions_is_honest(
    session: Session, orchestrator: AcademicAssistantOrchestrator
) -> None:
    course_id, _ = _seed_quiz3(session)
    response = orchestrator.run(
        AssistantRequest(
            query="Explain what Quiz 3 is asking for in plain language.",
            course_id=course_id,
            operation="answer",
        )
    )
    text = (response.blocks[0].text or "").casefold()
    assert "do not explain" in text or "does not explain" in text or "can't verify" in text


def test_study_materials_without_links_is_honest(
    session: Session, orchestrator: AcademicAssistantOrchestrator
) -> None:
    course_id, _ = _seed_quiz3(session)
    response = orchestrator.run(
        AssistantRequest(
            query="Which professor materials should I study for Quiz 3?",
            course_id=course_id,
            operation="answer",
        )
    )
    text = (response.blocks[0].text or "").casefold()
    assert "percolation" not in text
    assert "hoshen" not in text
    assert "does not list" in text or "could not verify" in text or "explicitly linked" in text


def test_streaming_due_date_uses_deterministic_path_without_provider(
    session: Session, orchestrator: AcademicAssistantOrchestrator
) -> None:
    """SSE must not call Ollama for a structured deadline question."""
    from app.assistant_orchestration.models import AssistantEventType

    course_id, _ = _seed_quiz3(session)
    events = list(
        orchestrator.events(
            AssistantRequest(
                query="When is Quiz 3 due?",
                course_id=course_id,
                operation="answer",
            )
        )
    )
    completed = [event for event in events if event.type is AssistantEventType.COMPLETED]
    assert len(completed) == 1
    assert completed[0].response is not None
    assert completed[0].response.status == "ok"
    assert "October" in (completed[0].response.blocks[0].text or "")
    assert not any(event.type is AssistantEventType.ERROR for event in events)


def test_streamed_quiz_answer_has_no_unrelated_material_sources(
    session: Session, orchestrator: AcademicAssistantOrchestrator
) -> None:
    """Empty quiz instructions must not cite random course documents."""
    from app.assistant_orchestration.models import AssistantEventType

    course_id, _ = _seed_quiz3(session)
    events = list(
        orchestrator.events(
            AssistantRequest(
                query="Explain what Quiz 3 is asking for in plain language.",
                course_id=course_id,
                operation="answer",
            )
        )
    )
    completed = next(event for event in events if event.type is AssistantEventType.COMPLETED)
    assert completed.response is not None
    text = (completed.response.blocks[0].text or "").casefold()
    assert "does not explain" in text or "can't verify" in text
    assert not any(event.type is AssistantEventType.SOURCE for event in events)


def test_deterministic_assignment_context_payload_matches_ui_contract(
    session: Session, orchestrator: AcademicAssistantOrchestrator
) -> None:
    """The frontend expects singular assignment/course keys, not nested lists."""
    course_id, assignment_id = _seed_quiz3(session)
    response = orchestrator.run(
        AssistantRequest(query="When is Quiz 3 due?", course_id=course_id)
    )
    blocks = [block for block in response.blocks if block.type == "assignment_context"]
    assert len(blocks) == 1
    payload = blocks[0].payload or {}
    assert payload["assignment"]["canvas_assignment_id"] == assignment_id
    assert payload["course"]["canvas_course_id"] == course_id
    assert payload["course"]["course_name"] == "Autonomous Robots"
