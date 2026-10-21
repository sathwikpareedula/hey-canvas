from app.api.assistant_stream_errors import format_assistant_stream_error


def test_maps_raw_network_error() -> None:
    text = format_assistant_stream_error(RuntimeError("network error"))
    assert "network error" not in text.lower() or "connection" in text.lower()
    assert "retry" in text.lower()


def test_maps_local_ai_busy() -> None:
    text = format_assistant_stream_error(RuntimeError("local_ai_busy: queue"))
    assert "another question" in text.lower()
