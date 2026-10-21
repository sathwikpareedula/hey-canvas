import httpx
from app.benchmarks.models import BenchmarkCase
from app.benchmarks.ollama import OllamaBenchmarkService
from app.config import Settings


def test_ollama_benchmark_uses_selected_installed_models_and_isolates_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "local:3b"}]})
        if request.url.path == "/api/generate":
            body = request.read().decode()
            if "broken:3b" in body:
                return httpx.Response(503)
            return httpx.Response(
                200,
                content=b'{"response":"{\\"ok\\":true}","done":true}\n',
            )
        return httpx.Response(404)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://127.0.0.1:11434",
    )
    service = OllamaBenchmarkService(
        Settings(ollama_base_url="http://127.0.0.1:11434"),
        client=client,
    )
    results = service.run(
        ("local:3b", "broken:3b"),
        (BenchmarkCase(case_id="structured", prompt="return JSON"),),
    )

    assert results[0].success
    assert results[0].provider == "ollama"
    assert results[0].structured_output_valid
    assert results[1].error == "model_not_installed"


def test_two_link_kinematics_guidance_preserves_relative_vs_absolute_conventions():
    from app.assistant_provider.ollama import _relative_angle_kinematics_guidance

    hint = _relative_angle_kinematics_guidance(
        "Explain two-link planar forward kinematics using relative joint angles"
    )
    assert hint is not None
    assert "theta1 + theta2" in hint
    assert "x = l1 cos(theta1) + l2 cos(theta1 + theta2)" in hint
    assert "y = l1 sin(theta1) + l2 sin(theta1 + theta2)" in hint
    assert "not a claim about a Canvas quiz" in hint
    assert _relative_angle_kinematics_guidance(
        "Explain two-link forward kinematics with absolute link angles"
    ) is None
    assert _relative_angle_kinematics_guidance(
        "Explain two-link forward kinematics with absolute joint angles"
    ) is None
    assert _relative_angle_kinematics_guidance("Explain A* search") is None
