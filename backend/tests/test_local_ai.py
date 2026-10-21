import httpx
import pytest
from app.api.routes import assistant as assistant_routes
from app.api.routes import benchmarks as benchmark_routes
from app.api.routes import local_ai as local_ai_routes
from app.benchmarks.models import BenchmarkCase, BenchmarkResult
from app.benchmarks.ollama import OllamaBenchmarkService
from app.config import Settings
from app.database.session import get_session
from app.local_ai.service import LocalAISettingsService, resolve_installed_model_name
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        academic_model_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="bootstrap:1b",
    )


def test_model_selection_persists_and_provider_consumes_it(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = LocalAISettingsService(session, _settings())
    installed = ("local:3b", "other:7b")
    selected = first.select("local:3b", installed_models=installed)
    assert selected.model == "local:3b"
    assert selected.source == "saved"
    assert LocalAISettingsService(session, _settings()).selection().model == "local:3b"

    captured: list[str | None] = []

    class FakeProvider:
        def __init__(self, *, model: str | None = None) -> None:
            captured.append(model)

    class FakeBenchmark:
        def __init__(self, settings: Settings) -> None:
            del settings

        def installed_models(self) -> tuple[str, ...]:
            return installed

        def close(self) -> None:
            return None

    monkeypatch.setattr(assistant_routes, "get_settings", _settings)
    monkeypatch.setattr(assistant_routes, "OllamaBenchmarkService", FakeBenchmark)
    monkeypatch.setattr(assistant_routes, "OllamaAcademicModelProvider", FakeProvider)
    assistant_routes.get_model_provider(session)
    LocalAISettingsService(session, _settings()).select("other:7b", installed_models=installed)
    assistant_routes.get_model_provider(session)
    assert captured == ["local:3b", "other:7b"]
    assert LocalAISettingsService(session, _settings()).selection().model == "other:7b"


def test_provider_resolves_untagged_selection_to_installed_identity(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[str | None] = []

    class FakeProvider:
        def __init__(self, *, model: str | None = None) -> None:
            captured.append(model)

    class FakeBenchmark:
        def __init__(self, settings: Settings) -> None:
            del settings

        def installed_models(self) -> tuple[str, ...]:
            return ("llama3.2:3b", "other:7b")

        def close(self) -> None:
            return None

    settings = Settings(
        _env_file=None,
        academic_model_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="llama3.2",
    )
    monkeypatch.setattr(assistant_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(assistant_routes, "OllamaBenchmarkService", FakeBenchmark)
    monkeypatch.setattr(assistant_routes, "OllamaAcademicModelProvider", FakeProvider)

    assistant_routes.get_model_provider(session)

    assert captured == ["llama3.2:3b"]


def test_model_identity_resolution_is_exact_or_unambiguous() -> None:
    assert resolve_installed_model_name("llama3.2", ("llama3.2:3b",)) == "llama3.2:3b"
    assert (
        resolve_installed_model_name(
            "llama3.2", ("llama3.2:1b", "llama3.2:3b")
        )
        == "llama3.2"
    )


def test_model_selection_rejects_uninstalled_model(session: Session) -> None:
    with pytest.raises(LookupError, match="not installed"):
        LocalAISettingsService(session, _settings()).select(
            "missing:7b", installed_models=("local:3b",)
        )
    assert LocalAISettingsService(session, _settings()).selection().model == "bootstrap:1b"


def test_installed_model_discovery_is_bounded_and_deterministic() -> None:
    names = [{"name": f"model-{index}:1b"} for index in range(25)]
    names.extend([{"name": "model-00:1b"}, {"name": ""}, {"bad": "value"}])

    def handle(request: httpx.Request) -> httpx.Response:
        timeout = request.extensions["timeout"]
        assert timeout["connect"] <= 5.0
        assert timeout["read"] <= 5.0
        return httpx.Response(200, json={"models": names}, request=request)

    client = httpx.Client(
        transport=httpx.MockTransport(handle),
        base_url="http://127.0.0.1:11434",
    )
    models = OllamaBenchmarkService(_settings(), client=client).installed_models()
    assert len(models) == 20
    assert models == tuple(sorted(set(models)))


def test_local_ai_model_api_uses_one_canonical_contract(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeBenchmark:
        def __init__(self, settings: Settings) -> None:
            del settings

        def installed_models(self) -> tuple[str, ...]:
            return ("local:3b",)

        def close(self) -> None:
            return None

    monkeypatch.setattr(local_ai_routes, "OllamaBenchmarkService", FakeBenchmark)
    monkeypatch.setattr(local_ai_routes, "get_settings", _settings)
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            response = client.put("/api/local-ai/model", json={"model": "local:3b"})
            loaded = client.get("/api/local-ai/model")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["model"] == "local:3b"
    assert loaded.status_code == 200
    assert loaded.json()["source"] == "saved"


def test_installed_models_api_hides_runtime_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailedBenchmark:
        def __init__(self, settings: Settings) -> None:
            del settings

        def installed_models(self) -> tuple[str, ...]:
            raise httpx.ConnectError("private runtime detail")

        def close(self) -> None:
            return None

    monkeypatch.setattr(benchmark_routes, "OllamaBenchmarkService", FailedBenchmark)
    with TestClient(app) as client:
        response = client.get("/api/benchmarks/ollama/models")
    assert response.status_code == 503
    assert response.json() == {"detail": "Local AI runtime is unavailable."}


def test_benchmark_api_uses_only_allowlisted_synthetic_prompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, ...]] = []

    class FakeBenchmark:
        def __init__(self, settings: Settings) -> None:
            del settings

        def run(
            self,
            models: tuple[str, ...],
            cases: tuple[BenchmarkCase, ...],
        ) -> tuple[BenchmarkResult, ...]:
            del models
            captured.append(tuple(case.prompt for case in cases))
            return ()

        def close(self) -> None:
            return None

    monkeypatch.setattr(benchmark_routes, "OllamaBenchmarkService", FakeBenchmark)
    with TestClient(app) as client:
        response = client.post(
            "/api/benchmarks/ollama",
            json={"models": ["local:3b"], "case_ids": ["short_reply"]},
        )
        rejected = client.post(
            "/api/benchmarks/ollama",
            json={
                "models": ["local:3b"],
                "case_ids": ["short_reply"],
                "cases": [{"case_id": "private", "prompt": "course content"}],
            },
        )
    assert response.status_code == 200
    assert captured == [("Reply with exactly one word: OK",)]
    assert rejected.status_code == 422
