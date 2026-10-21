"""Bounded, process-local concept continuity; never persists conversation text."""

from __future__ import annotations

import re
import threading
import time

_FOLLOW_UPS = frozenset({
    "give me a simple example",
    "can you give me a simple example",
    "give me an example",
    "can you give me an example",
    "show me an example",
    "show an example",
    "show a numerical example",
    "give a numerical example",
    "can you show a numerical example",
    "show me a numerical example",
    "numerical example",
    "explain it more simply",
    "explain that more simply",
    "make it simpler",
    "can you explain it again",
})


def is_concept_follow_up(query: str) -> bool:
    normalized = re.sub(r"[?.!,]+", "", " ".join(query.casefold().split()))
    if normalized in _FOLLOW_UPS:
        return True
    if any(
        phrase in normalized
        for phrase in (
            "numerical example",
            "simple example",
            "show an example",
            "give an example",
            "show me an example",
        )
    ):
        return True
    # Pronouns can safely continue a topic only after the session/course cache
    # supplies one. This classifier never performs cross-course lookup.
    return bool(re.match(
        r"^(?:what (?:is|are)|what's|how (?:does|do|is)|why (?:does|is|do we|do)|"
        r"can you explain|explain|show)\s+(?:it|its|this|that|those)\b",
        normalized,
    ))


class ConceptContinuity:
    """TTL-bound per-session/course topic hints, kept only in process memory."""

    def __init__(self, *, ttl_seconds: float = 900, max_entries: int = 128) -> None:
        self._ttl = ttl_seconds
        self._capacity = max_entries
        self._lock = threading.RLock()
        self._items: dict[tuple[str, str], tuple[float, str]] = {}

    def remember(self, session_id: str, course_id: str, query: str) -> None:
        if not session_id or not course_id or is_concept_follow_up(query):
            return
        topic = " ".join(query.split())[:160]
        if not topic:
            return
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            self._items[(session_id, course_id)] = (now, topic)
            while len(self._items) > self._capacity:
                oldest = min(self._items, key=lambda key: self._items[key][0])
                del self._items[oldest]

    def clear(self, session_id: str, course_id: str) -> None:
        """Forget a concept after a non-concept turn in the same conversation/course."""
        if not session_id or not course_id:
            return
        with self._lock:
            self._items.pop((session_id, course_id), None)

    def recall(self, session_id: str, course_id: str) -> str | None:
        if not session_id or not course_id:
            return None
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            item = self._items.get((session_id, course_id))
            return item[1] if item is not None else None

    def _prune(self, now: float) -> None:
        for key, (timestamp, _) in tuple(self._items.items()):
            if now - timestamp >= self._ttl:
                del self._items[key]


concept_continuity = ConceptContinuity()
