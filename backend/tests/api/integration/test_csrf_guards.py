"""Ensure mutating routes enforce CSRF guards."""

from __future__ import annotations

import inspect
from collections.abc import Iterable

import pytest
from fastapi.routing import APIRoute

from ade_api.core.http import require_csrf
from ade_api.main import create_app


@pytest.fixture()
def app(empty_database_settings):
    return create_app(settings=empty_database_settings)

MUTATING_METHODS: set[str] = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_ROUTE_ALLOWLIST: set[tuple[str, str]] = {
    ("/api/v1/auth/setup", "POST"),
    ("/api/v1/auth/login", "POST"),
    ("/api/v1/auth/password/forgot", "POST"),
    ("/api/v1/auth/password/reset", "POST"),
    ("/api/v1/auth/mfa/challenge/verify", "POST"),
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


def test_mutating_routes_require_csrf(app) -> None:
    """All mutating routes should include the CSRF dependency unless allowlisted."""

    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/v1/"):
            continue
        if route.path.startswith("/api/v1/rbac"):
            # New RBAC endpoints are bearer-only; CSRF enforcement will be added separately.
            continue
        for method in MUTATING_METHODS & set(route.methods or {}):
            if (route.path, method) in CSRF_ROUTE_ALLOWLIST:
                continue
            assert _has_require_csrf(route), f"{route.path} missing CSRF guard"
