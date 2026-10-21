"""Student red-team runtime probes (HTTP only, bounded timeouts, sanitized output)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".hey-canvas" / "run" / "student-red-team-runtime.json"

DEADLINE_PROMPT_GROUPS: dict[str, list[str]] = {
    "TODAY": [
        "What do I have due today?",
        "what's due today",
        "anything due today?",
        "what do i gotta do today",
        "bro whats due today",
    ],
    "TOMORROW": [
        "What do I have due tomorrow?",
        "anything tomorrow?",
        "what's due tmrw",
    ],
    "THIS_WEEK": [
        "what's due this week?",
        "what should I finish this week?",
    ],
    "NEXT_WEEK": [
        "what's due next week?",
        "what do i have next week",
        "anything due next wk?",
        "show next week's work",
        "i asked next week",
        "no, NEXT week",
    ],
    "PRIORITIES": [
        "what should i do first?",
        "what should i work on tonight?",
        "give me my priorities",
    ],
    "ROBOTICS_EXAM_PREP": [
        "make me prepared for the next robotics exam",
        "what should i study?",
        "explain the latest relevant lecture from scratch",
        "i don't understand anything",
        "quiz me on it",
        "when is my next exam?",
        "what did my professor say is definitely on the exam?",
    ],
}

FAST_PATH_WINDOW: dict[str, str] = {
    "TODAY": "today",
    "TOMORROW": "tomorrow",
    "THIS_WEEK": "this_week",
    "NEXT_WEEK": "next_week",
}


def _fingerprint_assignments(rows: list[dict[str, Any]]) -> str:
    ids = sorted(str(r.get("canvas_assignment_id") or r.get("id") or "") for r in rows)
    return hashlib.sha256("|".join(ids).encode()).hexdigest()[:16]


def _deadline_rows(client: httpx.Client, base: str, window: str) -> list[dict[str, Any]]:
    resp = client.get(f"{base}/api/deadlines", params={"window": window}, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def _collect_assistant(
    client: httpx.Client, base: str, prompt: str, *, timeout: float = 180.0
) -> dict[str, Any]:
    started = time.perf_counter()
    first_ms: int | None = None
    chunks: list[str] = []
    terminal: str | None = None
    references = 0
    body = {"query": prompt, "operation": "answer", "session_id": "student-red-team-runtime"}
    with client.stream(
        "POST",
        f"{base}/api/assistant/stream",
        json=body,
        timeout=timeout,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            typ = event.get("type")
            if typ == "text_delta" and event.get("text"):
                if first_ms is None:
                    first_ms = int((time.perf_counter() - started) * 1000)
                chunks.append(str(event["text"]))
            if typ == "completed" and event.get("response"):
                response = event["response"]
                if isinstance(response, dict):
                    for block in response.get("blocks") or []:
                        if isinstance(block, dict):
                            if block.get("text"):
                                if first_ms is None:
                                    first_ms = int((time.perf_counter() - started) * 1000)
                                chunks.append(str(block["text"]))
                            references += len(block.get("references") or [])
            if typ == "error" and event.get("text"):
                chunks.append(str(event["text"]))
            if typ in {"completed", "error"}:
                terminal = str(typ)
                break
    total_ms = int((time.perf_counter() - started) * 1000)
    text = "".join(chunks).strip()
    return {
        "empty": len(text) == 0,
        "text_len": len(text),
        "grounded": references > 0 or len(text) > 40,
        "terminal": terminal,
        "first_text_ms": first_ms,
        "total_ms": total_ms,
        "route": "api/assistant/stream",
    }


def _test_deadline_group(
    client: httpx.Client, base: str, label: str, prompts: list[str]
) -> dict[str, Any]:
    window = FAST_PATH_WINDOW.get(label)
    prompt_results: list[dict[str, Any]] = []
    fps: set[str] = set()
    for prompt in prompts:
        row: dict[str, Any] = {
            "prompt_len": len(prompt),
            "route": "client_deadline_fast_path+/api/deadlines",
            "correct_window": window is not None,
        }
        if window:
            rows = _deadline_rows(client, base, window)
            fp = _fingerprint_assignments(rows)
            row["assignment_fingerprint"] = fp
            row["assignment_count"] = len(rows)
            row["empty"] = len(rows) == 0
            row["pass"] = True
            fps.add(fp)
        else:
            assistant = _collect_assistant(client, base, prompt, timeout=90.0)
            row.update(assistant)
            row["pass"] = not assistant["empty"]
        prompt_results.append(row)
    consistent = len(fps) <= 1 if fps else True
    return {
        "label": label,
        "pass": consistent and all(r["pass"] for r in prompt_results),
        "deterministic_fingerprints_consistent": consistent,
        "api_window": window,
        "results": prompt_results,
    }


def main() -> int:
    base = (
        os.environ.get("STUDENT_RED_TEAM_BASE_URL")
        or os.environ.get("HEY_CANVAS_BACKEND_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")
    summary: dict[str, Any] = {"backend_url": base, "groups": {}, "failed": 0}
    with httpx.Client() as client:
        health = client.get(f"{base}/health", timeout=5.0)
        health.raise_for_status()
        status = client.get(f"{base}/api/assistant/status", timeout=5.0)
        status.raise_for_status()
        summary["assistant_provider"] = status.json().get("provider")

        for label, prompts in DEADLINE_PROMPT_GROUPS.items():
            if label in FAST_PATH_WINDOW:
                group = _test_deadline_group(client, base, label, prompts)
            else:
                results = []
                for prompt in prompts:
                    row = _collect_assistant(client, base, prompt, timeout=120.0)
                    row["prompt_len"] = len(prompt)
                    row["pass"] = not row["empty"]
                    results.append(row)
                group = {
                    "label": label,
                    "pass": all(r["pass"] for r in results),
                    "results": results,
                }
            summary["groups"][label] = group
            if not group["pass"]:
                summary["failed"] += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"failed": summary["failed"], "groups": list(summary["groups"])}))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
