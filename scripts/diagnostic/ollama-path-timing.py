#!/usr/bin/env python3
"""Run a small number of real Ollama calls and print model-path timing logs."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "backend"))
os.environ.setdefault("ACADEMIC_MODEL_PROVIDER", "ollama")
os.environ.setdefault("LOCAL_API_GUARD_ENABLED", "false")

logging.basicConfig(level=logging.INFO, format="%(message)s")

from app.assistant_orchestration.models import AssistantModelInput, AssistantOperation, ToolPlan
from app.assistant_provider.ollama import OllamaAcademicModelProvider
from app.assistant_tools.models import AssistantRequest
from app.config import get_settings


def main() -> int:
    import time

    settings = get_settings()
    provider = OllamaAcademicModelProvider()
    model_input = AssistantModelInput(
        request=AssistantRequest(query="Define forward kinematics in one sentence.", course_id="101"),
        plan=ToolPlan(
            operation=AssistantOperation.STUDY_HELP,
            course_id="101",
            query="forward kinematics",
        ),
        context=None,
        evidence=(),
    )
    )
    runs = max(1, int(os.environ.get("OLLAMA_TIMING_RUNS", "3")))
    print(f"model={provider._model} base_url={settings.ollama_base_url} runs={runs}")
    for index in range(runs):
        print(f"--- run {index + 1}/{runs} complete ---")
        started = time.perf_counter()
        provider.complete(model_input)
        print(f"complete_wall_s={time.perf_counter() - started:.2f}")
        print(f"--- run {index + 1}/{runs} stream ---")
        started = time.perf_counter()
        for event in provider.stream(model_input):
            if event.type.value == "completed":
                print(f"stream_wall_s={time.perf_counter() - started:.2f}")
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
