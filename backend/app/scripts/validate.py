"""CLI entry point for validating ADE config packages."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from backend.app.features.configs.spec import (
    ConfigPackageValidator,
    DiagnosticLevel,
    ManifestLoader,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ADE config packages")
    parser.add_argument(
        "package",
        nargs="+",
        help="Path to a config package directory or .zip archive",
    )
    args = parser.parse_args(argv)

    loader = ManifestLoader()
    validator = ConfigPackageValidator()

    exit_code = 0
    for raw_path in args.package:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            print(f"[error] {path} does not exist", file=sys.stderr)
            exit_code = 1
            continue

        if path.is_dir():
            manifest_path = path / "manifest.json"
            if not manifest_path.exists():
                print(f"[error] {path} is missing manifest.json", file=sys.stderr)
                exit_code = 1
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_model = loader.load(manifest)
            diagnostics = validator.validate(manifest=manifest_model, package_dir=path)
        elif path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path, "r") as archive:
                try:
                    with archive.open("manifest.json") as fh:
                        manifest = json.load(fh)
                except KeyError:
                    print(f"[error] {path} is missing manifest.json", file=sys.stderr)
                    exit_code = 1
                    continue
            manifest_model = loader.load(manifest)
            diagnostics = validator.validate_archive_bytes(
                manifest=manifest_model,
                archive_bytes=path.read_bytes(),
            )
        else:
            print(f"[error] Unsupported package type: {path}", file=sys.stderr)
            exit_code = 1
            continue

        title = manifest.get("info", {}).get("title", path.name)
        print(f"Validating: {title} ({path})")
        for diag in diagnostics:
            level = diag.level.value if hasattr(diag.level, "value") else str(diag.level)
            hint = f" hint={diag.hint}" if getattr(diag, "hint", None) else ""
            print(f" - [{level}] {diag.code} ({diag.path}): {diag.message}{hint}")
        errors = [d for d in diagnostics if d.level == DiagnosticLevel.ERROR]
        if errors:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
