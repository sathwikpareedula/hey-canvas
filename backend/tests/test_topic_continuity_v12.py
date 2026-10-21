"""Session/course-isolated, TTL-bounded concept continuation regressions."""

import time

from app.assistant_orchestration.models import (
    AssistantModelInput,
    AssistantOperation,
    ToolPlan,
)
from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_orchestration.topic_continuity import ConceptContinuity
from app.assistant_tools.models import AssistantRequest


def _input(query: str, session_id: str, course_id: str) -> AssistantModelInput:
    return AssistantModelInput.model_construct(
        request=AssistantRequest(query=query, session_id=session_id, course_id=course_id),
        plan=ToolPlan(operation=AssistantOperation.STUDY_HELP, course_id=course_id, query=query),
        context=None,
    )


def test_example_followup_uses_latest_concept_not_stale_course_topic(monkeypatch):
    from app.assistant_orchestration import service

    cache = ConceptContinuity()
    monkeypatch.setattr(service, "concept_continuity", cache)
    first = _input("Explain robot path planning including A* search", "session-one", "robotics")
    assert AcademicAssistantOrchestrator._conceptual_provider_input(first) is first

    follow_up = _input("Can you give me a simple example?", "session-one", "robotics")
    output = AcademicAssistantOrchestrator._conceptual_provider_input(follow_up)
    assert "A* search" in output.request.query
    assert "forward kinematics" not in output.request.query
    assert follow_up.request.query == "Can you give me a simple example?"


def test_pronoun_followups_preserve_topic_within_same_session_and_course(monkeypatch):
    from app.assistant_orchestration import service

    cache = ConceptContinuity()
    monkeypatch.setattr(service, "concept_continuity", cache)
    first = _input("Explain A* search.", "session-one", "robotics")
    AcademicAssistantOrchestrator._conceptual_provider_input(first)

    for query in ("What is its time complexity?", "How does it handle obstacles?"):
        follow_up = _input(query, "session-one", "robotics")
        output = AcademicAssistantOrchestrator._conceptual_provider_input(follow_up)
        assert "Explain A* search" in output.request.query

    for session_id, course_id in (("other-session", "robotics"), ("session-one", "ml")):
        follow_up = _input("What is its time complexity?", session_id, course_id)
        assert AcademicAssistantOrchestrator._conceptual_provider_input(follow_up) is follow_up


def test_concept_continuity_isolates_sessions_and_courses(monkeypatch):
    from app.assistant_orchestration import service

    cache = ConceptContinuity()
    monkeypatch.setattr(service, "concept_continuity", cache)
    AcademicAssistantOrchestrator._conceptual_provider_input(
        _input("Explain robot path planning including A* search", "s1", "robotics")
    )
    for session_id, course_id in (("s2", "robotics"), ("s1", "machine-learning")):
        item = _input("Give me a simple example", session_id, course_id)
        assert AcademicAssistantOrchestrator._conceptual_provider_input(item) is item


def test_concept_cache_is_bounded_and_expires():
    cache = ConceptContinuity(ttl_seconds=0.01, max_entries=2)
    for key in ("s1", "s2", "s3"):
        cache.remember(key, "c1", "Explain A* search")
    assert cache.recall("s1", "c1") is None
    assert cache.recall("s3", "c1") is not None
    time.sleep(0.02)
    assert cache.recall("s3", "c1") is None


def test_assignment_turn_clears_stale_concept_before_deterministic_return(monkeypatch):
    from app.assistant_orchestration import service

    cache = ConceptContinuity()
    monkeypatch.setattr(service, "concept_continuity", cache)
    concept = _input("Explain A* search", "session-one", "robotics")
    AcademicAssistantOrchestrator._conceptual_provider_input(concept)
    assert cache.recall("session-one", "robotics") is not None

    assignment = _input("What is Homework 3 asking me to do?", "session-one", "robotics")
    AcademicAssistantOrchestrator._clear_stale_concept(assignment)
    followup = _input("Can you give me a simple example?", "session-one", "robotics")
    assert AcademicAssistantOrchestrator._conceptual_provider_input(followup) is followup


def test_subject_switch_preserves_current_concept_and_isolation(monkeypatch):
    from app.assistant_orchestration import service

    cache = ConceptContinuity()
    monkeypatch.setattr(service, "concept_continuity", cache)
    for course, session in (("robotics", "s1"), ("robotics", "s2"), ("machine-learning", "s1")):
        AcademicAssistantOrchestrator._conceptual_provider_input(
            _input("Explain A* search", session, course)
        )
    AcademicAssistantOrchestrator._conceptual_provider_input(
        _input("Explain relative-angle forward kinematics", "s1", "robotics")
    )
    followup = AcademicAssistantOrchestrator._conceptual_provider_input(
        _input("Give me a simple example", "s1", "robotics")
    )
    assert "relative-angle forward kinematics" in followup.request.query
    assert "A* search" not in followup.request.query

    AcademicAssistantOrchestrator._clear_stale_concept(
        _input("When is Homework 3 due?", "s1", "robotics")
    )
    assert cache.recall("s1", "robotics") is None
    assert cache.recall("s2", "robotics") is not None
    assert cache.recall("s1", "machine-learning") is not None

    # New conversation has a distinct session id and cannot reuse prior subjects.
    new_conversation = _input("Give me a simple example", "new-session", "robotics")
    assert (
        AcademicAssistantOrchestrator._conceptual_provider_input(new_conversation)
        is new_conversation
    )


def test_bfs_dfs_fundamentals_use_bounded_general_knowledge() -> None:
    model_input = _input(
        "What are the core differences between BFS and DFS for state space exploration?",
        "search-session",
        "ai-course",
    )
    response = AcademicAssistantOrchestrator._graph_search_concept_answer(model_input)

    assert response is not None
    rendered = response.model_dump_json().casefold()
    assert "fifo queue" in rendered
    assert "lifo stack" in rendered
    assert "not verified course coverage" in rendered


def test_astar_answer_and_followup_are_fast_and_course_isolated(monkeypatch) -> None:
    from app.assistant_orchestration import service

    cache = ConceptContinuity()
    monkeypatch.setattr(service, "concept_continuity", cache)
    first = _input(
        "Explain robot path planning including the A* search algorithm.",
        "astar-session",
        "robotics",
    )
    response = AcademicAssistantOrchestrator._graph_search_concept_answer(first)
    assert response is not None
    assert "f(n) = g(n) + h(n)" in response.model_dump_json()

    follow_up = _input("Can you give me a simple example?", "astar-session", "robotics")
    example = AcademicAssistantOrchestrator._graph_search_concept_answer(follow_up)
    assert example is not None
    assert "Manhattan distance" in example.model_dump_json()

    other_course = _input("Can you give me a simple example?", "astar-session", "ml")
    assert AcademicAssistantOrchestrator._graph_search_concept_answer(other_course) is None


def test_inadmissible_heuristic_loses_optimality_guarantee() -> None:
    model_input = _input(
        "What happens if the heuristic is not admissible; is the path still optimal?",
        "astar-session",
        "robotics",
    )
    response = AcademicAssistantOrchestrator._graph_search_concept_answer(model_input)

    assert response is not None
    rendered = response.model_dump_json().casefold()
    assert "overestimates" in rendered
    assert "optimality guarantee is lost" in rendered
