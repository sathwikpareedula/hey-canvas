"""Multi-turn assistant adversarial probes (sanitized metrics only)."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".hey-canvas" / "run" / "adversarial-conversations.json"

TURNS: dict[str, list[str]] = {
    "A": [
        "what do i have due next week",
        "i asked NEXT week",
        "which one should i do first",
        "explain that one",
        "what material do i need",
        "when is it due",
        "quiz me on it",
    ],
    "B": [
        "help me prepare for robotics",
        "what should i study",
        "explain it from scratch",
        "quiz me",
        "harder",
        "why",
        "what homework uses this",
        "what did professor say",
    ],
    "C": [
        "what's next for ML",
        "explain it",
        "switch to neural networks",
        "what should I study there",
        "go back to ML",
        "when is that assignment due",
    ],
    "D": [
        "help with senior design",
        "how do i do the assignment",
        "what about the individual report",
        "when is it due",
        "what instructions did professor give",
    ],
}


def _collect(
    client: httpx.Client, base: str, session_id: str, prompt: str, *, timeout: float = 180.0
) -> dict[str, Any]:
    started = time.perf_counter()
    first_ms: int | None = None
    chunks: list[str] = []
    course_ids: set[str] = set()
    terminal: str | None = None
    body = {"query": prompt, "operation": "answer", "session_id": session_id}
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
            cid = event.get("course_id")
            if isinstance(cid, str) and cid:
                course_ids.add(cid)
            if typ == "text_delta" and event.get("text"):
                if first_ms is None:
                    first_ms = int((time.perf_counter() - started) * 1000)
                chunks.append(str(event["text"]))
            if typ == "completed" and event.get("response"):
                response = event["response"]
                if isinstance(response, dict):
                    for block in response.get("blocks") or []:
                        if not isinstance(block, dict):
                            continue
                        if block.get("text"):
                            if first_ms is None:
                                first_ms = int((time.perf_counter() - started) * 1000)
                            chunks.append(str(block["text"]))
                        for ref in block.get("references") or []:
                            if isinstance(ref, dict) and ref.get("course_id"):
                                course_ids.add(str(ref["course_id"]))
            if typ == "error" and event.get("text"):
                chunks.append(str(event["text"]))
            if typ in {"completed", "error"}:
                terminal = str(typ)
                break
    text = "".join(chunks).strip()
    heading = None
    if re.search(r"next week", text, re.I):
        heading = "next_week"
    elif re.search(r"this week", text, re.I):
        heading = "this_week"
    elif re.search(r"due today", text, re.I):
        heading = "today"
    elif re.search(r"due tomorrow", text, re.I):
        heading = "tomorrow"
    return {
        "empty": len(text) == 0,
        "text_len": len(text),
        "first_ms": first_ms,
        "total_ms": int((time.perf_counter() - started) * 1000),
        "terminal": terminal,
        "heading_hint": heading,
        "distinct_course_ids_in_stream": len(course_ids),
        "pass": len(text) > 0 and terminal != "error",
    }


def main() -> int:
    base = os.environ.get("HEY_CANVAS_BACKEND_URL", "http://127.0.0.1:18196").rstrip("/")
    summary: dict[str, Any] = {"backend_url": base, "conversations": {}, "failed": 0}
    with httpx.Client() as client:
        client.get(f"{base}/health", timeout=5.0).raise_for_status()
        for label, prompts in TURNS.items():
            session_id = f"adv-{label.lower()}-{uuid.uuid4().hex[:8]}"
            turns: list[dict[str, Any]] = []
            ok = True
            for prompt in prompts:
                row = _collect(client, base, session_id, prompt)
                row["prompt_len"] = len(prompt)
                turns.append(row)
                if row["empty"]:
                    ok = False
            cross = [t for t in turns if t["distinct_course_ids_in_stream"] > 1]
            conv = {
                "pass": ok and not cross,
                "turns": turns,
                "cross_course_turns": len(cross),
            }
            summary["conversations"][label] = conv
            if not conv["pass"]:
                summary["failed"] += 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"failed": summary["failed"], "keys": list(summary["conversations"])}))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
