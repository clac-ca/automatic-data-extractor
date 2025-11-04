"""Execute `on_activate` hooks inside an activated virtual environment."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.features.configs.spec import ManifestLoader
from backend.app.features.jobs.runtime.loader import ConfigPackageLoader


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run on_activate hooks for a config package")
    parser.add_argument("--config-dir", required=True, help="Path to the unpacked config package")
    parser.add_argument("--manifest-path", required=True, help="Path to the manifest.json inside the package")
    parser.add_argument("--output", required=True, help="Where to write hook annotations/diagnostics JSON")
    return parser.parse_args(argv)


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    model = ManifestLoader().load(payload)
    return model.model_dump(mode="json")


def _run_hooks(config_dir: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    loader = ConfigPackageLoader(config_dir)
    hook_modules = loader.load_hook_modules(manifest).get("on_activate", [])
    annotations: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    failed = False

    for hook in hook_modules:
        run_fn = getattr(hook.module, "run", None)
        if not callable(run_fn):
            diagnostics.append(
                {
                    "level": "warning",
                    "code": "activation.hook.missing_run",
                    "message": f"Hook {hook.path} does not define run()",
                    "path": hook.path,
                }
            )
            continue

        context = {
            "manifest": manifest,
            "env": manifest.get("env") or {},
            "artifact": {},
            "job_context": {"phase": "activation"},
        }
        try:
            result = run_fn(**context)
        except Exception as exc:  # pragma: no cover - defensive
            diagnostics.append(
                {
                    "level": "error",
                    "code": "activation.hook.exception",
                    "message": str(exc),
                    "path": f"{hook.path}:run",
                }
            )
            failed = True
            continue

        if isinstance(result, dict) and result:
            annotation = {
                "stage": "on_activate",
                "hook": hook.path,
                "annotated_at": datetime.now(timezone.utc).isoformat(),
            }
            annotation.update(result)
            annotations.append(annotation)

    return annotations, diagnostics, failed


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    config_dir = Path(args.config_dir).resolve()
    manifest_path = Path(args.manifest_path).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if str(config_dir) not in sys.path:
        sys.path.insert(0, str(config_dir))

    manifest = _load_manifest(manifest_path)
    annotations, diagnostics, failed = _run_hooks(config_dir, manifest)
    payload = {"annotations": annotations, "diagnostics": diagnostics}
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    raise SystemExit(main())
