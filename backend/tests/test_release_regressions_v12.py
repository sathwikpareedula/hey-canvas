"""Targeted regressions for defects found by the V1.2 synthetic-student campaign."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_tools.deterministic_answers import due_clause
from app.assistant_tools.models import AssistantRequest
from app.assistant_tools.operational_answers import (
    build_no_evidence_answer,
    build_sync_status_answer,
    sync_caveat,
)
from app.assistant_tools.question_intent import (
    AcademicQuestionIntent,
    _one_edit_apart,
    classify_academic_question,
    normalize_question,
)
from app.assistant_tools.service import AcademicToolService
from app.services.retrieval_query_focus import focused_retrieval_query
from sqlalchemy.orm import Session

from tests.acceptance.harness import RaisingProvider
from tests.test_academic_correctness_v12 import _add_assignment
from tests.services.test_assignment_sync import add_course

CHICAGO = ZoneInfo("America/Chicago")
NOW = datetime(2026, 10, 15, 15, 0, tzinfo=UTC)


def _text(response: object) -> str:
    return " ".join(b.text or "" for b in response.blocks)  # type: ignore[attr-defined]


def test_missing_due_date_reads_as_a_sentence() -> None:
    clause = due_clause(None, timezone=CHICAGO)
    assert clause == "has no due date listed in Canvas"
    assert "is due" not in clause
    assert due_clause(NOW, timezone=CHICAGO).startswith("is due October 15, 2026")


@pytest.mark.parametrize(
    ("typo", "fixed"),
    [("dedline", "deadline"), ("assigment", "assignment"), ("sumarize", "summarize")],
)
def test_single_edit_typos_are_repaired(typo: str, fixed: str) -> None:
    assert fixed in normalize_question(f"what is my {typo}")


def test_typo_repair_does_not_rewrite_unrelated_words() -> None:
    query = "explain the thermodynamic cycle for the exam review"
    assert normalize_question(query) == query
    assert not _one_edit_apart("quiz", "quiz")
    assert not _one_edit_apart("lecture", "lectures and more")


def test_typo_still_routes_to_deadline_intent() -> None:
    plain = classify_academic_question("what is due tomorrow?")
    typo = classify_academic_question("what is due tomorow?")
    assert typo == plain
    assert plain is not AcademicQuestionIntent.GENERAL_STUDY


def test_sync_caveat_states() -> None:
    assert sync_caveat(None, now=NOW) is None
    assert sync_caveat({"status": "not_run"}, now=NOW) is None
    assert "failed" in (sync_caveat({"status": "failed"}, now=NOW) or "")
    assert "partly" in (sync_caveat({"status": "partially_succeeded"}, now=NOW) or "")
    fresh = {"status": "succeeded", "finished_at": (NOW - timedelta(hours=2)).isoformat()}
    assert sync_caveat(fresh, now=NOW) is None
    stale = {"status": "succeeded", "finished_at": (NOW - timedelta(days=5)).isoformat()}
    assert "out of date" in (sync_caveat(stale, now=NOW) or "")


def test_sync_status_never_looks_healthy_after_failure() -> None:
    text = _text(build_sync_status_answer({"status": "failed"}, now=NOW, timezone=CHICAGO))
    assert "failed" in text.casefold()
    assert "up to date" not in text.casefold()


def test_no_evidence_answer_is_explicit_about_unreadable_files() -> None:
    text = _text(build_no_evidence_answer(course_name="Algorithms", unreadable_titles=["Scan 1"]))
    assert "Algorithms" in text and "Scan 1" in text
    assert "contents are unknown" in text
    assert "which course" in _text(build_no_evidence_answer(course_name=None, unreadable_titles=[]))


def test_lecture_summary_query_keeps_only_discriminative_terms() -> None:
    focused = focused_retrieval_query("summarize the professor lecture on graph traversal")
    assert "professor" not in focused and "summarize" not in focused
    assert "graph" in focused
    assert focused_retrieval_query("what did lecture 7 cover") == "lecture 7"
    assert focused_retrieval_query("notes from the lecture about sensors") == "sensors"
    assert focused_retrieval_query("what did lecture slides cover") != "lecture slides"


@pytest.mark.parametrize(
    "error", [TimeoutError("model timed out"), ConnectionError("refused"), RuntimeError("boom")]
)
def test_provider_failures_fall_back_to_a_grounded_answer(
    session: Session, error: Exception
) -> None:
    course = add_course(session, "801", name="Algorithms")
    _add_assignment(
        session,
        course.id,
        "9001",
        "Project 2",
        due=datetime.now(UTC) + timedelta(days=3),
        description_html=None,
        points=40,
    )
    tools = AcademicToolService(session, academic_timezone=CHICAGO)
    orchestrator = AcademicAssistantOrchestrator(tools, RaisingProvider(error), retrieval=None)
    request = AssistantRequest(
        query="Why is this important for the final?", course_id="801", operation="answer"
    )

    response = orchestrator.run(request)
    events = list(orchestrator.events(request))

    assert response.status in {"ok", "error"}
    assert _text(response)
    assert "Traceback" not in _text(response)
    assert events and events[-1].type in {"completed", "error"}
    assert sum(e.type in {"completed", "error"} for e in events) == 1


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("INTERNAL_SECRET_DETAIL"),
        ConnectionError("INTERNAL_SECRET_DETAIL"),
        TimeoutError("INTERNAL_SECRET_DETAIL"),
    ],
)
def test_provider_exception_details_and_class_are_not_exposed(
    session: Session, error: Exception
) -> None:
    """Provider failures without grounded evidence must not expose internal details."""
    tools = AcademicToolService(session, academic_timezone=CHICAGO)
    orchestrator = AcademicAssistantOrchestrator(tools, RaisingProvider(error), retrieval=None)
    request = AssistantRequest(
        query="Explain a topic with no available course material", operation="answer"
    )

    response = orchestrator.run(request)
    visible = _text(response)
    assert response.status == "error"
    assert visible == "assistant provider is temporarily unavailable"
    assert "INTERNAL_SECRET_DETAIL" not in visible
    assert type(error).__name__ not in visible


def test_deterministic_path_does_not_call_the_model(session: Session) -> None:
    course = add_course(session, "802", name="Databases")
    _add_assignment(
        session,
        course.id,
        "9002",
        "Quiz 3",
        due=NOW + timedelta(days=1),
        description_html=None,
    )
    provider = RaisingProvider(RuntimeError("must not be called"))
    orchestrator = AcademicAssistantOrchestrator(
        AcademicToolService(session, academic_timezone=CHICAGO), provider, retrieval=None
    )
    response = orchestrator.run(
        AssistantRequest(query="When is Quiz 3 due?", course_id="802", operation="answer")
    )
    assert provider.calls == 0
    assert "has no due date" not in _text(response)
    assert "Central" in _text(response) or "CDT" in _text(response) or "CST" in _text(response)


class _ForeignCourseRetrieval:
    """Hostile/buggy retriever that returns evidence belonging to another course."""

    MARKER = "foreign-course-secret-marker"

    def evidence_for(self, *, course_id: str, query: str):  # type: ignore[no-untyped-def]
        from app.assistant_tools.models import DocumentEvidence

        return (
            DocumentEvidence(
                canvas_file_id="foreign-file",
                canvas_course_id="not-" + course_id,
                display_name="Other Course Notes",
                filename="other.pdf",
                unit_type="page",
                unit_index=0,
                page_number=1,
                slide_number=None,
                heading=None,
                excerpt=f"{self.MARKER} lecture summary",
                is_stale=False,
            ),
        )


def test_foreign_course_evidence_never_reaches_answers_or_the_model(session: Session) -> None:
    add_course(session, "803", name="Compilers")
    provider = RaisingProvider(RuntimeError("model unavailable"))
    orchestrator = AcademicAssistantOrchestrator(
        AcademicToolService(session, academic_timezone=CHICAGO),
        provider,
        retrieval=_ForeignCourseRetrieval(),
    )
    request = AssistantRequest(
        query="Summarize the professor lecture", course_id="803", operation="answer"
    )
    outputs: list[str] = []
    for attempt in (
        lambda: _text(orchestrator.run(request)),
        lambda: " ".join(str(e.model_dump()) for e in orchestrator.events(request)),
    ):
        try:
            outputs.append(attempt())
        except ValueError as exc:  # fail closed: a refusal, never a leak
            outputs.append(str(exc))
    for visible in outputs:
        assert _ForeignCourseRetrieval.MARKER not in visible
        assert "Other Course Notes" not in visible


def test_legacy_study_mode_in_database_does_not_break_course_chat(session: Session) -> None:
    """Found by browser E2E: the demo fixture stored study_mode='learn', which the
    public StudyMode enum rejects, so every course-scoped chat failed."""
    from app.database.models import StudyContext
    from app.services.study_context import StudyContextService
    from sqlalchemy import select

    course = add_course(session, "804", name="Robotics")
    now = datetime.now(UTC)
    session.add(
        StudyContext(
            course_id=course.canvas_course_id,
            study_mode="learn",
            concepts_covered=[],
            topics_to_revisit=[],
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    assert session.scalar(select(StudyContext.study_mode)) == "learn"

    view = StudyContextService(session).get("804")
    assert view.study_mode.value == "balanced"

    _add_assignment(
        session, course.id, "9004", "Worksheet", due=None, description_html=None, points=25
    )
    tools = AcademicToolService(session, academic_timezone=CHICAGO)
    orchestrator = AcademicAssistantOrchestrator(
        tools, RaisingProvider(RuntimeError("unused")), retrieval=None
    )
    text = _text(
        orchestrator.run(
            AssistantRequest(
                query="How many points is Worksheet worth?", course_id="804", operation="answer"
            )
        )
    )
    assert "25" in text


def test_seeded_demo_fixture_uses_only_valid_study_modes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from app.dev_fixture import seed_synthetic_fixture
    from app.study_context.models import StudyMode
    from sqlalchemy import create_engine, select
    from app.database.models import StudyContext

    database = tmp_path / "demo.db"
    seed_synthetic_fixture(database)
    with Session(create_engine(f"sqlite:///{database}")) as demo:
        modes = set(demo.scalars(select(StudyContext.study_mode)))
    assert modes and modes <= {m.value for m in StudyMode}
