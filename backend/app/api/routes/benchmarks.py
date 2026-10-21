from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.benchmarks.models import BenchmarkCase, BenchmarkResult
from app.benchmarks.ollama import OllamaBenchmarkService
from app.benchmarks.service import BenchmarkService
from app.config import get_settings
from app.database.session import get_session
from app.local_ai.models import InstalledModelsResponse

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


class BenchmarkRequest(BaseModel):
    cases: tuple[BenchmarkCase, ...] = Field(max_length=50)


class SafeLocalBenchmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    models: tuple[str, ...] = Field(min_length=1, max_length=10)
    case_ids: tuple[str, ...] = Field(
        default=("short_reply", "structured_json"), min_length=1, max_length=2
    )


LOCAL_BENCHMARK_CASES = {
    "short_reply": BenchmarkCase(case_id="short_reply", prompt="Reply with exactly one word: OK"),
    "structured_json": BenchmarkCase(
        case_id="structured_json", prompt='Return only JSON: {"ok":true}'
    ),
}


@router.post("/synthetic", response_model=tuple[BenchmarkResult, ...])
def benchmark_synthetic(
    request: BenchmarkRequest,
    session: Annotated[Session, Depends(get_session)],
) -> tuple[BenchmarkResult, ...]:
    del session
    def run(prompt: str) -> str:
        return f"Synthetic benchmark response for: {prompt[:1000]}"

    try:
        return BenchmarkService(model_name="synthetic", runner=run).run(request.cases)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ollama/models", response_model=InstalledModelsResponse)
def installed_ollama_models() -> InstalledModelsResponse:
    service = OllamaBenchmarkService(get_settings())
    try:
        return InstalledModelsResponse(models=service.installed_models())
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Local AI runtime is unavailable.") from exc
    finally:
        service.close()


@router.post("/ollama", response_model=tuple[BenchmarkResult, ...])
def benchmark_ollama(request: SafeLocalBenchmarkRequest) -> tuple[BenchmarkResult, ...]:
    try:
        cases = tuple(LOCAL_BENCHMARK_CASES[case_id] for case_id in request.case_ids)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="unknown synthetic benchmark case") from exc
    service = OllamaBenchmarkService(get_settings())
    try:
        return service.run(request.models, cases)
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="local benchmark unavailable") from exc
    finally:
        service.close()
