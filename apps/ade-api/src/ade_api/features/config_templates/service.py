"""Service layer for discovering available configuration templates."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi.concurrency import run_in_threadpool

from ade_api.settings import Settings

from .schemas import ConfigTemplate

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore

logger = logging.getLogger(__name__)


class ConfigTemplatesService:
    """List bundled and user-provided configuration templates."""

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._root = Path(settings.config_templates_dir).expanduser().resolve()

    async def list_templates(self) -> list[ConfigTemplate]:
        return await run_in_threadpool(self._list_templates_sync)

    def _list_templates_sync(self) -> list[ConfigTemplate]:
        if not self._root.exists():
            return []

        templates: list[ConfigTemplate] = []
        for entry in sorted(self._root.iterdir(), key=lambda p: p.name.lower()):
            if not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue
            name, description, version = self._read_manifest(entry)
            templates.append(
                ConfigTemplate(
                    id=entry.name,
                    name=name or entry.name,
                    description=description,
                    version=version,
                )
            )
        return templates

    def _read_manifest(self, template_dir: Path) -> tuple[str, str | None, str | None]:
        manifest_candidates = [
            template_dir / "src" / "ade_config" / "manifest.toml",
            template_dir / "manifest.toml",
        ]

        for manifest_path in manifest_candidates:
            if not manifest_path.exists():
                continue
            try:
                payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning(
                    "config_templates.manifest_read_failed",
                    extra={"path": str(manifest_path)},
                    exc_info=True,
                )
                return template_dir.name, None, None

            name = str(payload.get("name") or "").strip()
            description = (payload.get("description") or "").strip() or None
            version = (payload.get("version") or "").strip() or None
            return name or template_dir.name, description, version

        return template_dir.name, None, None


__all__ = ["ConfigTemplatesService"]
