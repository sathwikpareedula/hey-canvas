"""Deterministic benchmark runner for configured providers only."""

from collections.abc import Callable
from time import monotonic

from app.benchmarks.models import BenchmarkCase, BenchmarkResult


class BenchmarkService:
    def __init__(self, *, model_name: str, runner: Callable[[str], str]) -> None:
        self._model_name = model_name
        self._runner = runner

    def run(self, cases: tuple[BenchmarkCase, ...]) -> tuple[BenchmarkResult, ...]:
        if len(cases) > 50:
            raise ValueError("benchmark is limited to 50 cases")
        results: list[BenchmarkResult] = []
        for case in cases:
            started = monotonic()
            try:
                output = self._runner(case.prompt)
                elapsed = int((monotonic() - started) * 1000)
                bounded = output[:4000]
                results.append(
                    BenchmarkResult(
                        case_id=case.case_id,
                        provider="synthetic",
                        model=self._model_name,
                        success=bool(bounded.strip()),
                        timed_out=False,
                        first_token_ms=None,
                        total_ms=elapsed,
                        structured_output_valid=bounded.lstrip().startswith("{"),
                        output=bounded,
                    )
                )
            except TimeoutError:
                results.append(
                    BenchmarkResult(
                        case_id=case.case_id,
                        provider="synthetic",
                        model=self._model_name,
                        success=False,
                        timed_out=True,
                        first_token_ms=None,
                        total_ms=int((monotonic() - started) * 1000),
                        structured_output_valid=False,
                        output="",
                        error="timeout",
                    )
                )
            except (RuntimeError, ValueError, TypeError) as exc:
                results.append(
                    BenchmarkResult(
                        case_id=case.case_id,
                        provider="synthetic",
                        model=self._model_name,
                        success=False,
                        timed_out=False,
                        first_token_ms=None,
                        total_ms=int((monotonic() - started) * 1000),
                        structured_output_valid=False,
                        output="",
                        error=type(exc).__name__,
                    )
                )
        return tuple(results)
