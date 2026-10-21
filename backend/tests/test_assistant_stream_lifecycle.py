"""SSE lifecycle, error sanitization and cancellation behaviour (synthetic only)."""

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import httpx
import pytest
from app.api import assistant_stream_errors
from app.api.routes import assistant as assistant_routes
from app.assistant import blocking_runner
from app.assistant_orchestration.models import AssistantEvent, AssistantEventType
from app.database.session import get_session
from app.main import app
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

LEAK = "credential-marker C:\\private\\academic.db"


def test_ambiguous_wording_does_not_reflect_raw_exception_text() -> None:
    rendered = assistant_stream_errors.format_assistant_stream_error(
        RuntimeError(f"ambiguous {LEAK}")
    )
    assert "academic.db" not in rendered
    assert "credential-marker" not in rendered


def test_unresolved_wording_does_not_reflect_raw_exception_text() -> None:
    rendered = assistant_stream_errors.format_assistant_stream_error(
        ValueError(f"could not be resolved {LEAK}")
    )
    assert "academic.db" not in rendered


def _install(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    events: Callable[..., AsyncIterator[AssistantEvent]],
) -> None:
    async def no_prepare(*_: object, **__: object) -> None:
        return None

    def override() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    monkeypatch.setattr(assistant_routes, "prepare_material_for_request", no_prepare)
    monkeypatch.setattr(assistant_routes, "iter_orchestrator_events", events)
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[assistant_routes.get_model_provider] = lambda: object()


async def _stream() -> tuple[int, list[dict[str, Any]], str]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as client:
        response = await client.post("/api/assistant/stream", json={"query": "synthetic"})
    parsed = []
    for chunk in response.text.split("\n\n"):
        for line in chunk.splitlines():
            if line.startswith("data: "):
                parsed.append(json.loads(line[6:]))
    return response.status_code, parsed, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        ValueError(LEAK),
        TypeError(LEAK),
        KeyError(LEAK),
        OperationalError(LEAK, {}, Exception(LEAK)),
        httpx.ReadError(LEAK),
    ],
)
async def test_unexpected_exception_mid_stream_becomes_sanitized_error_event(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    exc: BaseException,
) -> None:
    async def events(*_: object, **__: object) -> AsyncIterator[AssistantEvent]:
        yield AssistantEvent(type=AssistantEventType.BLOCK, block_type="text", text="partial")
        raise exc

    _install(monkeypatch, session_factory, events)
    try:
        status, parsed, raw = await _stream()
    finally:
        app.dependency_overrides.clear()

    assert status == 200
    assert parsed[-1]["type"] == "error"
    assert "academic.db" not in raw
    assert "credential-marker" not in raw


