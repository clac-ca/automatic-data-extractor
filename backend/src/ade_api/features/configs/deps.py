"""Helpers for config dependency manifests."""

from __future__ import annotations

import re
import tomllib
from hashlib import sha256
from pathlib import Path

from .constants import CONFIG_DEP_FILES

ENGINE_DEPENDENCY_NAME = "ade-engine"
_NAME_NORMALIZER = re.compile(r"[-_.]+")


def normalize_dependency_name(value: str) -> str:
    """Normalize package names using PEP 503 semantics."""

    return _NAME_NORMALIZER.sub("-", value.strip().lower())


def _iter_pyproject_dependencies(pyproject_path: Path) -> list[str]:
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []

    dependencies: list[str] = []
    project = payload.get("project")
    if isinstance(project, dict):
        direct = project.get("dependencies")
        if isinstance(direct, list):
            dependencies.extend(item for item in direct if isinstance(item, str))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for items in optional.values():
                if isinstance(items, list):
                    dependencies.extend(item for item in items if isinstance(item, str))

    poetry = (
        payload.get("tool", {}).get("poetry") if isinstance(payload.get("tool"), dict) else None
    )
    if isinstance(poetry, dict):
        poetry_deps = poetry.get("dependencies")
        if isinstance(poetry_deps, dict):
            dependencies.extend(str(name) for name in poetry_deps.keys() if isinstance(name, str))

    return dependencies


def _dep_name_from_requirement_line(line: str) -> str | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None

    if " #" in text:
        text = text.split(" #", 1)[0].strip()
    if not text:
        return None

    lower = text.lower()
    if lower.startswith(("-r ", "--requirement ", "-c ", "--constraint ", "-f ", "--find-links ")):
        return None
    if lower.startswith(("--index-url ", "--extra-index-url ", "--trusted-host ")):
        return None

    if lower.startswith(("-e ", "--editable ")):
        match = re.search(r"#egg=([A-Za-z0-9_.-]+)", text)
        if match:
            return match.group(1)
        return None

    match = re.match(r"([A-Za-z0-9_.-]+)", text)
    if not match:
        return None
    return match.group(1)


def _iter_requirement_dependencies(path: Path) -> list[str]:
    dependencies: list[str] = []
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return dependencies

    for raw in content.splitlines():
        name = _dep_name_from_requirement_line(raw)
        if name:
            dependencies.append(name)
    return dependencies


def iter_declared_dependency_names(root: Path) -> list[str]:
    """Return normalized dependency names declared in known manifest files."""

    names: list[str] = []
    for manifest_name in CONFIG_DEP_FILES:
        manifest = root / manifest_name
        if not manifest.is_file():
            continue
        if manifest_name == "pyproject.toml":
            deps = _iter_pyproject_dependencies(manifest)
        else:
            deps = _iter_requirement_dependencies(manifest)
        for dep in deps:
            dep_name = _dep_name_from_requirement_line(dep)
            if dep_name:
                names.append(normalize_dependency_name(dep_name))
    return names


def has_engine_dependency(root: Path) -> bool:
    """Return True when the config declares ade-engine in known manifests."""

    target = normalize_dependency_name(ENGINE_DEPENDENCY_NAME)
    return target in set(iter_declared_dependency_names(root))


def compute_dependency_digest(root: Path) -> str:
    """Hash only dependency manifests inside a config package.

    Venv rebuilds are expensive; we only need to redo them when dependency
    metadata changes. This digest intentionally ignores source files so code
    edits picked up via editable installs do not force a rebuild.
    """

    digest = sha256()
    found = False

    for name in CONFIG_DEP_FILES:
        path = root / name
        if not path.is_file():
            continue
        found = True
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())

    if not found:
        # Fallback: if no manifest exists, treat as empty dependencies so the
        # fingerprint remains stable but still deterministic.
        digest.update(b"empty")

    return f"sha256:{digest.hexdigest()}"


__all__ = [
    "ENGINE_DEPENDENCY_NAME",
    "compute_dependency_digest",
    "has_engine_dependency",
    "iter_declared_dependency_names",
    "normalize_dependency_name",
]
