"""Repeat latency samples for top candidates (measurement only)."""
from __future__ import annotations

import json
import statistics
import time
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
PROMPT = (
    "EVIDENCE: The quiz covers chapters 4-5 only. "
    "QUESTION: Which chapters are on the quiz? One sentence."
)
MODELS = ["qwen3.5:2b", "qwen3:4b-instruct"]
RUNS = 3


def one(model: str) -> tuple[int | None, int]:
    body = {
        "model": model,
        "prompt": PROMPT,
        "stream": True,
        "think": False,
        "options": {"num_predict": 384, "temperature": 0.3},
    }
    started = time.monotonic()
    first_ms: int | None = None
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw in resp:
            item = json.loads(raw.decode())
            if item.get("response") and first_ms is None:
                first_ms = int((time.monotonic() - started) * 1000)
            if item.get("done"):
                break
    return first_ms, int((time.monotonic() - started) * 1000)


def main() -> None:
    for model in MODELS:
        totals: list[int] = []
        firsts: list[int] = []
        for i in range(RUNS):
            ft, tot = one(model)
            if ft is not None:
                firsts.append(ft)
            totals.append(tot)
            print(f"{model} run {i + 1}: ft={ft} total={tot}", flush=True)
        print(
            f"{model} median_ft={int(statistics.median(firsts)) if firsts else 'n/a'} "
            f"median_total={int(statistics.median(totals))}",
            flush=True,
        )


if __name__ == "__main__":
    main()
