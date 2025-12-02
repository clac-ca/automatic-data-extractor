"""Custom response classes built on ADE schema conventions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from starlette.background import BackgroundTask
from starlette.responses import Response

from ade_api.common.encoding import json_bytes
from .schema import BaseSchema


class JSONResponse(Response):
    """Response class that understands ADE BaseSchema instances."""

    media_type = "application/json"

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            headers=dict(headers or {}),
            media_type=media_type or self.media_type,
            background=background,
        )
        self.body = self.render(content)

    def render(self, content: Any) -> bytes:  # noqa: D401 - standard Starlette signature
        if content is None:
            return b"null"

        prepared = _prepare_payload(content)
        return _encode_payload(prepared)


class DefaultResponse(BaseSchema):
    """Consistent envelope for success/failure acknowledgements."""

    status: bool
    message: str
    details: dict[str, Any] | None = None

    @classmethod
    def success(
        cls,
        message: str = "OK",
        *,
        details: dict[str, Any] | None = None,
    ) -> DefaultResponse:
        """Return a successful response wrapper."""

        return cls(status=True, message=message, details=details)

    @classmethod
    def failure(
        cls,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> DefaultResponse:
        """Return a failure response wrapper."""

        return cls(status=False, message=message, details=details)


def _prepare_payload(content: Any) -> Any:
    if isinstance(content, BaseSchema):
        return content.serializable_dict()

    if isinstance(content, Mapping):
        return {key: _prepare_payload(value) for key, value in content.items()}

    if isinstance(content, (list, tuple, set)):
        return [_prepare_payload(item) for item in content]

    return content


def _encode_payload(content: Any) -> bytes:
    return json_bytes(content, separators=(",", ":"))


__all__ = ["DefaultResponse", "JSONResponse"]
