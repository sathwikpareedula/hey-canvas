"""Verify /health stays responsive during a long assistant stream."""
from __future__ import annotations

import json
import threading
import time
import urllib.request

BASE = "http://127.0.0.1:8000"


def main() -> int:
    payload = {
        "query": "Teach me SLAM from Lecture 01 materials with citations.",
        "course_id": "278791",
    }
    events: list[str] = []

    def stream() -> None:
        req = urllib.request.Request(
            f"{BASE}/api/assistant/stream",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                for raw in response:
                    line = raw.decode().strip()
                    if line.startswith("data:"):
                        events.append(line[5:].strip())
        except Exception as exc:  # noqa: BLE001
            events.append(f"ERROR:{exc}")

    thread = threading.Thread(target=stream, daemon=True)
    thread.start()
    time.sleep(2)
    latencies: list[float] = []
    for _ in range(6):
        start = time.perf_counter()
        urllib.request.urlopen(f"{BASE}/health", timeout=5)
        latencies.append(time.perf_counter() - start)
        time.sleep(2)
    thread.join(timeout=280)
    terminal = next(
        (
            json.loads(event)
            for event in reversed(events)
            if event.startswith("{") and json.loads(event).get("type") in {"completed", "error"}
        ),
        None,
    )
    print("health_latencies_s", [round(value, 3) for value in latencies])
    print("stream_events", len(events), "terminal", terminal.get("type") if terminal else None)
    ok = all(value < 2.0 for value in latencies) and terminal is not None
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
