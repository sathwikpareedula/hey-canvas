"""Structured timing logs for the local Ollama model path."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPathTiming:
    model: str
    mode: str
    prompt_chars: int
    prompt_build_ms: float
    queue_wait_ms: float
    request_ms: float
    first_token_ms: float | None
    total_ms: float
    cancelled: bool = False

    def emit(self) -> None:
        logger.info("ollama_model_path_timing %s", asdict(self))
