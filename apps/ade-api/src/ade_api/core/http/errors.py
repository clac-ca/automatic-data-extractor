"""Exception handlers that translate auth errors to HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, status

from ..auth.errors import AuthenticationError, PermissionDeniedError
from ade_api.common.exceptions import api_error_handler
from ade_api.common.problem_details import ApiError


async def _handle_authentication_error(request, exc: AuthenticationError):
    """Translate auth failures into HTTP 401 responses."""

    error = ApiError(
        error_type="unauthorized",
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=str(exc) or "Authentication required",
    )
    return await api_error_handler(request, error)


async def _handle_permission_error(request, exc: PermissionDeniedError):
    """Translate permission denials into HTTP 403 responses."""

    error = ApiError(
        error_type="forbidden",
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(exc) or "Forbidden",
    )
    return await api_error_handler(request, error)


def register_auth_exception_handlers(app: FastAPI) -> None:
    """Attach auth/RBAC handlers to the FastAPI app."""

    app.add_exception_handler(AuthenticationError, _handle_authentication_error)
    app.add_exception_handler(PermissionDeniedError, _handle_permission_error)
