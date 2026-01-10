"""Filesystem layout for the worker.

Align with the API storage layout (venvs root is configurable):
- data/workspaces/<workspace_id>/config_packages/<configuration_id>
- data/workspaces/<workspace_id>/documents/<stored_uri>
- data/workspaces/<workspace_id>/runs/<run_id>
- venvs/<workspace_id>/<configuration_id>/<deps_digest>/<environment_id>/.venv
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path


class UnsafePathError(ValueError):
    pass


def _safe_join(base: Path, *parts: str) -> Path:
    base_resolved = base.resolve()
    candidate = (base_resolved.joinpath(*parts)).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise UnsafePathError(f"Unsafe path join: {candidate} is outside {base_resolved}") from exc
    return candidate


def _normalize_uuid(value: str | uuid.UUID) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    text = str(value)
    try:
        return str(uuid.UUID(text))
    except (ValueError, AttributeError, TypeError):
        return text


def _strip_file_uri(uri: str) -> str:
    # Supports:
    # - file:/abs/path
    # - file:relative/path
    if not uri.startswith("file:"):
        raise ValueError(f"Unsupported URI scheme: {uri!r}")
    path = uri[len("file:") :]
    if path.startswith("//") and not path.startswith("///"):
        # file://host/path is not supported
        raise ValueError(f"Unsupported file URI: {uri!r}")
    if path.startswith("///"):
        # file:///abs/path -> /abs/path
        path = path[2:]
    return path


def _safe_segment(value: str, *, fallback: str) -> str:
    cleaned = []
    for ch in value:
        if ch.isalnum() or ch in {"-", "_"}:
            cleaned.append(ch)
        else:
            cleaned.append("_")
    segment = "".join(cleaned).strip("_")
    return segment or fallback


def _deps_digest_segment(deps_digest: str) -> str:
    raw = (deps_digest or "").strip()
    if not raw:
        return "deps-unknown"
    if ":" in raw:
        _, raw = raw.split(":", 1)
    return f"deps-{_safe_segment(raw, fallback='unknown')}"


@dataclass(frozen=True, slots=True)
class PathManager:
    data_dir: Path
    venvs_dir: Path

    # --- roots ---
    def workspaces_root(self) -> Path:
        return _safe_join(self.data_dir, "workspaces")

    def documents_root(self, workspace_id: str) -> Path:
        return _safe_join(self.workspaces_root(), _normalize_uuid(workspace_id), "documents")

    def configs_root(self, workspace_id: str) -> Path:
        return _safe_join(self.workspaces_root(), _normalize_uuid(workspace_id), "config_packages")

    def runs_root(self, workspace_id: str) -> Path:
        return _safe_join(self.workspaces_root(), _normalize_uuid(workspace_id), "runs")

    def venvs_root(self, workspace_id: str) -> Path:
        return _safe_join(self.venvs_dir, _normalize_uuid(workspace_id))

    def pip_cache_dir(self) -> Path:
        return _safe_join(self.data_dir, "cache", "pip")

    # --- config packages ---
    def config_package_dir(self, workspace_id: str, configuration_id: str) -> Path:
        return _safe_join(
            self.configs_root(workspace_id),
            _normalize_uuid(configuration_id),
        )

    # --- environments / venvs ---
    def environment_root(
        self,
        workspace_id: str,
        configuration_id: str,
        deps_digest: str,
        environment_id: str,
    ) -> Path:
        segment = _deps_digest_segment(deps_digest)
        return _safe_join(
            self.venvs_root(workspace_id),
            _normalize_uuid(configuration_id),
            segment,
            _normalize_uuid(environment_id),
        )

    def environment_venv_dir(
        self,
        workspace_id: str,
        configuration_id: str,
        deps_digest: str,
        environment_id: str,
    ) -> Path:
        return _safe_join(
            self.environment_root(workspace_id, configuration_id, deps_digest, environment_id),
            ".venv",
        )

    def environment_event_log_path(
        self,
        workspace_id: str,
        configuration_id: str,
        deps_digest: str,
        environment_id: str,
    ) -> Path:
        return _safe_join(
            self.environment_root(workspace_id, configuration_id, deps_digest, environment_id),
            "logs",
            "events.ndjson",
        )

    # --- runs ---
    def run_dir(self, workspace_id: str, run_id: str) -> Path:
        return _safe_join(self.runs_root(workspace_id), _normalize_uuid(run_id))

    def run_input_dir(self, workspace_id: str, run_id: str) -> Path:
        return _safe_join(self.run_dir(workspace_id, run_id), "input")

    def run_output_dir(self, workspace_id: str, run_id: str) -> Path:
        return _safe_join(self.run_dir(workspace_id, run_id), "output")

    def run_event_log_path(self, workspace_id: str, run_id: str) -> Path:
        return _safe_join(self.run_dir(workspace_id, run_id), "logs", "events.ndjson")

    # --- documents ---
    def document_storage_path(self, *, workspace_id: str, stored_uri: str) -> Path:
        uri = (stored_uri or "").strip()
        if not uri:
            raise ValueError("stored_uri is empty")
        if uri.startswith("file:"):
            uri = _strip_file_uri(uri)
        uri = uri.lstrip("/")  # always treat as relative-to-documents root
        return _safe_join(self.documents_root(workspace_id), uri)

    # --- venv executables ---
    def python_in_venv(self, venv_dir: Path) -> Path:
        if os.name == "nt":
            return venv_dir / "Scripts" / "python.exe"
        return venv_dir / "bin" / "python"


__all__ = ["PathManager", "UnsafePathError"]
