"""User-safe assistant stream error text (no raw httpx / socket strings)."""

from __future__ import annotations

import httpx


def format_assistant_stream_error(exc: BaseException) -> str:
    message = str(exc).strip()
    lower = message.lower()

    if lower.startswith("local_ai_busy:"):
        return (
            "Your local AI is already answering another question. "
            "Wait for it to finish, then try again."
        )
    if "disconnected" in lower:
        return "The chat connection closed before the answer finished."
    if isinstance(exc, httpx.HTTPError) or "provider request failed" in lower:
        return (
            "Hey Canvas could not reach your local AI (Ollama). "
            "Confirm Ollama is running, then retry."
        )
    if "provider unavailable" in lower or "unavailable" in lower:
        return "Your local AI model is not available right now. Check Ollama and retry."
    if "timeout" in lower or "timed out" in lower:
        return (
            "The local AI took too long to respond. "
            "Try a shorter question or retry in a moment."
        )
    if "ambiguous" in lower or "could not be resolved" in lower:
        return "Hey Canvas could not tell which course you mean. Pick a course and retry."
    if "invalid stream" in lower or "malformed" in lower:
        return "The local AI returned an unexpected response. Please retry."
    return (
        "Hey Canvas could not complete this answer right now. Please retry."
    )
