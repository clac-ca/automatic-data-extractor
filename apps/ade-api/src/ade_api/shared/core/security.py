"""Helpers for evaluating security scopes in HTTP routes."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.security import SecurityScopes


def forbidden_response(
    *, permission: str, scope_type: str, scope_id: str | None
) -> HTTPException:
    detail = {
        "error": "forbidden",
        "permission": permission,
        "scope_type": scope_type,
        "scope_id": scope_id,
    }
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)


def resolve_workspace_scope(
    *,
    request: Request,
    security_scopes: SecurityScopes,
    default_param: str,
    permission: str | None = None,
) -> str:
    param_name = default_param
    for scope in security_scopes.scopes:
        if scope.startswith("{") and scope.endswith("}") and len(scope) > 2:
            param_name = scope[1:-1]
            break

    workspace_id = request.path_params.get(param_name) or request.query_params.get(param_name)
    if not workspace_id:
        detail = {
            "error": "invalid_scope",
            "scope_type": "workspace",
            "scope_param": param_name,
            "message": f"Workspace scope parameter '{param_name}' is required.",
        }
        if permission is not None:
            detail["permission"] = permission
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)
    return str(workspace_id)


__all__ = ["forbidden_response", "resolve_workspace_scope"]
