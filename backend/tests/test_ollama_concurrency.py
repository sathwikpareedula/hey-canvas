import time

from app.assistant_provider.ollama_concurrency import ollama_generate_slot


def test_second_slot_waits_or_raises_when_busy(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_MAX_CONCURRENT_REQUESTS", "1")
    monkeypatch.setenv("OLLAMA_QUEUE_WAIT_SECONDS", "1")
    from app.assistant_provider import ollama_concurrency as mod
    from app.config import get_settings

    get_settings.cache_clear()
    mod._semaphore = None

    with ollama_generate_slot():
        started = time.perf_counter()
        raised = False
        try:
            with ollama_generate_slot():
                pass
        except RuntimeError as exc:
            raised = True
            assert "local_ai_busy" in str(exc).lower() or "another" in str(exc).lower()
        assert raised
        assert time.perf_counter() - started < 2.0
