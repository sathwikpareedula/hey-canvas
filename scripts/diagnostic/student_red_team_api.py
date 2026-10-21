"""Student prompt battery against local assistant API (synthetic provider)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".hey-canvas" / "run" / "student-red-team-api.json"

PROMPTS = [
    "What do I have due today?",
    "what i got tmrw",
    "anything next wk",
    "i asked next week",
    "make me prepared for the next robotics exam",
    "help me study robotics",
    "when is my next exam?",
    "explain lecture 99",
]


def _collect_assistant_text(
    client: httpx.Client, base: str, prompt: str
) -> tuple[bool, int, str | None]:
    body = {
        "query": prompt,
        "operation": "answer",
        "session_id": "student-red-team",
    }
    chunks: list[str] = []
    terminal: str | None = None
    with client.stream(
        "POST",
        f"{base}/api/assistant/stream",
        json=body,
        timeout=120.0,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            typ = event.get("type")
            if typ == "text_delta" and event.get("text"):
                chunks.append(str(event["text"]))
            if typ == "completed" and event.get("response"):
                response = event["response"]
                if isinstance(response, dict):
                    if response.get("text"):
                        chunks.append(str(response["text"]))
                    for block in response.get("blocks") or []:
                        if isinstance(block, dict) and block.get("text"):
                            chunks.append(str(block["text"]))
            if typ == "error" and event.get("text"):
                chunks.append(str(event["text"]))
            if typ in {"completed", "error"}:
                terminal = str(typ)
                break
    text = "".join(chunks).strip()
    return bool(text), len(text), terminal


def main() -> int:
    base = os.environ.get("HEY_CANVAS_BACKEND_URL", "http://127.0.0.1:18181").rstrip("/")
    results: list[dict[str, object]] = []
    failed = 0
    with httpx.Client() as client:
        for prompt in PROMPTS:
            row: dict[str, object] = {"prompt_len": len(prompt), "ok": False, "text_len": 0}
            try:
                ok, n, terminal = _collect_assistant_text(client, base, prompt)
                row["ok"] = ok
                row["text_len"] = n
                row["terminal"] = terminal
                if not ok:
                    failed += 1
            except Exception as exc:
                row["error"] = type(exc).__name__
                failed += 1
            results.append(row)

    summary = {"prompts": len(PROMPTS), "failed": failed, "results": results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"prompts": len(PROMPTS), "failed": failed}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
