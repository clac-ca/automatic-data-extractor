"""Strict config package validator covering static and dynamic checks."""

from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from .manifest import ManifestV1
from .static_validation import ConfigValidationService, Diagnostic, DiagnosticLevel

ALLOWED_IMPORT_PREFIXES: set[str] = {
    "array",
    "bisect",
    "collections",
    "copy",
    "csv",
    "datetime",
    "decimal",
    "functools",
    "hashlib",
    "heapq",
    "itertools",
    "json",
    "math",
    "operator",
    "pathlib",
    "random",
    "re",
    "statistics",
    "string",
    "textwrap",
    "typing",
    "uuid",
    "columns",
    "row_types",
    "hooks",
}


class ConfigPackageValidator:
    """Perform static and dynamic validation for config packages."""

    def __init__(self) -> None:
        self._static_validator = ConfigValidationService()

    def validate(self, *, manifest: ManifestV1, package_dir: Path) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        diagnostics.extend(self._static_validator.validate(manifest, package_dir))
        diagnostics.extend(self._validate_imports(package_dir))
        diagnostics.extend(self._validate_manifest_abi(manifest))
        diagnostics.extend(self._run_dynamic_checks(manifest=manifest, package_dir=package_dir))
        return diagnostics

    def validate_archive_bytes(
        self,
        *,
        manifest: ManifestV1,
        archive_bytes: bytes,
    ) -> List[Diagnostic]:
        with tempfile.TemporaryDirectory(prefix="ade-config-validate-") as tmp:
            tmp_path = Path(tmp)
            self._extract_archive(archive_bytes, tmp_path)
            return self.validate(manifest=manifest, package_dir=tmp_path)

    def _validate_manifest_abi(self, manifest: ManifestV1) -> List[Diagnostic]:
        if manifest.config_script_api_version != "1":
            return [
                Diagnostic(
                    path="config_script_api_version",
                    code="script_api.unsupported",
                    message=(
                        "Unsupported config script API version "
                        f"{manifest.config_script_api_version!r}"
                    ),
                )
            ]
        return []

    def _validate_imports(self, package_dir: Path) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        for source in package_dir.rglob("*.py"):
            if "__pycache__" in source.parts:
                continue
            module_rel = source.relative_to(package_dir).as_posix()
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"))
            except SyntaxError:
                # Syntax errors are handled by the static validator already.
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".", 1)[0]
                        if root and root not in ALLOWED_IMPORT_PREFIXES:
                            diagnostics.append(
                                Diagnostic(
                                    path=module_rel,
                                    code="import.forbidden",
                                    message=f"Import of '{alias.name}' is not allowed",
                                    level=DiagnosticLevel.ERROR,
                                    hint="Use stdlib-only helpers or vendor dependencies inside the package directory.",
                                )
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.module is None:
                        # Relative import - allowed within package.
                        continue
                    module = node.module or ""
                    root = module.split(".", 1)[0]
                    if root and root not in ALLOWED_IMPORT_PREFIXES:
                        diagnostics.append(
                            Diagnostic(
                                path=module_rel,
                                code="import.forbidden",
                                message=f"Import from '{module}' is not allowed",
                                level=DiagnosticLevel.ERROR,
                                hint="Only standard library modules are permitted; vendor additional code within the package.",
                            )
                        )
        return diagnostics

    def _run_dynamic_checks(
        self,
        *,
        manifest: ManifestV1,
        package_dir: Path,
    ) -> List[Diagnostic]:
        worker = Path(__file__).with_name("validator_worker.py")
        payload = {
            "schema": "ade.validator_request/v1",
            "package_dir": str(package_dir),
            "manifest": manifest.model_dump(mode="json", by_alias=True),
        }
        env = {
            "PYTHONPATH": os.pathsep.join(
                [str(package_dir), str((package_dir / "vendor"))]
            ),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        }
        proc = subprocess.run(
            [sys.executable, "-I", "-B", str(worker)],
            input=json.dumps(payload).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(package_dir),
            check=False,
        )
        diagnostics: List[Diagnostic] = []
        if proc.stderr:
            diagnostics.append(
                Diagnostic(
                    path="validator",
                    code="validator.stderr",
                    message=proc.stderr.decode("utf-8", errors="replace")[:4000],
                    level=DiagnosticLevel.ERROR,
                )
            )
        if proc.returncode != 0:
            diagnostics.append(
                Diagnostic(
                    path="validator",
                    code="validator.exit",
                    message=f"Validator worker exited with code {proc.returncode}",
                    level=DiagnosticLevel.ERROR,
                )
            )
            return diagnostics
        try:
            result = json.loads(proc.stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            diagnostics.append(
                Diagnostic(
                    path="validator",
                    code="validator.invalid-json",
                    message=f"Validator worker returned invalid JSON: {exc}",
                    level=DiagnosticLevel.ERROR,
                )
            )
            return diagnostics
        for item in result.get("diagnostics", []):
            diagnostics.append(
                Diagnostic(
                    path=item.get("path", ""),
                    code=item.get("code", "unknown"),
                    message=item.get("message", ""),
                    level=DiagnosticLevel(item.get("level", "error")),
                    hint=item.get("hint"),
                )
            )
        return diagnostics

    @staticmethod
    def _extract_archive(archive_bytes: bytes, target_dir: Path) -> None:
        import zipfile

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:  # type: ignore[name-defined]
            archive.extractall(target_dir)


__all__ = ["ConfigPackageValidator"]
