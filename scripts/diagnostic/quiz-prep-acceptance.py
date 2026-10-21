"""Quiz-prep acceptance probe (no secrets)."""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
QUERY = (
    "I am preparing for Quiz 3. When is it due, what topics does the course "
    "announcement say to study, and teach me SLAM basics from our lecture "
    "materials with citations."
)


def main() -> int:
    payload = {"query": QUERY, "course_id": "278791"}
    req = urllib.request.Request(
        f"{BASE}/api/assistant/stream",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    completed = None
    last_events: list[dict] = []
    with urllib.request.urlopen(req, timeout=300) as response:
        for raw in response:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            last_events.append(event)
            if len(last_events) > 8:
                last_events.pop(0)
            if event.get("type") == "completed":
                completed = event
    if completed is None:
        print("FAIL: no completed event; tail=", last_events)
        return 1
    body = completed["response"]
    blocks = body.get("blocks") or []
    text = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
    all_refs: list[dict] = []
    for block in blocks:
        all_refs.extend(block.get("references") or [])
    evidence = next((b for b in blocks if b.get("type") == "document_evidence"), None)
    ev_refs = (evidence or {}).get("references") or []
    print(f"status={body.get('status')} text_len={len(text)} text_refs={len(all_refs)}")
    print(f"document_evidence_refs={len(ev_refs)} block_types={[b.get('type') for b in blocks]}")
    for ref in ev_refs[:6]:
        print(f"  ref {ref.get('authority')} {ref.get('identifier')} {ref.get('locator')}")
    checks = {
        "quiz3": "quiz 3" in text.casefold(),
        "slam": "slam" in text.casefold(),
        "oct20": "oct" in text.casefold() and "20" in text,
        "refs": len(ev_refs) > 0,
    }
    print("checks", checks)
    print("snippet", text[:600].replace("\n", " "))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
