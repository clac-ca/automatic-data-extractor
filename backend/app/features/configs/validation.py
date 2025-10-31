"""Validation helpers for configuration bundles."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from pydantic import ValidationError

from .schemas import Manifest, ValidationIssue, ValidationIssueLevel

ALLOWED_ROOT_FILES = {
    "manifest.json",
    "README.md",
    "on_activate.py",
    "on_job_start.py",
    "on_after_extract.py",
    "on_job_end.py",
}
ALLOWED_ROOT_DIRECTORIES = {"columns", "resources"}

CODE_STRUCTURE_UNKNOWN = "STRUCT001"
CODE_MANIFEST_JSON = "MANIFEST001"
CODE_MANIFEST_SCHEMA = "MANIFEST002"
CODE_HOOK_MISSING = "HOOK001"
CODE_HOOK_SIGNATURE = "HOOK002"
CODE_COLUMN_MISSING = "COLUMN001"
CODE_COLUMN_DETECT = "COLUMN002"
CODE_COLUMN_TRANSFORM = "COLUMN003"


def validate_bundle(root: Path) -> tuple[Manifest | None, list[ValidationIssue]]:
    """Validate the configuration bundle located at ``root``."""

    bundle = Path(root)
    issues: list[ValidationIssue] = []
    if not bundle.exists():
        issues.append(
            ValidationIssue(
                path=".",
                code=CODE_STRUCTURE_UNKNOWN,
                message="Configuration directory is missing",
            )
        )
        return None, issues

    manifest_path = bundle / "manifest.json"
    if not manifest_path.exists():
        issues.append(
            ValidationIssue(
                path="manifest.json",
                code=CODE_STRUCTURE_UNKNOWN,
                message="manifest.json not found",
            )
        )
        return None, issues

    manifest = _load_manifest(manifest_path, issues)
    if manifest is None:
        return None, issues

    issues.extend(_validate_root_structure(bundle))
    issues.extend(_validate_hooks(bundle, manifest))
    issues.extend(_validate_columns(bundle, manifest))
    return manifest, issues


def _load_manifest(path: Path, issues: list[ValidationIssue]) -> Manifest | None:
    try:
        payload = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(
            ValidationIssue(
                path="manifest.json",
                code=CODE_MANIFEST_JSON,
                message=f"Invalid JSON: {exc.msg} (line {exc.lineno} column {exc.colno})",
            )
        )
        return None

    try:
        return Manifest.model_validate(payload)
    except ValidationError as exc:
        for error in exc.errors():
            location = "#" + ".".join(str(segment) for segment in error.get("loc", ()))
            issues.append(
                ValidationIssue(
                    path=f"manifest.json{location}",
                    code=CODE_MANIFEST_SCHEMA,
                    message=error.get("msg", "Invalid value"),
                )
            )
        return None


def _validate_root_structure(root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for entry in root.iterdir():
        name = entry.name
        if entry.is_dir():
            if name not in ALLOWED_ROOT_DIRECTORIES:
                issues.append(
                    ValidationIssue(
                        path=name,
                        code=CODE_STRUCTURE_UNKNOWN,
                        message="Unexpected directory in configuration bundle",
                        level=ValidationIssueLevel.WARNING,
                    )
                )
        else:
            if name not in ALLOWED_ROOT_FILES:
                issues.append(
                    ValidationIssue(
                        path=name,
                        code=CODE_STRUCTURE_UNKNOWN,
                        message="Unexpected file in configuration bundle",
                        level=ValidationIssueLevel.WARNING,
                    )
                )
    return issues


def _validate_hooks(root: Path, manifest: Manifest) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for hook_name, entries in manifest.hooks.model_dump().items():
        for entry in entries or []:
            script = entry.get("script")
            if not script:
                issues.append(
                    ValidationIssue(
                        path="manifest.json#hooks",
                        code=CODE_HOOK_MISSING,
                        message=f"Hook '{hook_name}' is missing a script path",
                    )
                )
                continue
            resolved = _resolve_relative(root, script, issues)
            if resolved is None:
                continue
            if not resolved.exists():
                issues.append(
                    ValidationIssue(
                        path=script,
                        code=CODE_HOOK_MISSING,
                        message="Hook script does not exist",
                    )
                )
                continue
            issues.extend(_ensure_hook_exports_run(resolved, script))
    return issues


def _validate_columns(root: Path, manifest: Manifest) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for key in manifest.columns.order:
        column = manifest.columns.meta[key]
        script = column.script
        resolved = _resolve_relative(root, script, issues)
        if resolved is None:
            continue
        if not resolved.exists():
            issues.append(
                ValidationIssue(
                    path=script,
                    code=CODE_COLUMN_MISSING,
                    message=f"Column script for '{key}' does not exist",
                )
            )
            continue
        issues.extend(_inspect_column_module(resolved, script))
    return issues


def _ensure_hook_exports_run(path: Path, display_path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except SyntaxError as exc:
        issues.append(
            ValidationIssue(
                path=display_path,
                code=CODE_HOOK_SIGNATURE,
                message=f"Hook script contains syntax error: {exc.msg}",
            )
        )
        return issues

    has_run = any(isinstance(node, ast.FunctionDef) and node.name == "run" for node in tree.body)
    if not has_run:
        issues.append(
            ValidationIssue(
                path=display_path,
                code=CODE_HOOK_SIGNATURE,
                message="Hook script must define a callable named 'run'",
            )
        )
    return issues


def _inspect_column_module(path: Path, display_path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except SyntaxError as exc:
        issues.append(
            ValidationIssue(
                path=display_path,
                code=CODE_COLUMN_MISSING,
                message=f"Column module contains syntax error: {exc.msg}",
            )
        )
        return issues

    detect_functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("detect_")
    ]
    if not detect_functions:
        issues.append(
            ValidationIssue(
                path=display_path,
                code=CODE_COLUMN_DETECT,
                message="Column module must define at least one detect_* function",
            )
        )

    has_transform = any(
        isinstance(node, ast.FunctionDef) and node.name == "transform" for node in tree.body
    )
    if not has_transform:
        issues.append(
            ValidationIssue(
                path=display_path,
                code=CODE_COLUMN_TRANSFORM,
                message="Column module must define a transform function",
            )
        )
    return issues


def _resolve_relative(root: Path, relative: str, issues: list[ValidationIssue]) -> Path | None:
    try:
        candidate = (root / relative).resolve()
        candidate.relative_to(root)
    except ValueError:
        issues.append(
            ValidationIssue(
                path=relative,
                code=CODE_STRUCTURE_UNKNOWN,
                message="Script path escapes configuration directory",
            )
        )
        return None
    return candidate


__all__ = [
    "CODE_COLUMN_DETECT",
    "CODE_COLUMN_MISSING",
    "CODE_COLUMN_TRANSFORM",
    "CODE_HOOK_MISSING",
    "CODE_HOOK_SIGNATURE",
    "CODE_MANIFEST_JSON",
    "CODE_MANIFEST_SCHEMA",
    "CODE_STRUCTURE_UNKNOWN",
    "validate_bundle",
]
