from __future__ import annotations

from fastapi import Request
from starlette.responses import JSONResponse

from .errors import ScimApiError


def scim_api_error_handler(_request: Request, exc: ScimApiError) -> JSONResponse:
    payload: dict[str, str | list[str]] = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
        "detail": exc.detail,
        "status": str(exc.status_code),
    }
    if exc.scim_type:
        payload["scimType"] = exc.scim_type
    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        media_type="application/scim+json",
    )


__all__ = ["scim_api_error_handler"]
