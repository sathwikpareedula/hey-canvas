"""Measured (not guessed) latency and boundedness checks on synthetic data.

Budgets are deliberately generous so shared CI hardware does not flake; the real
numbers are written to ``$HEY_CANVAS_PERF_REPORT`` (JSON) when that variable is set.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from pathlib import Path
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from app.api.routes import assistant as assistant_routes
from app.assistant_orchestration.models import AssistantModelInput, ToolPlan
from app.assistant_provider.ollama import OllamaAcademicModelProvider
from app.assistant_provider.synthetic import SyntheticAcademicModelProvider
from app.assistant_tools.models import AssistantRequest, DocumentEvidence, SourceAuthority
from app.main import app

from tests.acceptance.harness import student_world
from tests.acceptance.student_factory import build_student
from tests.acceptance.test_http_campaign import (
    BASE,
    _client,
    _profile,
    _world,
)

MEASUREMENTS: dict[str, Any] = {}


def _percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "n": len(ordered),
        "p50_ms": round(statistics.median(ordered) * 1000, 3),
        "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1] * 1000, 3),
        "max_ms": round(ordered[-1] * 1000, 3),
    }


def _time(fn: Callable[[], object], repeat: int) -> list[float]:
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return samples


@pytest.fixture(scope="module", autouse=True)
def _write_report() -> Any:
    yield
    path = os.environ.get("HEY_CANVAS_PERF_REPORT")
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(MEASUREMENTS, handle, indent=2, sort_keys=True)


def _busy_profile() -> Any:
    for index in range(200):
        profile = build_student(99, index)
        if sum(len(c.assignments) for c in profile.courses) >= 10:
            return profile
    raise AssertionError("no busy profile")


def test_deterministic_deadline_latency() -> None:
    with student_world(_busy_profile()) as world:
        orchestrator = world.orchestrator()
        request = world.request("What is due today?")
        samples = _time(lambda: orchestrator.run(request), 100)
    stats = _percentiles(samples)
    MEASUREMENTS["deterministic_deadline_response"] = stats
    assert stats["p95_ms"] < 500


def test_assignment_answer_and_context_assembly_latency() -> None:
    profile = _busy_profile()
    with student_world(profile) as world:
        course = next(c for c in profile.courses if c.assignments)
        orchestrator = world.orchestrator()
        due = world.request(
            f"When is {course.assignments[0].name} due?", course_id=course.canvas_id
        )
        lecture = world.request("Summarize the professor lecture", course_id=course.canvas_id)
        plan = orchestrator.plan(lecture)
        MEASUREMENTS["assignment_due_response"] = _percentiles(
            _time(lambda: orchestrator.run(due), 60)
        )
        MEASUREMENTS["context_assembly"] = _percentiles(
            _time(lambda: orchestrator._assemble(lecture, plan), 60)
        )
    assert MEASUREMENTS["assignment_due_response"]["p95_ms"] < 500
    assert MEASUREMENTS["context_assembly"]["p95_ms"] < 750


def _oversized_input(evidence_count: int = 20) -> AssistantModelInput:
    evidence = tuple(
        DocumentEvidence(
            authority=SourceAuthority.PROFESSOR_MATERIAL,
            canvas_file_id=f"f{i}",
            canvas_course_id="c1",
            display_name=f"Lecture {i}",
            filename=f"lecture-{i}.pdf",
            unit_type="page",
            unit_index=i,
            page_number=i + 1,
            slide_number=None,
            heading=None,
            excerpt=("graph traversal " * 80)[:1000],
            is_stale=False,
        )
        for i in range(evidence_count)
    )
    return AssistantModelInput(
        request=AssistantRequest(query="What is covered?", course_id="c1"),
        plan=ToolPlan(operation="study_help", query="What is covered?", course_id="c1"),
        context=None,
        evidence=evidence,
    )


def test_prompt_size_is_bounded_for_oversized_context() -> None:
    provider = OllamaAcademicModelProvider(model="synthetic-model")
    small = len(provider._compile_prompt(_oversized_input(1)))
    large_input = _oversized_input(20)
    start = time.perf_counter()
    large = len(provider._compile_prompt(large_input))
    elapsed = time.perf_counter() - start
    MEASUREMENTS["prompt_construction"] = {
        "chars_1_evidence": small,
        "chars_20_evidence": large,
        "ms_20_evidence": round(elapsed * 1000, 3),
    }
    assert large < 12_000, "prompt must stay bounded even when 20 evidence items arrive"
    assert elapsed < 0.25
    assert large < small * 12


@pytest.mark.asyncio
async def test_concurrent_requests_all_succeed_and_stay_consistent(
    install: Any, tmp_path: Path
) -> None:
    profile = _profile(3)
    factory, engine = _world(profile, database_path=str(tmp_path / "concurrent.db"))
    install(factory)
    app.dependency_overrides[assistant_routes.get_model_provider] = lambda: (
        SyntheticAcademicModelProvider()
    )
    count = 40
    try:
        async with _client() as client:
            start = time.perf_counter()
            responses = await asyncio.gather(
                *(
                    client.post("/api/assistant/respond", json={"query": "What is due today?"})
                    for _ in range(count)
                ),
                *(
                    client.post("/api/assistant/stream", json={"query": "What is due today?"})
                    for _ in range(count)
                ),
            )
            elapsed = time.perf_counter() - start
    finally:
        engine.dispose()
    assert all(r.status_code == 200 for r in responses)
    texts = {
        "\n".join(b["text"] for b in r.json()["blocks"] if b.get("text")) for r in responses[:count]
    }
    assert len(texts) == 1, "repeated identical queries must give identical answers"
    for r in responses[count:]:
        assert r.text.count("event: completed") + r.text.count("event: error") == 1
    MEASUREMENTS["concurrency"] = {
        "requests": count * 2,
        "wall_seconds": round(elapsed, 3),
        "requests_per_second": round(count * 2 / elapsed, 1),
    }
    assert elapsed < 30


@pytest.mark.asyncio
async def test_cancelled_streams_release_workers_for_later_requests(
    install: Any, tmp_path: Path
) -> None:
    profile = _profile(2)
    factory, engine = _world(profile, database_path=str(tmp_path / "cancel.db"))
    install(factory)

    class Slow(SyntheticAcademicModelProvider):
        def stream(self, model_input: Any) -> tuple[Any, ...]:
            time.sleep(0.5)
            return super().stream(model_input)

    app.dependency_overrides[assistant_routes.get_model_provider] = lambda: Slow()
    course = next(c for c in profile.courses if c.enrollment_state == "active")
    body = {"query": "Help me understand the main ideas", "course_id": course.canvas_id}
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=BASE
        ) as client:
            tasks = [
                asyncio.create_task(client.post("/api/assistant/stream", json=body))
                for _ in range(8)
            ]
            await asyncio.sleep(0.1)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            start = time.perf_counter()
            follow = await client.post(
                "/api/assistant/respond", json={"query": "What is due today?"}
            )
            elapsed = time.perf_counter() - start
    finally:
        engine.dispose()
    MEASUREMENTS["cancellation_recovery"] = {
        "cancelled_streams": 8,
        "follow_up_seconds": round(elapsed, 3),
    }
    assert follow.status_code == 200
    assert elapsed < 5.0
