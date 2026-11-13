"""Typed application errors and a consistent JSON error envelope.

Every handled error returns ``{"error": {"code", "message", "details"}}`` so the
frontend can branch on a stable ``code`` rather than parsing prose.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for errors we deliberately surface to clients."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ProfileStoreDisabledError(AppError):
    """MongoDB isn't configured. 501 (not 503) so clients don't mistake it for a cold start."""

    status_code = 501
    code = "profile_store_disabled"


class ProfileStoreError(AppError):
    """MongoDB is configured but failed. 424 (not 502/503) for the same reason."""

    status_code = 424
    code = "profile_store_error"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str, *, retry_after: int) -> None:
        super().__init__(message, details={"retry_after_sec": retry_after})
        self.retry_after = retry_after


_log = logging.getLogger("uvicorn.error.cadence.errors")


def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Any crash answers in the same JSON envelope as every other error (so the UI can show
    a real message instead of "Request failed"); the traceback goes to the server log."""
    _log.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Something went wrong on our side. Please try again.",
                "details": None,
            }
        },
    )


def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, RateLimitError) else None
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message, "details": exc.details}
        },
        headers=headers,
    )
