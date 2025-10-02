"""Startup helpers for ADE runtime."""

from __future__ import annotations

from pathlib import Path

from .config import Settings, get_settings


def ensure_runtime_dirs(settings: Settings | None = None) -> None:
    """Create runtime directories required by the application."""

    settings = settings or get_settings()

    data_dir = Path(settings.storage_data_dir)
    documents_dir = getattr(settings, "storage_documents_dir", None)

    targets: list[Path] = [data_dir]
    if documents_dir is not None:
        targets.append(Path(documents_dir))

    for target in targets:
        target.mkdir(parents=True, exist_ok=True)


__all__ = ["ensure_runtime_dirs"]
