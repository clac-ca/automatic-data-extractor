"""Static validation helpers for config packages."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, List

from .manifest import ColumnMeta, ManifestV1


class DiagnosticLevel(str, Enum):
    """Severity of a validation diagnostic."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(slots=True)
class Diagnostic:
    """Represents a validation diagnostic message."""

    path: str
    code: str
    message: str
    level: DiagnosticLevel = DiagnosticLevel.ERROR
    hint: str | None = None


class ConfigValidationService:
    """Validate manifest + package structure for config packages."""

    def validate(self, manifest: ManifestV1, package_root: Path) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        diagnostics.extend(
            self._validate_columns(manifest.columns.meta.items(), package_root)
        )
        diagnostics.extend(self._validate_hooks(manifest, package_root))
        return diagnostics

    def _validate_columns(
        self,
        columns: Iterable[tuple[str, ColumnMeta]],
        package_root: Path,
    ) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        for field_id, meta in columns:
            if not meta.enabled:
                continue
            script_path = package_root / meta.script
            if not script_path.exists():
                diagnostics.append(
                    Diagnostic(
                        path=f"columns.meta.{field_id}.script",
                        code="missing_script",
                        message=f"Column script {meta.script!r} not found in package",
                    )
                )
                continue
            try:
                code = script_path.read_text(encoding="utf-8")
            except OSError as exc:
                diagnostics.append(
                    Diagnostic(
                        path=f"columns.meta.{field_id}.script",
                        code="unreadable_script",
                        message=f"Failed to read {meta.script!r}: {exc}",
                    )
                )
                continue

            try:
                module = ast.parse(code, filename=str(script_path))
            except SyntaxError as exc:
                diagnostics.append(
                    Diagnostic(
                        path=f"columns.meta.{field_id}.script",
                        code="invalid_syntax",
                        message=f"Script {meta.script!r} contains syntax errors: {exc.msg}",
                    )
                )
                continue

            functions = {node.name for node in module.body if isinstance(node, ast.FunctionDef)}
            detects = [name for name in functions if name.startswith("detect_")]
            if not detects:
                diagnostics.append(
                    Diagnostic(
                        path=f"columns.meta.{field_id}.script",
                        code="missing_detector",
                        message="Column scripts must define at least one detect_* function",
                    )
                )
            if "transform" not in functions:
                diagnostics.append(
                    Diagnostic(
                        path=f"columns.meta.{field_id}.script",
                        code="missing_transform",
                        message="Column scripts must define a transform function",
                    )
                )
        return diagnostics

    def _validate_hooks(self, manifest: ManifestV1, package_root: Path) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        for hook_name, entries in {
            "on_activate": manifest.hooks.on_activate,
            "on_job_start": manifest.hooks.on_job_start,
            "on_after_extract": manifest.hooks.on_after_extract,
            "on_job_end": manifest.hooks.on_job_end,
        }.items():
            for index, entry in enumerate(entries):
                if not entry.enabled:
                    continue
                script_path = package_root / entry.script
                path = f"hooks.{hook_name}[{index}].script"
                if not script_path.exists():
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            code="missing_hook_script",
                            message=f"Hook script {entry.script!r} not found in package",
                        )
                    )
                    continue
                try:
                    code = script_path.read_text(encoding="utf-8")
                except OSError as exc:
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            code="unreadable_hook",
                            message=f"Failed to read {entry.script!r}: {exc}",
                        )
                    )
                    continue
                try:
                    module = ast.parse(code, filename=str(script_path))
                except SyntaxError as exc:
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            code="invalid_hook_syntax",
                            message=f"Hook script {entry.script!r} contains syntax errors: {exc.msg}",
                        )
                    )
                    continue
                functions = {node.name for node in module.body if isinstance(node, ast.FunctionDef)}
                if "run" not in functions:
                    diagnostics.append(
                        Diagnostic(
                            path=path,
                            code="missing_hook_run",
                            message="Hook scripts must expose a run function",
                        )
                    )
        return diagnostics


__all__ = ["ConfigValidationService", "Diagnostic", "DiagnosticLevel"]
