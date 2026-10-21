"""Resolve Canvas credentials without exposing secrets through APIs."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from app.config import Settings
from app.security.canvas_credential_store import (
    load_stored_canvas_token,
    migrate_env_token_to_store,
    store_status,
)


def resolve_canvas_token(settings: Settings) -> SecretStr | None:
    """Environment token wins for backward compatibility; else DPAPI store."""
    if settings.canvas_token is not None:
        secret = settings.canvas_token.get_secret_value().strip()
        if secret:
            return settings.canvas_token
    return load_stored_canvas_token()


def canvas_configured(settings: Settings) -> bool:
    return bool(settings.canvas_base_url and resolve_canvas_token(settings))


def env_file_lists_canvas_token(env_path: Path | None = None) -> bool:
    """Detect plaintext CANVAS_TOKEN in local .env (warning signal only)."""
    path = env_path or Path(".env")
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.upper().startswith("CANVAS_TOKEN="):
                value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                return bool(value)
    except OSError:
        return False
    return False


def bootstrap_credential_storage(settings: Settings) -> None:
    """Optional migration hook; safe to call on startup."""
    if settings.canvas_token is not None:
        migrate_env_token_to_store(settings.canvas_token)


def credential_protection_summary(settings: Settings) -> tuple[str, str]:
    """Return (status_level, student_message) without secrets."""
    status = store_status()
    env_plain = env_file_lists_canvas_token()
    has_token = canvas_configured(settings)

    if not has_token:
        return (
            "not_checked",
            "Canvas is not configured yet. Add your token during setup.",
        )

    if status.has_token and not env_plain:
        return (
            "pass",
            "Your Canvas token is stored with Windows secure storage on this account.",
        )

    if status.has_token and env_plain:
        return (
            "warning",
            "Your token is protected in Windows storage, but a copy may still exist in "
            "your local .env file. Remove it from .env when you are ready.",
        )

    if env_plain and sys_platform_supports_dpapi():
        return (
            "warning",
            "Your Canvas token is only in your local .env file. Consider moving it to "
            "Windows secure storage from Settings → Security & Health.",
        )

    if env_plain:
        return (
            "warning",
            "Your Canvas token is stored in a local environment file on this computer.",
        )

    return ("pass", "Canvas credentials are configured locally.")


def sys_platform_supports_dpapi() -> bool:
    import sys

    return sys.platform == "win32"
