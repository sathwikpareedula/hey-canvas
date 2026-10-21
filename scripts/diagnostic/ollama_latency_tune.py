"""Compare latency-related Ollama options on a fixed synthetic prompt."""
from __future__ import annotations

import json
import time
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
MODEL = "qwen3:4b-instruct"
PROMPT = (
    "EVIDENCE: The quiz covers chapters 4-5 only. "
    "QUESTION: Which chapters are on the quiz? One sentence."
)

CONFIGS = [
    {"label": "baseline", "options": {"num_predict": 384, "temperature": 0.3}},
    {"label": "shorter_output", "options": {"num_predict": 128, "temperature": 0.2}},
    {"label": "low_temp", "options": {"num_predict": 256, "temperature": 0.0}},
]


def run_once(options: dict) -> tuple[int | None, int]:
    body = {
        "model": MODEL,
        "prompt": PROMPT,
        "stream": True,
        "think": False,
        "options": options,
    }
    started = time.monotonic()
    first_ms: int | None = None
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        for raw in resp:
            item = json.loads(raw.decode())
            if item.get("response") and first_ms is None:
                first_ms = int((time.monotonic() - started) * 1000)
            if item.get("done"):
                break
    return first_ms, int((time.monotonic() - started) * 1000)


def main() -> None:
    # Warm model
    run_once({"num_predict": 8, "temperature": 0.0})
    for cfg in CONFIGS:
        ft, tot = run_once(cfg["options"])
        print(f"{cfg['label']}: first_token_ms={ft} total_ms={tot}")


if __name__ == "__main__":
    main()
