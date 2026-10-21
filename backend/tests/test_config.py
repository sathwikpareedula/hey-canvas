import pytest
from app.config import Settings


def test_pytest_environment_cannot_inherit_live_canvas_credentials() -> None:
    settings = Settings()
    assert settings.app_env == "test"
    assert settings.canvas_base_url in {None, ""}
    assert settings.canvas_token is None or not settings.canvas_token.get_secret_value()
    assert settings.academic_model_provider == "synthetic"

    from app.security.canvas_credential_store import _default_store_path

    assert "pytest-tmp" in str(_default_store_path())
from pydantic import ValidationError


def test_settings_accept_a_valid_iana_timezone() -> None:
    settings = Settings(_env_file=None, academic_timezone="America/New_York")

    assert settings.academic_timezone == "America/New_York"


def test_settings_reject_an_unknown_timezone() -> None:
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        Settings(_env_file=None, academic_timezone="Mars/Olympus_Mons")


@pytest.mark.parametrize(
    "field",
    [
        "max_document_characters",
        "max_document_units",
        "max_document_unit_characters",
        "max_document_archive_entries",
        "max_document_archive_uncompressed_bytes",
        "max_document_archive_ratio",
    ],
)
def test_document_resource_limits_must_be_positive(field: str) -> None:
    with pytest.raises(ValidationError, match="document resource limits must be positive"):
        Settings(_env_file=None, **{field: 0})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ollama_num_predict", 31),
        ("ollama_num_predict", 901),
        ("ollama_context_length", 1024),
        ("ollama_context_length", 32769),
        ("ollama_keep_alive_seconds", -1),
        ("ollama_keep_alive_seconds", 3601),
    ],
)
def test_ollama_runtime_bounds_are_validated(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
