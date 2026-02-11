"""Exception handlers that translate auth errors to HTTP responses."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast
from urllib.parse import urlencode

from fastapi import FastAPI, Request, status
from starlette.responses import RedirectResponse, Response

from ade_api.common.exceptions import api_error_handler
from ade_api.common.problem_details import ApiError

from ..auth.errors import AuthenticationError, PermissionDeniedError

type HttpExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]
_DOCS_LOGIN_REDIRECT_PATHS = frozenset(
    {
        "/api",
        "/api/swagger",
        "/api/openapi.json",
        "/api/docs",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)


def _docs_login_redirect_location(request: Request) -> str | None:
    method = request.method.upper()
    if method not in {"GET", "HEAD"}:
        return None
    path = request.url.path
    if path not in _DOCS_LOGIN_REDIRECT_PATHS:
        return None

    return_to = path
    query = request.url.query
    if query:
        return_to = f"{return_to}?{query}"

    return f"/login?{urlencode({'returnTo': return_to})}"


def _handle_authentication_error(request: Request, exc: AuthenticationError) -> Response:
    """Translate auth failures into HTTP 401 responses."""

    docs_redirect = _docs_login_redirect_location(request)
    if docs_redirect:
        return RedirectResponse(url=docs_redirect, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    error = ApiError(
        error_type="unauthorized",
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=str(exc) or "Authentication required",
    )
    return api_error_handler(request, error)


def _handle_permission_error(request: Request, exc: PermissionDeniedError) -> Response:
    """Translate permission denials into HTTP 403 responses."""

    error = ApiError(
        error_type="forbidden",
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(exc) or "Forbidden",
    )
    return api_error_handler(request, error)


def register_auth_exception_handlers(app: FastAPI) -> None:
    """Attach auth/RBAC handlers to the FastAPI app."""

    app.add_exception_handler(
        AuthenticationError,
        cast(HttpExceptionHandler, _handle_authentication_error),
    )
    app.add_exception_handler(
        PermissionDeniedError,
        cast(HttpExceptionHandler, _handle_permission_error),
    )
