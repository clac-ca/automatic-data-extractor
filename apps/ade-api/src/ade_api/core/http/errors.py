"""Exception handlers that translate auth errors to HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from ..auth.errors import AuthenticationError, PermissionDeniedError


def _handle_authentication_error(_request, exc: AuthenticationError) -> JSONResponse:
    """Translate auth failures into HTTP 401 responses."""

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc) or "Authentication required"},
    )


def _handle_permission_error(_request, exc: PermissionDeniedError) -> JSONResponse:
    """Translate permission denials into HTTP 403 responses."""

    detail = {
        "error": "forbidden",
        "permission": exc.permission_key,
        "scope_type": exc.scope_type,
        "scope_id": exc.scope_id,
    }
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": detail},
    )


def register_auth_exception_handlers(app: FastAPI) -> None:
    """Attach auth/RBAC handlers to the FastAPI app."""

    app.add_exception_handler(AuthenticationError, _handle_authentication_error)
    app.add_exception_handler(PermissionDeniedError, _handle_permission_error)
