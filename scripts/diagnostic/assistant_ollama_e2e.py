"""Live Local AI E2E probe (synthetic prompt). Writes sanitized JSON summary."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".hey-canvas" / "run" / "assistant-ollama-e2e.json"


def main() -> int:
    base = os.environ.get("HEY_CANVAS_BACKEND_URL", "http://127.0.0.1:18180").rstrip("/")
    ollama = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    prompt = os.environ.get("E2E_ASSISTANT_PROMPT", "Reply with exactly: E2E_OK")

    summary: dict[str, object] = {
        "backend_url": base,
        "ollama_url": ollama,
        "provider": None,
        "resolved_model": None,
        "first_text_latency_ms": None,
        "total_latency_ms": None,
        "event_count": 0,
        "terminal_event": None,
        "usable_text": False,
        "error": None,
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            tags = client.get(f"{ollama}/api/tags")
            tags.raise_for_status()
            models = [m.get("name") for m in tags.json().get("models", []) if m.get("name")]
            if not models:
                summary["error"] = "no_ollama_models"
                OUT.parent.mkdir(parents=True, exist_ok=True)
                OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
                return 1

            status = client.get(f"{base}/api/assistant/status")
            status.raise_for_status()
            st = status.json()
            summary["provider"] = st.get("provider")
            if st.get("provider") == "synthetic":
                summary["error"] = "synthetic_provider_not_e2e"
                OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
                return 1

            sel = client.get(f"{base}/api/local-ai/model")
            if sel.status_code == 200:
                summary["resolved_model"] = sel.json().get("model") or sel.json().get(
                    "selected_model"
                )

        started = time.perf_counter()
        first_text_at: float | None = None
        events = 0
        terminal: str | None = None
        text_parts: list[str] = []

        with httpx.Client(timeout=120.0) as client, client.stream(
            "POST",
            f"{base}/api/assistant/stream",
            json={
                "query": prompt,
                "operation": "answer",
                "session_id": "e2e-probe",
            },
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    terminal = "done"
                    break
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                events += 1
                typ = data.get("type")
                if typ == "text_delta" and data.get("text"):
                    text_parts.append(str(data["text"]))
                    if first_text_at is None:
                        first_text_at = time.perf_counter()
                if typ in {"completed", "error"}:
                    terminal = typ
                    break

        total_ms = int((time.perf_counter() - started) * 1000)
        summary["total_latency_ms"] = total_ms
        summary["event_count"] = events
        summary["terminal_event"] = terminal
        if first_text_at is not None:
            summary["first_text_latency_ms"] = int((first_text_at - started) * 1000)
        joined = "".join(text_parts).strip()
        summary["usable_text"] = len(joined) >= 3
        if not summary["usable_text"]:
            summary["error"] = "empty_or_tiny_response"
    except Exception as exc:
        summary["error"] = type(exc).__name__

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("usable_text") else 1


if __name__ == "__main__":
    sys.exit(main())
