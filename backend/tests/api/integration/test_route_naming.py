"""Enforce lowerCamelCase path segments in API routes."""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from ade_api.main import create_app


@pytest.fixture()
def app(empty_database_settings):
    return create_app(settings=empty_database_settings)


def test_routes_use_lower_camel_case_segments(app) -> None:
    """Ensure no route segment contains '-' or ':' characters."""

    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        for segment in path.strip("/").split("/"):
            if not segment:
                continue
            if segment.startswith("{") and segment.endswith("}"):
                param_name = segment[1:-1].split(":", 1)[0]
                assert "-" not in param_name, f"Route segment contains '-': {path}"
                continue
            assert "-" not in segment, f"Route segment contains '-': {path}"
            assert ":" not in segment, f"Route segment contains ':': {path}"
