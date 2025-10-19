"""Platform security primitives."""

from .permissions import forbidden_response, resolve_workspace_scope

__all__ = [
    "forbidden_response",
    "resolve_workspace_scope",
]
