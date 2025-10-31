"""Filesystem helpers for file-backed configuration bundles."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(slots=True)
class ConfigFileMetadata:
    """Lightweight description of a file inside a configuration bundle."""

    path: str
    byte_size: int
    sha256: str


class ConfigFilesystem:
    """Operate on configuration bundles stored on the local filesystem."""

    def __init__(self, root_dir: Path) -> None:
        self._root = Path(root_dir).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        _fsync_dir(self._root)

    def ensure_config_dir(self, config_id: str) -> Path:
        """Return the root folder for ``config_id`` creating it when missing."""

        bundle = self._config_root(config_id)
        bundle.mkdir(parents=True, exist_ok=True)
        _fsync_dir(bundle.parent)
        _fsync_dir(bundle)
        return bundle

    def config_path(self, config_id: str) -> Path:
        """Return the absolute path to the bundle for ``config_id`` without creating it."""

        return self._config_root(config_id)

    def delete_config(self, config_id: str) -> None:
        """Remove ``config_id`` from storage if it exists."""

        bundle = self._config_root(config_id)
        if not bundle.exists():
            return
        shutil.rmtree(bundle)
        _fsync_dir(bundle.parent)

    def copy_config(self, source_config_id: str, target_config_id: str) -> None:
        """Copy the bundle for ``source_config_id`` into ``target_config_id``."""

        source = self._config_root(source_config_id)
        if not source.exists():
            raise FileNotFoundError(f"Config {source_config_id} directory does not exist")

        destination = self._config_root(target_config_id)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination, dirs_exist_ok=True)
        _fsync_tree(destination)
        _fsync_dir(destination.parent)

    def list_files(self, config_id: str) -> list[ConfigFileMetadata]:
        """Return metadata for every tracked file relative to ``config_id`` root."""

        bundle = self._config_root(config_id)
        if not bundle.exists():
            return []

        items: list[ConfigFileMetadata] = []
        for file_path in _iter_files(bundle):
            relative = file_path.relative_to(bundle).as_posix()
            stats = file_path.stat()
            digest = _sha256_for_path(file_path)
            items.append(
                ConfigFileMetadata(
                    path=relative,
                    byte_size=stats.st_size,
                    sha256=digest,
                )
            )
        items.sort(key=lambda item: item.path)
        return items

    def read_bytes(self, config_id: str, relative_path: str) -> bytes:
        """Return the raw bytes for ``relative_path`` inside ``config_id``."""

        path = self._resolve_file(config_id, relative_path)
        return path.read_bytes()

    def read_text(self, config_id: str, relative_path: str, *, encoding: str = "utf-8") -> str:
        """Return decoded text for ``relative_path`` inside ``config_id``."""

        path = self._resolve_file(config_id, relative_path)
        return path.read_text(encoding=encoding)

    def write_bytes(self, config_id: str, relative_path: str, data: bytes) -> ConfigFileMetadata:
        """Persist ``data`` to ``relative_path`` returning updated metadata."""

        path = self._resolve_file(config_id, relative_path, create_parents=True)
        _atomic_write(path, data)
        stats = path.stat()
        digest = _sha256_for_path(path)
        return ConfigFileMetadata(path=relative_path, byte_size=stats.st_size, sha256=digest)

    def write_text(
        self,
        config_id: str,
        relative_path: str,
        data: str,
        *,
        encoding: str = "utf-8",
    ) -> ConfigFileMetadata:
        """Encode ``data`` and persist it to ``relative_path``."""

        return self.write_bytes(config_id, relative_path, data.encode(encoding))

    def delete_file(self, config_id: str, relative_path: str) -> None:
        """Delete ``relative_path`` inside ``config_id``."""

        path = self._resolve_file(config_id, relative_path)
        path.unlink()
        _fsync_dir(path.parent)

    def rename_file(self, config_id: str, source: str, destination: str) -> None:
        """Rename ``source`` to ``destination`` ensuring the target directories exist."""

        source_path = self._resolve_file(config_id, source)
        destination_path = self._resolve_file(config_id, destination, create_parents=True)
        os.replace(source_path, destination_path)
        _fsync_dir(destination_path.parent)
        _fsync_dir(source_path.parent)

    def copy_template(self, template_dir: Path, config_id: str) -> None:
        """Copy ``template_dir`` into the bundle folder for ``config_id``."""

        destination = self._config_root(config_id)
        if destination.exists() and any(destination.iterdir()):
            raise FileExistsError(f"Config {config_id} already has files")
        shutil.copytree(template_dir, destination, dirs_exist_ok=True)
        _fsync_tree(destination)
        _fsync_dir(destination.parent)

    def compute_package_hash(self, config_id: str) -> str:
        """Return a deterministic SHA-256 hash for the bundle contents."""

        bundle = self._config_root(config_id)
        return compute_tree_hash(bundle)

    def _config_root(self, config_id: str) -> Path:
        candidate = (self._root / config_id).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError("Config ID escapes storage root") from exc
        return candidate

    def _resolve_file(
        self,
        config_id: str,
        relative_path: str,
        *,
        create_parents: bool = False,
    ) -> Path:
        bundle = self._config_root(config_id)
        if not bundle.exists():
            raise FileNotFoundError(f"Config {config_id} directory does not exist")
        relative = Path(relative_path)
        candidate = (bundle / relative).resolve()
        try:
            candidate.relative_to(bundle)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError("Relative path escapes configuration bundle") from exc
        if create_parents:
            candidate.parent.mkdir(parents=True, exist_ok=True)
        if not candidate.exists() and not create_parents:
            raise FileNotFoundError(relative_path)
        return candidate


def compute_tree_hash(root: Path) -> str:
    """Return a deterministic digest for the files contained in ``root``."""

    root = Path(root)
    if not root.exists():
        return ""

    entries: list[tuple[str, str]] = []
    for file_path in _iter_files(root):
        relative = file_path.relative_to(root).as_posix()
        digest = _sha256_for_path(file_path)
        entries.append((relative, digest))

    hasher = sha256()
    for relative, file_hash in sorted(entries):
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(file_hash.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _iter_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _should_skip(path):
            continue
        yield path


def _should_skip(path: Path) -> bool:
    parts = path.parts
    if any(part == "__pycache__" for part in parts):
        return True
    name = path.name
    if name.endswith(".pyc") or name.startswith("."):
        return True
    return False


def _sha256_for_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(destination: Path, data: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_path = Path(tmp.name)
    os.replace(temp_path, destination)
    fd = os.open(destination, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(destination.parent)


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:  # pragma: no cover - defensive
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_tree(root: Path) -> None:
    for directory in _iter_directories(root):
        _fsync_dir(directory)


def _iter_directories(root: Path) -> Iterable[Path]:
    # Ensure deterministic ordering for tests and platform parity.
    stack = [root]
    seen: set[Path] = set()
    while stack:
        current = stack.pop()
        normalised = current.resolve()
        if normalised in seen:
            continue
        seen.add(normalised)
        yield current
        for child in sorted((p for p in current.iterdir() if p.is_dir()), reverse=True):
            stack.append(child)


__all__ = ["ConfigFilesystem", "ConfigFileMetadata", "compute_tree_hash"]