@pytest.mark.asyncio
async def test_stream_that_ends_without_terminal_event_reports_an_error(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def events(*_: object, **__: object) -> AsyncIterator[AssistantEvent]:
        yield AssistantEvent(type=AssistantEventType.BLOCK, block_type="text", text="partial")

    _install(monkeypatch, session_factory, events)
    try:
        _, parsed, _ = await _stream()
    finally:
        app.dependency_overrides.clear()

    assert parsed[-1]["type"] == "error"


@pytest.mark.asyncio
async def test_completed_stream_does_not_add_spurious_error(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def events(*_: object, **__: object) -> AsyncIterator[AssistantEvent]:
        yield AssistantEvent(type=AssistantEventType.BLOCK, block_type="text", text="ok")
        yield AssistantEvent(type=AssistantEventType.COMPLETED)

    _install(monkeypatch, session_factory, events)
    try:
        _, parsed, _ = await _stream()
    finally:
        app.dependency_overrides.clear()

    assert [item["type"] for item in parsed] == ["block", "completed"]


class _FloodingOrchestrator:
    """Produces far more events than the bounded queue holds."""

    def __init__(self) -> None:
        self.finished = threading.Event()
        self.produced = 0

    def events(self, request: object, cancellation: object = None) -> Iterator[AssistantEvent]:
        try:
            for _ in range(1000):
                self.produced += 1
                yield AssistantEvent(type=AssistantEventType.BLOCK, block_type="text", text="x")
                time.sleep(0.001)
        finally:
            self.finished.set()


@pytest.mark.asyncio
async def test_abandoned_consumer_releases_producer_thread_promptly() -> None:
    orchestrator = _FloodingOrchestrator()
    iterator = blocking_runner.iter_orchestrator_events(
        orchestrator,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )
    await iterator.__anext__()
    await asyncio.sleep(0.2)  # let the bounded queue fill so the producer blocks
    await iterator.aclose()

    released = await asyncio.get_running_loop().run_in_executor(
        None, orchestrator.finished.wait, 5.0
    )
    assert released, "producer thread kept running after the consumer went away"
    assert orchestrator.produced < 1000


class _SlowFirstEventOrchestrator:
    """Models a local provider that is still waiting for its first token."""

    def __init__(self) -> None:
        self.finished = threading.Event()

    def events(self, request: object, cancellation: object = None) -> Iterator[AssistantEvent]:
        try:
            # DB preflight is finished; the provider is now waiting for a token.
            yield AssistantEvent(type=AssistantEventType.STARTED)
            time.sleep(2.0)
            yield AssistantEvent(type=AssistantEventType.BLOCK, block_type="text", text="late")
        finally:
            self.finished.set()


@pytest.mark.asyncio
async def test_cancellation_does_not_wait_for_slow_first_provider_event() -> None:
    cancelled = threading.Event()
    orchestrator = _SlowFirstEventOrchestrator()
    iterator = blocking_runner.iter_orchestrator_events(
        orchestrator,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        cancellation=cancelled.is_set,
    )

    started_event = await asyncio.wait_for(iterator.__anext__(), timeout=1.0)
    assert started_event.type is AssistantEventType.STARTED
    pending = asyncio.create_task(iterator.__anext__())
    await asyncio.sleep(0.05)
    cancelled.set()
    started = time.perf_counter()
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(pending, timeout=1.25)
    assert time.perf_counter() - started < 1.2

    released = await asyncio.get_running_loop().run_in_executor(
        None, orchestrator.finished.wait, 3.0
    )
    assert released


@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [ValueError(LEAK), KeyError(LEAK), httpx.ReadError(LEAK)])
async def test_synchronous_respond_sanitizes_unexpected_exceptions(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    exc: BaseException,
) -> None:
    async def no_prepare(*_: object, **__: object) -> None:
        return None

    async def fail(*_: object, **__: object) -> object:
        raise exc

    def override() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    monkeypatch.setattr(assistant_routes, "prepare_material_for_request", no_prepare)
    monkeypatch.setattr(assistant_routes, "run_orchestrator", fail)
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[assistant_routes.get_model_provider] = lambda: object()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
        ) as client:
            response = await client.post("/api/assistant/respond", json={"query": "synthetic"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "academic.db" not in response.text
    assert "credential-marker" not in response.text



class _SlowDatabaseSetupOrchestrator:
    """Simulate a DB read that must finish before the session can be closed."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.setup_finished = threading.Event()
        self.allow_setup_to_finish = threading.Event()

    def events(self, request: object, cancellation: object = None) -> Iterator[AssistantEvent]:
        self.entered.set()
        self.allow_setup_to_finish.wait(timeout=5.0)
        self.setup_finished.set()
        yield AssistantEvent(type=AssistantEventType.STARTED)


@pytest.mark.asyncio
async def test_cancellation_waits_for_database_setup_before_session_teardown() -> None:
    orchestrator = _SlowDatabaseSetupOrchestrator()
    cancelled = threading.Event()
    iterator = blocking_runner.iter_orchestrator_events(
        orchestrator,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        cancellation=cancelled.is_set,
    )
    pending = asyncio.create_task(iterator.__anext__())
    entered = await asyncio.to_thread(orchestrator.entered.wait, 2.0)
    assert entered
    cancelled.set()
    await asyncio.sleep(0.35)
    # Detaching here would let FastAPI close the request-scoped DB session
    # while the producer is still in the synthetic DB setup.
    assert not pending.done()
    orchestrator.allow_setup_to_finish.set()
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(pending, timeout=2.0)
    assert orchestrator.setup_finished.is_set()



@pytest.mark.asyncio
async def test_cancelled_stream_keeps_real_sqlalchemy_session_alive_during_setup(
    session_factory: sessionmaker[Session],
) -> None:
    """The producer must complete its DB read before request session teardown."""
    from sqlalchemy import text

    class DatabaseSetup:
        def __init__(self, session: Session) -> None:
            self.session = session
            self.entered = threading.Event()
            self.allow_read = threading.Event()
            self.read_done = threading.Event()
            self.result: int | None = None

        def events(
            self, request: object, cancellation: object = None
        ) -> Iterator[AssistantEvent]:
            self.entered.set()
            if not self.allow_read.wait(timeout=5.0):
                raise TimeoutError("synthetic database setup gate timed out")
            self.result = self.session.execute(text("SELECT 1")).scalar_one()
            self.read_done.set()
            yield AssistantEvent(type=AssistantEventType.STARTED)

    with session_factory() as session:
        orchestrator = DatabaseSetup(session)
        cancelled = threading.Event()
        stream = blocking_runner.iter_orchestrator_events(
            orchestrator,  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            cancellation=cancelled.is_set,
        )
        pending = asyncio.create_task(stream.__anext__())
        assert await asyncio.to_thread(orchestrator.entered.wait, 2.0)
        cancelled.set()
        await asyncio.sleep(0.35)
        assert not pending.done(), "session could close before worker finishes DB setup"
        orchestrator.allow_read.set()
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(pending, timeout=2.0)
        assert orchestrator.read_done.is_set()
        assert orchestrator.result == 1


@pytest.mark.asyncio
async def test_hard_task_cancellation_cannot_bypass_database_setup_barrier() -> None:
    orchestrator = _SlowDatabaseSetupOrchestrator()
    stream = blocking_runner.iter_orchestrator_events(
        orchestrator,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )
    pending = asyncio.create_task(stream.__anext__())
    assert await asyncio.to_thread(orchestrator.entered.wait, 2.0)

    pending.cancel()
    await asyncio.sleep(0.35)
    assert not pending.done(), "hard abort bypassed the database setup barrier"

    orchestrator.allow_setup_to_finish.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, timeout=2.0)
    assert orchestrator.setup_finished.is_set()


@pytest.mark.asyncio
async def test_hard_cancellation_with_real_sqlalchemy_session_no_unraisable_warnings(
    session_factory: sessionmaker[Session],
) -> None:
    """Hard abort during DB access must finish setup cleanly.

    Subsequent requests on new sessions must remain fully healthy.
    """
    import sys
    from sqlalchemy import text

    unraisables: list[object] = []
    orig_unraisable = sys.unraisablehook

    def hook(unraisable: object) -> None:
        unraisables.append(unraisable)

    sys.unraisablehook = hook

    class RealDbOrchestrator:
        def __init__(self, session: Session) -> None:
            self.session = session
            self.entered = threading.Event()
            self.allow_read = threading.Event()
            self.read_done = threading.Event()
            self.result: int | None = None

        def events(
            self, request: object, cancellation: object = None
        ) -> Iterator[AssistantEvent]:
            self.entered.set()
            if not self.allow_read.wait(timeout=5.0):
                raise TimeoutError("DB setup gate timed out")
            self.result = self.session.execute(text("SELECT 42")).scalar_one()
            self.read_done.set()
            yield AssistantEvent(type=AssistantEventType.STARTED)

    try:
        # Request 1: hard-aborted during database setup
        with session_factory() as session1:
            orch1 = RealDbOrchestrator(session1)
            stream1 = blocking_runner.iter_orchestrator_events(
                orch1,  # type: ignore[arg-type]
                object(),  # type: ignore[arg-type]
            )
            task1 = asyncio.create_task(stream1.__anext__())
            assert await asyncio.to_thread(orch1.entered.wait, 2.0)

            # Hard cancel the consumer task
            task1.cancel()
            await asyncio.sleep(0.25)
            assert not task1.done(), "task aborted before DB setup finished"

            orch1.allow_read.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task1, timeout=2.0)

            assert orch1.read_done.is_set()
            assert orch1.result == 42

        # Verify no unraisable SQLAlchemy warnings or errors were trapped
        assert len(unraisables) == 0, f"Unraisable warnings trapped: {unraisables}"

        # Request 2: immediate new request on new session runs cleanly
        with session_factory() as session2:
            res = session2.execute(text("SELECT 100")).scalar_one()
            assert res == 100

    finally:
        sys.unraisablehook = orig_unraisable


@pytest.mark.asyncio
async def test_cancellation_mid_stream_and_immediate_follow_up() -> None:
    """Mid-stream abort must cleanly stop consumer and allow immediate follow-up request."""
    class MultiTokenOrchestrator:
        def __init__(self) -> None:
            self.tokens_emitted = 0

        def events(
            self, request: object, cancellation: object = None
        ) -> Iterator[AssistantEvent]:
            yield AssistantEvent(type=AssistantEventType.STARTED)
            for i in range(10):
                time.sleep(0.05)
                self.tokens_emitted += 1
                yield AssistantEvent(
                    type=AssistantEventType.TEXT_DELTA,
                    data={"text": f"token_{i}"},
                )
            yield AssistantEvent(type=AssistantEventType.COMPLETED)

    # First request: consumer cancels after 2 tokens
    orch1 = MultiTokenOrchestrator()
    stream1 = blocking_runner.iter_orchestrator_events(
        orch1,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )

    ev1 = await stream1.__anext__()
    assert ev1.type == AssistantEventType.STARTED
    ev2 = await stream1.__anext__()
    assert ev2.type == AssistantEventType.TEXT_DELTA

    # Hard-cancel the stream iteration
    consumer_task = asyncio.create_task(stream1.__anext__())
    await asyncio.sleep(0.02)
    consumer_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer_task

    # Second request: immediate follow-up stream succeeds completely
    orch2 = MultiTokenOrchestrator()
    stream2 = blocking_runner.iter_orchestrator_events(
        orch2,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )
    events2: list[AssistantEvent] = []
    async for ev in stream2:
        events2.append(ev)

    assert events2[0].type == AssistantEventType.STARTED
    assert events2[-1].type == AssistantEventType.COMPLETED
    assert orch2.tokens_emitted == 10


@pytest.mark.asyncio
async def test_cancellation_during_provider_failure() -> None:
    """Provider failure during cancellation must not raise unhandled exceptions or hang."""
    class FailingOrchestrator:
        def events(
            self, request: object, cancellation: object = None
        ) -> Iterator[AssistantEvent]:
            yield AssistantEvent(type=AssistantEventType.STARTED)
            time.sleep(0.05)
            raise RuntimeError("synthetic provider connection failure")

    stream = blocking_runner.iter_orchestrator_events(
        FailingOrchestrator(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )

    ev = await stream.__anext__()
    assert ev.type == AssistantEventType.STARTED

    consumer_task = asyncio.create_task(stream.__anext__())
    await asyncio.sleep(0.02)
    consumer_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer_task

