"""Ensure mutating routes enforce CSRF guards."""

from __future__ import annotations

import inspect
from collections.abc import Iterable

from fastapi.routing import APIRoute

from backend.app.features.auth.dependencies import require_csrf
from backend.app.app import create_app

app = create_app()

MUTATING_METHODS: set[str] = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_ROUTE_ALLOWLIST: set[tuple[str, str]] = {
    ("/api/v1/setup", "POST"),
    ("/api/v1/auth/session", "POST"),
    ("/api/v1/auth/session/refresh", "POST"),
    ("/api/v1/me/permissions/check", "POST"),
}


def _dependency_calls(route: APIRoute) -> Iterable[object]:
    stack = list(route.dependant.dependencies)
    seen: set[int] = set()
    while stack:
        dependency = stack.pop()
        if id(dependency) in seen:
            continue
        seen.add(id(dependency))
        call = getattr(dependency, "call", None)
        if call is not None:
            yield inspect.unwrap(call)
        stack.extend(dependency.dependencies)


def _has_require_csrf(route: APIRoute) -> bool:
    return any(call is require_csrf for call in _dependency_calls(route))


def test_mutating_routes_require_csrf() -> None:
    """All mutating routes should include the CSRF dependency unless allowlisted."""

    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in MUTATING_METHODS & set(route.methods or {}):
            if (route.path, method) in CSRF_ROUTE_ALLOWLIST:
                continue
            assert _has_require_csrf(route), f"{route.path} missing CSRF guard"
