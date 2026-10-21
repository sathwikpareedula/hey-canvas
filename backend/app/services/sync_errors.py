"""Public-safe diagnostics for expected Canvas synchronization failures."""

from app.canvas.exceptions import (
    CanvasAPIError,
    CanvasAuthenticationError,
    CanvasError,
    CanvasRateLimitError,
    CanvasResponseError,
    CanvasTransportError,
)


def safe_sync_failure_message(exc: Exception, *, local_message: str) -> str:
    """Describe a failure without reflecting exception text or upstream payloads."""

    if isinstance(exc, CanvasAuthenticationError):
        return "Canvas authentication or authorization failed"
    if isinstance(exc, CanvasRateLimitError):
        return "Canvas rate limiting prevented synchronization"
    if isinstance(exc, CanvasTransportError):
        return "Canvas could not be reached"
    if isinstance(exc, CanvasResponseError):
        return "Canvas returned an invalid response"
    if isinstance(exc, CanvasAPIError):
        status = exc.status_code
        return (
            f"Canvas request failed with status {status}"
            if status is not None
            else "Canvas request failed"
        )
    if isinstance(exc, CanvasError):
        return "Canvas synchronization failed"
    return local_message
