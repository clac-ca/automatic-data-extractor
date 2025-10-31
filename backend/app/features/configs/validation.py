"""Validation helpers for configuration bundles."""

from __future__ import annotations

import ast
import json

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .schemas import (
    Manifest,
    ValidationIssue,
    ValidationIssueCode,
    ValidationIssueLevel,
)

ALLOWED_ROOT_FILES = {
    "manifest.json",
    "README.md",
    "on_activate.py",
    "on_job_start.py",
    "on_after_extract.py",
    "on_job_end.py",
}
ALLOWED_ROOT_DIRECTORIES = {"columns", "resources"}
HOOK_SIGNATURES: dict[str, tuple[str, ...]] = {
    "on_activate": ("workspace_id", "config_id", "env", "paths"),
    "on_job_start": (
        "workspace_id",
        "config_id",
        "job_id",
        "env",
        "paths",
        "inputs",
    ),
    "on_after_extract": (
        "workspace_id",
        "config_id",
        "job_id",
        "env",
        "paths",
        "mapping",
        "warnings",
    ),
    "on_job_end": (
        "workspace_id",
        "config_id",
        "job_id",
        "env",
        "paths",
        "success",
        "error",
    ),
}
COLUMN_DETECT_SIGNATURE = (
    "header",
    "values",
    "column_index",
    "table",
    "job_context",
    "env",
)
COLUMN_TRANSFORM_SIGNATURE = COLUMN_DETECT_SIGNATURE

@dataclass(slots=True)
class ValidationContext:
    """Track validation diagnostics for a configuration bundle."""

    root: Path
    issues: list[ValidationIssue]

    def add(
        self,
        *,
        path: str,
        code: ValidationIssueCode,
        message: str,
        level: ValidationIssueLevel = ValidationIssueLevel.ERROR,
    ) -> None:
        self.issues.append(
            ValidationIssue(path=path, code=code, message=message, level=level)
        )

    def resolve(self, relative: str) -> Path | None:
        candidate = (self.root / relative).resolve()
        if not candidate.is_relative_to(self.root):
            self.add(
                path=relative,
                code=ValidationIssueCode.STRUCTURE_UNKNOWN,
                message="Script path escapes configuration directory",
            )
            return None
        return candidate


@dataclass(slots=True)
class ValidationResult:
    """Outcome of bundle validation."""

    manifest: Manifest | None
    issues: list[ValidationIssue]


def validate_bundle(root: Path) -> ValidationResult:
    """Validate the configuration bundle located at ``root``."""

    context = ValidationContext(Path(root), [])
    if not context.root.exists():
        context.add(
            path=".",
            code=ValidationIssueCode.STRUCTURE_UNKNOWN,
            message="Configuration directory is missing",
        )
        return ValidationResult(manifest=None, issues=context.issues)

    manifest_path = context.root / "manifest.json"
    if not manifest_path.exists():
        context.add(
            path="manifest.json",
            code=ValidationIssueCode.STRUCTURE_UNKNOWN,
            message="manifest.json not found",
        )
        return ValidationResult(manifest=None, issues=context.issues)

    manifest = _load_manifest(manifest_path, context)
    if manifest is None:
        return ValidationResult(manifest=None, issues=context.issues)

    _validate_root_structure(context)
    _validate_hooks(context, manifest)
    _validate_columns(context, manifest)
    return ValidationResult(manifest=manifest, issues=context.issues)


def _load_manifest(path: Path, context: ValidationContext) -> Manifest | None:
    try:
        payload = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        context.add(
            path="manifest.json",
            code=ValidationIssueCode.MANIFEST_JSON,
            message=f"Invalid JSON: {exc.msg} (line {exc.lineno} column {exc.colno})",
        )
        return None

    try:
        return Manifest.model_validate(payload)
    except ValidationError as exc:
        for error in exc.errors():
            location = "#" + ".".join(str(segment) for segment in error.get("loc", ()))
            context.add(
                path=f"manifest.json{location}",
                code=ValidationIssueCode.MANIFEST_SCHEMA,
                message=error.get("msg", "Invalid value"),
            )
        return None


def _validate_root_structure(context: ValidationContext) -> None:
    for entry in context.root.iterdir():
        name = entry.name
        if entry.is_dir():
            if name not in ALLOWED_ROOT_DIRECTORIES:
                context.add(
                    path=name,
                    code=ValidationIssueCode.STRUCTURE_UNKNOWN,
                    message="Unexpected directory in configuration bundle",
                    level=ValidationIssueLevel.WARNING,
                )
        else:
            if name not in ALLOWED_ROOT_FILES:
                context.add(
                    path=name,
                    code=ValidationIssueCode.STRUCTURE_UNKNOWN,
                    message="Unexpected file in configuration bundle",
                    level=ValidationIssueLevel.WARNING,
                )


