"""Shared Pydantic schema utilities."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base class for all API schemas with ADE defaults."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        use_enum_values=True,
        extra="ignore",
        ser_json_timedelta="iso8601",
    )

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

        return self.model_dump_json(exclude_none=exclude_none, by_alias=by_alias).encode("utf-8")


__all__ = ["BaseSchema"]
