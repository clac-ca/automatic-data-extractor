"""Filesystem helpers for config package persistence."""

import io
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from backend.app.shared.core.config import DEFAULT_CONFIGS_SUBDIR, Settings

__all__ = ["ConfigStorage", "StoredConfigVersion"]


@dataclass(slots=True)
class StoredConfigVersion:
    """Metadata returned after writing a config version to disk."""

    package_dir: Path
    archive_path: Path
    manifest_path: Path


class ConfigStorage:
    """Materialise config packages beneath ``ADE_STORAGE_DATA_DIR``."""

    def __init__(self, settings: Settings) -> None:
        base = settings.storage_configs_dir or (settings.storage_data_dir / DEFAULT_CONFIGS_SUBDIR)
        self._root = Path(base).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def version_dir(self, config_id: str, sequence: int) -> Path:
        return self._root / config_id / f"{sequence:04d}"

    def store(
        self,
        *,
        config_id: str,
        sequence: int,
        archive_name: str,
        archive_bytes: bytes,
        manifest: dict[str, object],
    ) -> StoredConfigVersion:
        """Persist ``archive_bytes`` and unpack the package into storage."""

        target_dir = self.version_dir(config_id, sequence)
        if target_dir.exists():
            shutil.rmtree(target_dir)

        package_dir = target_dir / "package"
        package_dir.mkdir(parents=True, exist_ok=True)

        archive_path = target_dir / archive_name
        archive_path.write_bytes(archive_bytes)

        with ZipFile(io.BytesIO(archive_bytes)) as archive:
            archive.extractall(package_dir)

        manifest_path = package_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return StoredConfigVersion(
            package_dir=package_dir,
            archive_path=archive_path,
            manifest_path=manifest_path,
        )

    def package_root(self, package_uri: str) -> Path:
        """Return the resolved path for a stored package URI."""

        return Path(package_uri).resolve()
