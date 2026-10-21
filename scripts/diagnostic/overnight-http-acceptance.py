"""Batch HTTP acceptance checks for overnight mission (no secrets)."""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
FRONTEND = "http://localhost:13117"
COURSE = "278791"


def get_json(path: str, timeout: float = 30.0) -> dict | list:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def post_stream_completed(query: str, timeout: float = 300.0) -> dict:
    payload = {"query": query, "course_id": COURSE}
    req = urllib.request.Request(
        f"{BASE}/api/assistant/stream",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    completed = None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            if event.get("type") == "completed":
                completed = event
    if completed is None:
        raise RuntimeError("stream_missing_completed")
    return completed["response"]


def main() -> int:
    results: list[dict] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append({"name": name, "ok": ok, "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")

    try:
        health = get_json("/health")
        record("health", health.get("status") == "ok", str(health.get("status")))
    except Exception as exc:  # noqa: BLE001
        record("health", False, str(exc))
        print(json.dumps(results, indent=2))
        return 1

    try:
        status = get_json("/api/assistant/status")
        record(
            "assistant_status",
            status.get("provider") == "ollama" and status.get("available") is True,
            json.dumps(status),
        )
    except Exception as exc:  # noqa: BLE001
        record("assistant_status", False, str(exc))

    try:
        anns = get_json(f"/api/courses/{COURSE}/announcements")
        record(
            "live_announcements_empty",
            isinstance(anns, list) and len(anns) == 0,
            f"count={len(anns) if isinstance(anns, list) else 'invalid'}",
        )
    except Exception as exc:  # noqa: BLE001
        record("live_announcements_empty", False, str(exc))

    queries = [
        (
            "quiz_prep",
            "When is Quiz 3 due in this course, what does the syllabus say about quizzes, "
            "and teach me SLAM from Lecture 01 with citations.",
        ),
        (
            "deadline",
            "What is due soon in this course?",
        ),
        (
            "lecture",
            "How does Lecture 01 define a robot? Use course materials only.",
        ),
    ]
    for name, query in queries:
        try:
            t0 = time.perf_counter()
            body = post_stream_completed(query)
            elapsed = round(time.perf_counter() - t0, 1)
            blocks = body.get("blocks") or []
            text = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
            ev = next((b for b in blocks if b.get("type") == "document_evidence"), None)
            refs = len((ev or {}).get("references") or [])
            if name == "deadline":
                dead = next(
                    (
                        b
                        for b in blocks
                        if b.get("type") in {"deadlines", "deadline_group"}
                    ),
                    None,
                )
                ok = body.get("status") == "ok" and dead is not None
                record(
                    name,
                    ok,
                    f"elapsed_s={elapsed} deadlines={dead is not None} types={[b.get('type') for b in blocks]}",
                )
                continue
            ok = body.get("status") == "ok" and len(text) > 40 and refs > 0
            record(name, ok, f"elapsed_s={elapsed} text_len={len(text)} refs={refs}")
        except Exception as exc:  # noqa: BLE001
            record(name, False, str(exc))

    # health during stream
    try:
        payload = {
            "query": "Summarize motion planning from our lecture PDFs.",
            "course_id": COURSE,
        }
        events: list[str] = []

        def worker() -> None:
            req = urllib.request.Request(
                f"{BASE}/api/assistant/stream",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw in resp:
                    line = raw.decode().strip()
                    if line.startswith("data:"):
                        events.append(line[5:])

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        time.sleep(2)
        latencies = []
        for _ in range(4):
            t0 = time.perf_counter()
            urllib.request.urlopen(f"{BASE}/health", timeout=5)
            latencies.append(round(time.perf_counter() - t0, 3))
            time.sleep(2)
        thread.join(timeout=300)
        terminal = False
        for event in events:
            if not event.startswith("{"):
                continue
            try:
                parsed = json.loads(event)
            except json.JSONDecodeError:
                continue
            if parsed.get("type") in {"completed", "error"}:
                terminal = True
                break
        record(
            "health_during_stream",
            terminal and all(v < 2 for v in latencies),
            f"latencies={latencies} terminal={terminal}",
        )
    except Exception as exc:  # noqa: BLE001
        record("health_during_stream", False, str(exc))

    try:
        code = urllib.request.urlopen(f"{FRONTEND}/dashboard", timeout=10).status
        record("frontend_dashboard", code == 200, f"status={code}")
    except Exception as exc:  # noqa: BLE001
        record("frontend_dashboard", False, str(exc))

    failed = sum(1 for item in results if not item["ok"])
    print(json.dumps({"failed": failed, "results": results}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
