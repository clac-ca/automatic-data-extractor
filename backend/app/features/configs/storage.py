"""Filesystem helpers for config package persistence."""

import io
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.app.shared.core.config import DEFAULT_CONFIGS_SUBDIR, Settings

__all__ = ["ConfigStorage", "StoredConfigVersion", "PackageFileMetadata"]


@dataclass(slots=True)
class StoredConfigVersion:
    """Metadata returned after writing a config version to disk."""

    package_dir: Path
    archive_path: Path
    manifest_path: Path


@dataclass(slots=True)
class PackageFileMetadata:
    """Lightweight description of a file or directory within a stored package."""

    path: str
    type: str  # "file" or "directory"
    size: int | None = None
    sha256: str | None = None


class ConfigStorage:
    """Materialise config packages beneath ``ADE_STORAGE_DATA_DIR``."""

    _DRAFTS_DIRNAME = "drafts"
    _PACKAGE_SUBDIR = "package"
    _METADATA_FILENAME = "metadata.json"

    def __init__(self, settings: Settings) -> None:
        base = settings.storage_configs_dir or (settings.storage_data_dir / DEFAULT_CONFIGS_SUBDIR)
        self._root = Path(base).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def version_dir(self, config_id: str, sequence: int) -> Path:
        return self._root / config_id / f"{sequence:04d}"

    def draft_dir(self, config_id: str, draft_id: str) -> Path:
        return self._drafts_root(config_id) / draft_id

    def draft_package_dir(self, config_id: str, draft_id: str) -> Path:
        return self.draft_dir(config_id, draft_id) / self._PACKAGE_SUBDIR

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

        with ZipFile(io.BytesIO(archive_bytes)) as archive:
            self._extract_all(archive, package_dir)

        manifest_path = package_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        archive_path = target_dir / archive_name
        self._write_canonical_archive(package_dir, archive_path)

        return StoredConfigVersion(
            package_dir=package_dir,
            archive_path=archive_path,
            manifest_path=manifest_path,
        )

    def package_root(self, package_path: str) -> Path:
        """Return the resolved path for a stored package path."""

        return Path(package_path).resolve()

    def compute_package_hash(self, archive_path: Path) -> str:
        """Calculate a deterministic hash from the canonical archive."""

        return self._hash_bytes(archive_path.read_bytes())

    def garbage_collect(self, config_id: str, valid_sequences: Iterable[int]) -> None:
        """Remove on-disk version directories not referenced in ``valid_sequences``."""

        config_root = self.root / config_id
        if not config_root.exists():
            return
        keep = {f"{seq:04d}" for seq in valid_sequences}
        for child in config_root.iterdir():
            if not child.is_dir():
                continue
            if child.name == self._DRAFTS_DIRNAME:
                continue
            if child.name not in keep:
                shutil.rmtree(child, ignore_errors=True)

    def create_draft_from_source(
        self,
        *,
        config_id: str,
        draft_id: str,
        source_package_dir: Path,
        metadata: dict[str, object],
    ) -> Path:
        """Materialise a draft workspace copied from ``source_package_dir``."""

        source = source_package_dir.resolve()
        if not source.exists():
            raise FileNotFoundError(f"Source package directory does not exist: {source}")

        draft_root = self.draft_dir(config_id, draft_id)
        if draft_root.exists():
            shutil.rmtree(draft_root, ignore_errors=True)
        package_target = draft_root / self._PACKAGE_SUBDIR
        shutil.copytree(source, package_target)

        metadata_path = draft_root / self._METADATA_FILENAME
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        return package_target

    def update_draft_metadata(self, config_id: str, draft_id: str, metadata: dict[str, object]) -> None:
        path = self.draft_dir(config_id, draft_id) / self._METADATA_FILENAME
        if not path.parent.exists():
            raise FileNotFoundError(f"Draft does not exist: {draft_id}")
        path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    def read_draft_metadata(self, config_id: str, draft_id: str) -> dict[str, object]:
        path = self.draft_dir(config_id, draft_id) / self._METADATA_FILENAME
        if not path.exists():
            raise FileNotFoundError(f"Draft metadata missing for {draft_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_drafts(self, config_id: str) -> list[str]:
        root = self._drafts_root(config_id)
        if not root.exists():
            return []
        draft_ids = [child.name for child in root.iterdir() if child.is_dir()]
        draft_ids.sort()
        return draft_ids

    def delete_draft(self, config_id: str, draft_id: str) -> None:
        draft_root = self.draft_dir(config_id, draft_id)
        if draft_root.exists():
            shutil.rmtree(draft_root, ignore_errors=True)

    def list_entries(self, package_dir: Path) -> list[PackageFileMetadata]:
        """Return a sorted list of files and directories in ``package_dir``."""

        root = package_dir.resolve()
        if not root.exists():
            raise FileNotFoundError(f"Package directory not found: {root}")

        entries: list[PackageFileMetadata] = []
        for path in root.rglob("*"):
            if self._should_skip(path, root):
                continue
            relative = path.relative_to(root).as_posix()
            if not relative:
                continue
            if path.is_dir():
                entries.append(PackageFileMetadata(path=relative, type="directory"))
            else:
                file_bytes = path.read_bytes()
                entries.append(
                    PackageFileMetadata(
                        path=relative,
                        type="file",
                        size=len(file_bytes),
                        sha256=self._hash_bytes(file_bytes),
                    )
                )
        entries.sort(key=lambda item: (item.path.count("/"), item.path))
        return entries

    def read_text(self, package_dir: Path, relative_path: str, *, encoding: str = "utf-8") -> str:
        """Read a UTF-8 file from the package."""

        target = self._resolve_existing_path(package_dir, relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"Package file not found: {relative_path}")
        return target.read_text(encoding=encoding)

    def read_bytes(self, package_dir: Path, relative_path: str) -> bytes:
        """Read a binary file from the package."""

        target = self._resolve_existing_path(package_dir, relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"Package file not found: {relative_path}")
        return target.read_bytes()

    def write_text(
        self,
        package_dir: Path,
        relative_path: str,
        content: str,
        *,
        encoding: str = "utf-8",
    ) -> None:
        """Write (or create) a UTF-8 file within the package."""

        target = self._resolve_writable_path(package_dir, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)

    def write_bytes(self, package_dir: Path, relative_path: str, payload: bytes) -> None:
        """Write (or create) a binary file within the package."""

        target = self._resolve_writable_path(package_dir, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    def build_archive_bytes(self, package_dir: Path) -> bytes:
        """Return canonical archive bytes for the provided package directory."""

        buffer = io.BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            for file_path in sorted(self._iter_files(package_dir)):
                relative = file_path.relative_to(package_dir).as_posix()
                info = ZipInfo(relative)
                info.date_time = (2020, 1, 1, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, file_path.read_bytes())
        return buffer.getvalue()

    def delete_entry(self, package_dir: Path, relative_path: str) -> None:
        """Delete a file or directory within the package."""

        target = self._resolve_existing_path(package_dir, relative_path)
        if target == package_dir.resolve():
            raise ValueError("Cannot delete package root")
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=False)

    def ensure_directory(self, package_dir: Path, relative_path: str) -> None:
        """Create a directory (and parents) within the package."""

        target = self._resolve_writable_path(package_dir, relative_path)
        target.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _should_skip(path: Path, root: Path) -> bool:
        parts = path.relative_to(root).parts
        for part in parts:
            if part.startswith(".") and part != ".":
                return True
            if part == "__pycache__":
                return True
        return False

    @staticmethod
    def _normalise_relative_path(relative_path: str) -> Path:
        candidate = Path(relative_path.strip())
        if not str(candidate):
            raise ValueError("Path must not be empty")
        if candidate.is_absolute():
            raise ValueError("Path must be relative")
        if any(part in {"..", ""} for part in candidate.parts):
            raise ValueError("Path must not contain traversal segments or empty components")
        return candidate

    @staticmethod
    def _is_within(candidate: Path, root: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    def _resolve_existing_path(self, package_dir: Path, relative_path: str) -> Path:
        root = package_dir.resolve()
        relative = self._normalise_relative_path(relative_path)
        target = (root / relative).resolve(strict=True)
        if not self._is_within(target, root):
            raise ValueError("Resolved path escapes package directory")
        return target

    def _resolve_writable_path(self, package_dir: Path, relative_path: str) -> Path:
        root = package_dir.resolve()
        relative = self._normalise_relative_path(relative_path)
        target = (root / relative).resolve(strict=False)
        if not self._is_within(target, root):
            raise ValueError("Resolved path escapes package directory")
        return target

    def _drafts_root(self, config_id: str) -> Path:
        root = self.root / config_id / self._DRAFTS_DIRNAME
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _iter_files(root: Path):
        for path in root.rglob("*"):
            if path.is_dir():
                continue
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            if "__pycache__" in path.parts:
                continue
            yield path

    @staticmethod
    def _extract_all(archive: ZipFile, destination: Path) -> None:
        for member in archive.infolist():
            filename = Path(member.filename)
            if filename.is_absolute() or ".." in filename.parts:
                raise ValueError(f"Unsafe path in archive: {member.filename}")
        archive.extractall(destination)

    def _write_canonical_archive(self, package_dir: Path, destination: Path) -> None:
        with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
            for file_path in sorted(self._iter_files(package_dir)):
                relative = file_path.relative_to(package_dir).as_posix()
                info = ZipInfo(relative)
                info.date_time = (2020, 1, 1, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, file_path.read_bytes())

    @staticmethod
    def _hash_bytes(payload: bytes) -> str:
        import hashlib

        return hashlib.sha256(payload).hexdigest()
