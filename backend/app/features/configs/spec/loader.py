"""Manifest loading helpers."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .exceptions import (
    ManifestConversionError,
    ManifestError,
    ManifestValidationError,
    UnsupportedConfigScriptApiVersionError,
    UnsupportedManifestSchemaError,
)
from .manifest import ManifestV1


class ManifestLoader:
    """Convert manifest payloads into normalized ``ManifestV1`` models."""

    def load(self, payload: dict[str, Any]) -> ManifestV1:
        schema = self._extract_schema(payload)
        if schema == "ade.manifest/v1.0":
            model = self._load_v1(payload)
            if model.config_script_api_version != "1":
                raise UnsupportedConfigScriptApiVersionError(model.config_script_api_version)
            return model
        raise UnsupportedManifestSchemaError(schema)

    def _load_v1(self, payload: dict[str, Any]) -> ManifestV1:
        try:
            return ManifestV1.model_validate(payload)
        except ValidationError as exc:  # pragma: no cover - defensive
            msg = "; ".join(error["msg"] for error in exc.errors())
            raise ManifestValidationError(msg) from exc

    @staticmethod
    def _extract_schema(payload: dict[str, Any]) -> str | None:
        info = payload.get("info")
        if isinstance(info, dict):
            schema = info.get("schema")
            if isinstance(schema, str):
                return schema
        return None


__all__ = ["ManifestLoader"]
