"""Shared Pydantic schema utilities."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base class for all API schemas with ADE defaults."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        use_enum_values=True,
        ser_json_timedelta="iso8601",
    )

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Ensure serialization defaults exclude ``None`` and honor aliases."""

        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        """JSON serialization with ADE defaults."""

        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(*args, **kwargs)

    def serializable_dict(
        self,
        *,
        exclude_none: bool = True,
        by_alias: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return a dict representation suited for JSON responses."""

        return self.model_dump(exclude_none=exclude_none, by_alias=by_alias, **kwargs)

    def json_bytes(self, *, exclude_none: bool = True, by_alias: bool = True) -> bytes:
        """Encode the schema as JSON bytes."""

        serialized = self.model_dump_json(exclude_none=exclude_none, by_alias=by_alias)
        return serialized.encode("utf-8")


class ErrorMessage(BaseSchema):
    """Standard error envelope mirroring FastAPI's ``{"detail": ...}`` payload."""

    detail: str | dict[str, Any]


__all__ = ["BaseSchema", "ErrorMessage"]
