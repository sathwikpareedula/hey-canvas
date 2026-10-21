"""Credential-safe command for verifying permitted Canvas API access."""

import asyncio
import sys
from dataclasses import dataclass
from typing import Any

from app.canvas.client import CanvasClient
from app.canvas.exceptions import CanvasConfigurationError, CanvasError, CanvasResponseError
from app.config import get_settings
from app.logging import configure_logging
from app.security.canvas_credentials import resolve_canvas_token


@dataclass(frozen=True)
class CanvasConnectionInfo:
    """Non-secret result from Canvas's current-user profile endpoint."""

    user_id: str


async def verify_canvas_connection(client: CanvasClient) -> CanvasConnectionInfo:
    payload: Any = await client.get_json("/api/v1/users/self/profile")
    if not isinstance(payload, dict) or "id" not in payload:
        raise CanvasResponseError("Canvas profile response did not contain a user ID")
    return CanvasConnectionInfo(user_id=str(payload["id"]))


async def _run_check() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    token = resolve_canvas_token(settings)
    if settings.canvas_base_url is None or token is None:
        raise CanvasConfigurationError(
            "Set CANVAS_BASE_URL and CANVAS_TOKEN in local .env before running this check"
        )

    async with CanvasClient(
        base_url=settings.canvas_base_url,
        token=token,
    ) as client:
        info = await verify_canvas_connection(client)
    print(f"[OK] Canvas authentication verified for user ID {info.user_id}.")
    print("The token was not displayed and no Canvas data was synchronized.")
    return 0


def run() -> int:
    """Run the connectivity check and emit only credential-safe diagnostics."""

    try:
        return asyncio.run(_run_check())
    except CanvasError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())

