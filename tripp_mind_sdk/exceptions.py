"""SDK exception hierarchy."""

from __future__ import annotations

from typing import Any, Optional


class TrippMindError(Exception):
    """Base exception for all SDK errors."""


class TransportError(TrippMindError):
    """Raised when the SDK cannot reach the API gateway."""


class ApiError(TrippMindError):
    """Raised when the gateway or Tripp.Mind API returns an error response."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[int] = None,
        status_code: Optional[int] = None,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data

    def __str__(self) -> str:
        details = []
        if self.code is not None:
            details.append(f"code={self.code}")
        if self.status_code is not None:
            details.append(f"status_code={self.status_code}")
        if not details:
            return self.message
        return f"{self.message} ({', '.join(details)})"


class AuthenticationError(ApiError):
    """Raised when the JWT token is missing, invalid, or expired."""


class AuthorizationError(ApiError):
    """Raised when the authenticated token is not allowed to call an endpoint."""


class RateLimitError(ApiError):
    """Raised when the API gateway rate limit is exceeded."""