def _validate_hooks(context: ValidationContext, manifest: Manifest) -> None:
    hooks = manifest.hooks
    for hook_name, signature in HOOK_SIGNATURES.items():
        entries = getattr(hooks, hook_name) or []
        for entry in entries:
            script = entry.script
            if not script:
                context.add(
                    path="manifest.json#hooks",
                    code=ValidationIssueCode.HOOK_MISSING,
                    message=f"Hook '{hook_name}' is missing a script path",
                )
                continue
            resolved = context.resolve(script)
            if resolved is None:
                continue
            if not resolved.exists():
                context.add(
                    path=script,
                    code=ValidationIssueCode.HOOK_MISSING,
                    message="Hook script does not exist",
                )
                continue
            _inspect_hook_module(
                context,
                resolved,
                script,
                hook_name=hook_name,
                expected_signature=signature,
            )


def _validate_columns(context: ValidationContext, manifest: Manifest) -> None:
    for key in manifest.columns.order:
        column = manifest.columns.meta[key]
        script = column.script
        resolved = context.resolve(script)
        if resolved is None:
            continue
        if not resolved.exists():
            context.add(
                path=script,
                code=ValidationIssueCode.COLUMN_MISSING,
                message=f"Column script for '{key}' does not exist",
            )
            continue
        _inspect_column_module(context, resolved, script)


def _inspect_hook_module(
    context: ValidationContext,
    path: Path,
    display_path: str,
    *,
    hook_name: str,
    expected_signature: tuple[str, ...],
) -> None:
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except SyntaxError as exc:
        context.add(
            path=display_path,
            code=ValidationIssueCode.HOOK_SIGNATURE,
            message=f"Hook script contains syntax error: {exc.msg}",
        )
        return

    run_nodes = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run"
    ]
    if not run_nodes:
        context.add(
            path=display_path,
            code=ValidationIssueCode.HOOK_SIGNATURE,
            message=f"Hook '{hook_name}' must define a callable named 'run'",
        )
        return

    error = _keyword_only_signature_errors(run_nodes[0], expected_signature)
    if error:
        context.add(
            path=display_path,
            code=ValidationIssueCode.HOOK_SIGNATURE,
            message=f"Hook '{hook_name}' run() {error}",
        )


def _inspect_column_module(
    context: ValidationContext, path: Path, display_path: str
) -> None:
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except SyntaxError as exc:
        context.add(
            path=display_path,
            code=ValidationIssueCode.COLUMN_MISSING,
            message=f"Column module contains syntax error: {exc.msg}",
        )
        return

    detect_functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("detect_")
    ]
    if not detect_functions:
        context.add(
            path=display_path,
            code=ValidationIssueCode.COLUMN_DETECT,
            message="Column module must define at least one detect_* function",
        )
    else:
        for node in detect_functions:
            error = _keyword_only_signature_errors(node, COLUMN_DETECT_SIGNATURE)
            if error:
                context.add(
                    path=display_path,
                    code=ValidationIssueCode.COLUMN_DETECT,
                    message=f"Function '{node.name}' {error}",
                )

    has_transform = any(
        isinstance(node, ast.FunctionDef) and node.name == "transform" for node in tree.body
    )
    if not has_transform:
        context.add(
            path=display_path,
            code=ValidationIssueCode.COLUMN_TRANSFORM,
            message="Column module must define a transform function",
        )
    else:
        transform_node = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "transform"
        )
        error = _keyword_only_signature_errors(
            transform_node, COLUMN_TRANSFORM_SIGNATURE
        )
        if error:
            context.add(
                path=display_path,
                code=ValidationIssueCode.COLUMN_TRANSFORM,
                message=f"Function 'transform' {error}",
            )


def _keyword_only_signature_errors(
    node: ast.FunctionDef, expected: tuple[str, ...]
) -> str | None:
    args = node.args
    if args.posonlyargs:
        return "must not define positional-only parameters"
    if args.args:
        return "must not define positional parameters"
    if args.vararg is not None:
        return "must not accept *args"
    if args.kwarg is not None:
        return "must not accept **kwargs"

    keywords = [arg.arg for arg in args.kwonlyargs]
    missing = [name for name in expected if name not in keywords]
    unexpected = [name for name in keywords if name not in expected]
    if missing:
        return "is missing keyword-only parameters: " + ", ".join(missing)
    if unexpected:
        return "contains unsupported parameters: " + ", ".join(unexpected)
    return None


__all__ = ["ValidationResult", "validate_bundle"]
