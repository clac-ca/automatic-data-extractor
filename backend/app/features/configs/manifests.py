"""Helpers for reading and writing configuration manifests."""

from __future__ import annotations

import json
from pydantic import ValidationError

from .exceptions import ConfigFileNotFoundError, ManifestInvalidError
from .files import ConfigFilesystem
from .schemas import Manifest


def load_manifest(filesystem: ConfigFilesystem, config_id: str) -> Manifest:
    """Load and validate the manifest for ``config_id``."""

    try:
        payload = filesystem.read_text(config_id, "manifest.json")
    except FileNotFoundError as exc:
        raise ConfigFileNotFoundError(config_id, "manifest.json") from exc
    return _decode_manifest(config_id, payload)


def save_manifest(
    filesystem: ConfigFilesystem, config_id: str, manifest: Manifest
) -> Manifest:
    """Persist ``manifest`` for ``config_id`` returning a deep copy."""

    serialized = _encode_manifest(manifest)
    filesystem.write_text(config_id, "manifest.json", serialized)
    return manifest.model_copy(deep=True)


def _decode_manifest(config_id: str, payload: str) -> Manifest:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ManifestInvalidError(
            config_id,
            f"manifest.json is not valid JSON: {exc.msg} (line {exc.lineno} column {exc.colno})",
        ) from exc

    try:
        manifest = Manifest.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(error.get("msg", "invalid value") for error in exc.errors())
        message = "manifest.json does not conform to the v0.5 schema"
        if details:
            message = f"{message}: {details}"
        raise ManifestInvalidError(config_id, message) from exc
    return manifest.model_copy(deep=True)


def _encode_manifest(manifest: Manifest) -> str:
    payload = manifest.model_dump(mode="json")
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if not serialized.endswith("\n"):
        serialized += "\n"
    return serialized


__all__ = ["load_manifest", "save_manifest"]
