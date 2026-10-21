"""Credential-safe exception hierarchy for Canvas integration failures."""


class CanvasError(Exception):
    """Base exception for expected Canvas integration failures."""


class CanvasConfigurationError(CanvasError):
    """Local Canvas configuration is absent or unsafe."""


class CanvasTransportError(CanvasError):
    """Canvas could not be reached after bounded retries."""


class CanvasAuthenticationError(CanvasError):
    """Canvas rejected the configured credential or permission."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CanvasRateLimitError(CanvasError):
    """Canvas continued to rate-limit requests after bounded retries."""

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class CanvasAPIError(CanvasError):
    """Canvas returned a non-success response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CanvasResponseError(CanvasError):
    """Canvas returned a success response with an unexpected shape."""
