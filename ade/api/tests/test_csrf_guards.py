"""Ensure mutating routes enforce CSRF guards."""

from __future__ import annotations

import inspect
from collections.abc import Iterable

from fastapi.routing import APIRoute

from ade.api.security import require_csrf
from ade.main import app

MUTATING_METHODS: set[str] = {"POST", "PUT", "PATCH", "DELETE"}
# Routes that intentionally omit CSRF enforcement because they either run
# before a session exists or perform safe permission evaluation.
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
    violations: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = set(route.methods or []) & MUTATING_METHODS
        if not methods:
            continue
        if all((route.path, method) in CSRF_ROUTE_ALLOWLIST for method in methods):
            continue
        if not _has_require_csrf(route):
            violations.append(f"{route.path} [{', '.join(sorted(methods))}]")
    assert not violations, "Routes missing require_csrf guard: " + ", ".join(violations)
