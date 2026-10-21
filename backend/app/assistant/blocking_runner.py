"""Run blocking assistant orchestration off the asyncio event loop."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from functools import lru_cache

from app.assistant_orchestration.models import AssistantEvent, CancellationToken
from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_tools.models import AssistantRequest, AssistantResponse
from app.config import get_settings

_STOP = object()


class _CallableCancellationToken:
    def __init__(self, check: Callable[[], bool]) -> None:
        self._check = check

    @property
    def cancelled(self) -> bool:
        return self._check()


@lru_cache
def _executor() -> ThreadPoolExecutor:
    workers = max(1, min(4, get_settings().assistant_blocking_workers))
    return ThreadPoolExecutor(max_workers=workers, thread_name_prefix="assistant")


async def run_orchestrator(
    orchestrator: AcademicAssistantOrchestrator,
    request: AssistantRequest,
) -> AssistantResponse:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor(), orchestrator.run, request)


async def iter_orchestrator_events(
    orchestrator: AcademicAssistantOrchestrator,
    request: AssistantRequest,
    *,
    cancellation: Callable[[], bool] | None = None,
) -> AsyncIterator[AssistantEvent]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[AssistantEvent | object] = asyncio.Queue(maxsize=32)
    abandoned = threading.Event()
    setup_finished = threading.Event()

    def is_cancelled() -> bool:
        return abandoned.is_set() or (cancellation is not None and cancellation())

    token: CancellationToken = _CallableCancellationToken(is_cancelled)

    def put(item: object) -> bool:
        """Queue an item; give up promptly once the consumer is gone or cancelled."""
        future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
        while True:
            try:
                future.result(timeout=0.25)
                return True
            except FutureTimeoutError:
                if is_cancelled():
                    future.cancel()
                    return False

    def producer() -> None:
        try:
            for event in orchestrator.events(request, cancellation=token):
                # The orchestrator emits STARTED only after database-backed setup.
                # The consumer must not release its session before this barrier.
                setup_finished.set()
                if token.cancelled or not put(event):
                    break
        finally:
            setup_finished.set()
            if not is_cancelled():
                put(_STOP)

    producer_task = loop.run_in_executor(_executor(), producer)
    drained = False
    try:
        while True:
            if is_cancelled():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.25)
            except TimeoutError:
                if producer_task.done():
                    drained = True
                    break
                continue
            if item is _STOP:
                drained = True
                break
            if isinstance(item, AssistantEvent):
                yield item
    finally:
        abandoned.set()
        # A request-scoped SQLAlchemy session must not close while producer
        # is assembling its database-backed model input on another thread.
        # Cancellation may therefore await setup, but never the full model call.
        if not setup_finished.is_set():
            setup_wait = asyncio.create_task(asyncio.to_thread(setup_finished.wait))
            interrupted: asyncio.CancelledError | None = None
            while not setup_wait.done():
                try:
                    await asyncio.shield(setup_wait)
                except asyncio.CancelledError as exc:
                    # A hard client abort cancels the response task itself. Defer
                    # that cancellation until the producer has left all request-
                    # scoped database setup; otherwise FastAPI may close the same
                    # SQLAlchemy session concurrently with its worker thread.
                    interrupted = exc
            if interrupted is not None:
                producer_task.add_done_callback(_discard_outcome)
                raise interrupted
        if not drained:
            # Give the producer a short window to leave database-backed setup and close
            # a cancellable provider stream before FastAPI releases the request session.
            # Never wait for the full model response when a provider ignores cancellation.
            try:
                await asyncio.wait_for(asyncio.shield(producer_task), timeout=0.5)
            except Exception:
                # The consumer has abandoned this stream, so a late provider
                # failure must not replace the original cancellation. Do not
                # catch CancelledError (a BaseException) here: hard client
                # cancellation still has to propagate to FastAPI.
                producer_task.add_done_callback(_discard_outcome)
    if drained:
        await producer_task


def _discard_outcome(future: asyncio.Future[None]) -> None:
    if not future.cancelled():
        future.exception()
