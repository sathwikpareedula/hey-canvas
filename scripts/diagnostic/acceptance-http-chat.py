"""HTTP acceptance: assistant respond/stream against local backend (no secrets)."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
COURSE = "278791"


def post_json(path: str, body: dict, timeout: float = 240.0) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    cases = [
        ("due_soon", {"query": "What is due soon in this course?", "course_id": COURSE}),
        (
            "lecture_robot",
            {
                "query": "How does Lecture 01 define a robot? Use course materials only.",
                "course_id": COURSE,
            },
        ),
        (
            "braitenberg_limit",
            {
                "query": "Summarize Braitenberg vehicles from our readings.",
                "course_id": COURSE,
            },
        ),
    ]
    failed = 0
    for name, payload in cases:
        try:
            result = post_json("/api/assistant/respond", payload)
        except urllib.error.URLError as exc:
            print(f"FAIL {name}: backend unreachable ({exc})")
            failed += 1
            continue
        blocks = result.get("blocks") or []
        text_bits = [b.get("text") or "" for b in blocks if b.get("type") == "text"]
        refs = [
            ref
            for b in blocks
            for ref in (b.get("references") or [])
        ]
        print(f"OK {name}: blocks={len(blocks)} text_len={sum(len(t) for t in text_bits)} refs={len(refs)}")
        if name == "lecture_robot" and not any(text_bits):
            print(f"  WARN {name}: empty text response")
            failed += 1
    search_url = (
        f"{BASE}/api/retrieval/search?q=braitenberg&course_id={COURSE}&limit=3"
    )
    with urllib.request.urlopen(search_url, timeout=30) as resp:
        search = json.loads(resp.read().decode("utf-8"))
    print(
        "retrieval_braitenberg:",
        f"results={len(search.get('results') or [])}",
        f"limitation={search.get('index_limitation')}",
    )
    if not search.get("results") and not search.get("index_limitation"):
        print("FAIL retrieval_braitenberg: expected limitation or hits")
        failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
