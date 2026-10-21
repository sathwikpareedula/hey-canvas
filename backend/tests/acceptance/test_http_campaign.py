"""HTTP + SSE campaign: the same fixture truth must hold over the real FastAPI routes."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from app.api.routes import assistant as assistant_routes
from app.assistant_provider.synthetic import SyntheticAcademicModelProvider
from app.config import get_settings
from app.database.models import Base
from app.database.session import enable_sqlite_foreign_keys, get_session
from app.main import app
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from tests.acceptance.conftest import CAMPAIGN_RESULTS
from tests.acceptance.harness import fmt_due, invariant_violations
from tests.acceptance.student_factory import StudentProfile, build_student, seed_student

HTTP_SEED = 31337
HTTP_STUDENTS = 30
BASE = "http://127.0.0.1:8000"
LEAK = "credential-marker C:\\private\\academic.db"


def _profile(index: int) -> StudentProfile:
    # The routes use the real clock and the configured academic timezone.
    return build_student(
        HTTP_SEED, index, tz_name=get_settings().academic_timezone, now=datetime.now(UTC)
    )


def _world(
    profile: StudentProfile, *, database_path: str | None = None
) -> tuple[sessionmaker[Session], Any]:
    """In-memory world, or a file-backed one (separate connection per session).

    Concurrent tests must use ``database_path``: a StaticPool shares one sqlite
    connection between worker threads, which is not safe (it can segfault).
    """
    if database_path is None:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    else:
        engine = create_engine(
            f"sqlite:///{database_path}", connect_args={"check_same_thread": False}
        )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed_student(session, profile)
    return factory, engine


def _client(*, raise_app_exceptions: bool = True) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions),
        base_url=BASE,
    )


def _sse(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for chunk in text.split("\n\n"):
        for line in chunk.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def _text(blocks: list[dict[str, Any]]) -> str:
    return "\n".join(b["text"] for b in blocks if b.get("text"))


@pytest.mark.asyncio
@pytest.mark.parametrize("index", range(HTTP_STUDENTS))
async def test_http_and_sse_agree_with_fixture_truth(index: int, install) -> None:  # type: ignore[no-untyped-def]
    profile = _profile(index)
    factory, engine = _world(profile)
    install(factory)
    try:
        questions: list[tuple[str, dict[str, Any], Any, Any]] = [
            ("What is due today?", {}, None, None)
        ]
        for course in profile.courses:
            if course.enrollment_state == "active" and course.assignments:
                a = course.assignments[0]
                questions.append(
                    (f"When is {a.name} due?", {"course_id": course.canvas_id}, course, a)
                )
                questions.append(
                    (
                        f"How many points is {a.name} worth?",
                        {"course_id": course.canvas_id},
                        course,
                        a,
                    )
                )
                break
        async with _client() as client:
            for query, extra, course, assignment in questions:
                body = {"query": query, **extra}
                sync = await client.post("/api/assistant/respond", json=body)
                assert sync.status_code == 200, sync.text
                sync_json = sync.json()
                streamed = await client.post("/api/assistant/stream", json=body)
                assert streamed.status_code == 200
                events = _sse(streamed.text)
                terminal = [e for e in events if e["type"] in {"completed", "error"}]
                problems: list[str] = []
                if len(terminal) != 1 or events[-1] is not terminal[0]:
                    problems.append(
                        f"terminal-event contract broken: {[e['type'] for e in events]}"
                    )
                completed = [e for e in events if e["type"] == "completed"]
                if not completed:
                    problems.append("no completed event")
                else:
                    stream_text = _text(completed[0]["response"]["blocks"])
                    if stream_text != _text(sync_json["blocks"]):
                        problems.append("stream and synchronous text differ")
                sources = [
                    (e.get("identifier"), e.get("source")) for e in events if e["type"] == "source"
                ]
                if len(sources) != len(set(sources)):
                    problems.append("duplicate source events")
                visible = _text(sync_json["blocks"])
                due_at = assignment.due_at if assignment is not None else None
                if (
                    "due" in query
                    and due_at is not None
                    and fmt_due(due_at, profile) not in visible
                ):
                    problems.append("HTTP due date differs from fixture truth")
                if assignment is not None and "points" in query:
                    label = "does not list a point value" if assignment.points is None else "points"
                    if label not in visible:
                        problems.append("HTTP points differ from fixture truth")
                from app.assistant_tools.models import AssistantResponse

                problems += invariant_violations(
                    profile,
                    AssistantResponse.model_validate(sync_json),
                    course=course,
                    check_dates=True,
                )
                CAMPAIGN_RESULTS.append(
                    {
                        "student": f"http-{profile.label}",
                        "feature": "http_sse_parity",
                        "case": f"{query}",
                        "passed": not problems,
                        "detail": "; ".join(problems),
                    }
                )
                assert not problems, f"{profile.label} {query}: {problems}"
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/api/assistant/respond", "/api/assistant/stream"])
async def test_backend_database_failure_is_sanitized_and_terminal(route: str) -> None:
    def broken() -> Iterator[Session]:
        raise OperationalError(LEAK, {}, Exception(LEAK))
        yield  # pragma: no cover

    app.dependency_overrides[get_session] = broken
    app.dependency_overrides[assistant_routes.get_model_provider] = lambda: object()
    try:
        async with _client(raise_app_exceptions=False) as client:
            response = await client.post(route, json={"query": "What is due today?"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code >= 500 or "error" in response.text
    assert "academic.db" not in response.text
    assert "credential-marker" not in response.text
    assert "OperationalError" not in response.text


@pytest.mark.asyncio
async def test_cancelled_stream_does_not_wedge_the_next_request(install) -> None:  # type: ignore[no-untyped-def]
    profile = _profile(2)
    factory, engine = _world(profile)
    install(factory)

    class Slow(SyntheticAcademicModelProvider):
        def stream(self, model_input: Any) -> tuple[Any, ...]:
            time.sleep(0.4)
            return super().stream(model_input)

    app.dependency_overrides[assistant_routes.get_model_provider] = lambda: Slow()
    try:
        async with _client() as client:
            course = next(c for c in profile.courses if c.enrollment_state == "active")
            body = {"query": "Help me understand the main ideas", "course_id": course.canvas_id}
            task = asyncio.create_task(client.post("/api/assistant/stream", json=body))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            started = time.monotonic()
            follow_up = await client.post(
                "/api/assistant/respond", json={"query": "What is due today?"}
            )
            elapsed = time.monotonic() - started
        assert follow_up.status_code == 200
        assert elapsed < 3.0, f"follow-up request waited {elapsed:.2f}s behind a cancelled stream"
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/api/assistant/respond", "/api/assistant/stream"])
async def test_foreign_course_evidence_fails_closed_over_http(
    route: str, install, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    from tests.test_release_regressions_v12 import _ForeignCourseRetrieval

    profile = _profile(4)
    factory, engine = _world(profile)
    install(factory)
    monkeypatch.setattr(
        assistant_routes, "LocalDocumentRetrievalProvider", lambda _tools: _ForeignCourseRetrieval()
    )
    course = next(c for c in profile.courses if c.enrollment_state == "active")
    try:
        async with _client(raise_app_exceptions=False) as client:
            response = await client.post(
                route,
                json={"query": "Summarize the professor lecture", "course_id": course.canvas_id},
            )
    finally:
        engine.dispose()
    assert _ForeignCourseRetrieval.MARKER not in response.text
    assert "Other Course Notes" not in response.text
    if route.endswith("stream"):
        events = _sse(response.text)
        assert events[-1]["type"] in {"completed", "error"}
        assert sum(e["type"] in {"completed", "error"} for e in events) == 1
