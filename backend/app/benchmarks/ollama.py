"""Bounded real-local Ollama benchmark execution."""

from __future__ import annotations

import json
from time import monotonic

import httpx

from app.assistant_provider.ollama import _normalize_base_url
from app.benchmarks.models import BenchmarkCase, BenchmarkResult
from app.config import Settings

_MAX_BENCHMARK_RESPONSE_BYTES = 1_000_000
_MODEL_DISCOVERY_TIMEOUT_SECONDS = 5.0


class OllamaBenchmarkService:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._base_url = _normalize_base_url(settings.ollama_base_url)
        self._timeout = min(settings.assistant_request_timeout_seconds, 300.0)
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            follow_redirects=False,
        )

    def installed_models(self) -> tuple[str, ...]:
        response = self._client.get("/api/tags", timeout=_MODEL_DISCOVERY_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = {
            item["name"].strip()
            for item in models
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and item["name"].strip()
            and len(item["name"].strip()) <= 255
        }
        return tuple(sorted(names)[:20])

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def run(
        self,
        models: tuple[str, ...],
        cases: tuple[BenchmarkCase, ...],
    ) -> tuple[BenchmarkResult, ...]:
        installed = set(self.installed_models())
        selected = tuple(dict.fromkeys(models))
        if not selected or len(selected) > 10:
            raise ValueError("select between 1 and 10 benchmark models")
        results: list[BenchmarkResult] = []
        for model in selected:
            if model not in installed:
                results.extend(
                    BenchmarkResult(
                        case_id=case.case_id,
                        provider="ollama",
                        model=model,
                        success=False,
                        timed_out=False,
                        first_token_ms=None,
                        total_ms=0,
                        structured_output_valid=False,
                        output="",
                        error="model_not_installed",
                    )
                    for case in cases
                )
                continue
            for case in cases:
                results.append(self._run_case(model, case))
        return tuple(results)

    def _run_case(self, model: str, case: BenchmarkCase) -> BenchmarkResult:
        started = monotonic()
        first_token_ms: int | None = None
        output: list[str] = []
        response_bytes = 0
        try:
            with self._client.stream(
                "POST",
                "/api/generate",
                json={"model": model, "prompt": case.prompt, "stream": True},
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    response_bytes += len(line.encode("utf-8"))
                    if response_bytes > _MAX_BENCHMARK_RESPONSE_BYTES:
                        raise RuntimeError("benchmark response exceeded its size limit")
                    item = json.loads(line)
                    chunk = item.get("response") if isinstance(item, dict) else None
                    if isinstance(chunk, str) and chunk:
                        if first_token_ms is None:
                            first_token_ms = int((monotonic() - started) * 1000)
                        output.append(chunk)
                    if isinstance(item, dict) and item.get("done"):
                        break
            text = "".join(output)[:4000]
            return BenchmarkResult(
                case_id=case.case_id,
                provider="ollama",
                model=model,
                success=bool(text.strip()),
                timed_out=False,
                first_token_ms=first_token_ms,
                total_ms=int((monotonic() - started) * 1000),
                structured_output_valid=_structured_valid(text),
                output=text,
            )
        except httpx.TimeoutException:
            return self._failure(case, model, started, "timeout", timed_out=True)
        except (httpx.HTTPError, ValueError, TypeError, RuntimeError) as exc:
            return self._failure(case, model, started, type(exc).__name__)

    @staticmethod
    def _failure(
        case: BenchmarkCase,
        model: str,
        started: float,
        error: str,
        *,
        timed_out: bool = False,
    ) -> BenchmarkResult:
        return BenchmarkResult(
            case_id=case.case_id,
            provider="ollama",
            model=model,
            success=False,
            timed_out=timed_out,
            first_token_ms=None,
            total_ms=int((monotonic() - started) * 1000),
            structured_output_valid=False,
            output="",
            error=error,
        )


def _structured_valid(text: str) -> bool:
    if not text.lstrip().startswith(("{", "[")):
        return False
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return False
    return True
