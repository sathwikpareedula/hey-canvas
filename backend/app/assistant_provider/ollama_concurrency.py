"""Bound concurrent Ollama generate calls (single local GPU / model load)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypeVar

from app.config import get_settings

_T = TypeVar("_T")

_lock = threading.Lock()
_semaphore: threading.Semaphore | None = None
_waiters = 0


def _slot_semaphore() -> threading.Semaphore:
    global _semaphore
    if _semaphore is None:
        slots = max(1, min(2, get_settings().ollama_max_concurrent_requests))
        _semaphore = threading.Semaphore(slots)
    return _semaphore


@contextmanager
def ollama_generate_slot() -> Iterator[None]:
    """Acquire a slot before calling Ollama; release when the stream/complete finishes."""

    global _waiters
    sem = _slot_semaphore()
    with _lock:
        _waiters += 1
    wait_budget = get_settings().ollama_queue_wait_seconds
    acquired = sem.acquire(timeout=wait_budget)
    with _lock:
        _waiters = max(0, _waiters - 1)
    if not acquired:
        raise RuntimeError(
            "local_ai_busy: another Hey Canvas answer is still generating; try again shortly"
        )
    try:
        yield
    finally:
        sem.release()


def ollama_queue_depth() -> int:
    with _lock:
        return _waiters
