"""Worker process to execute dynamic config package validation."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import resource
import socket
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def main() -> None:
    try:
        request = json.loads(sys.stdin.read())
        if request.get("schema") != "ade.validator_request/v1":
            raise ValueError("Unsupported request schema")
        package_dir = Path(request["package_dir"]).resolve()
        manifest = request["manifest"]
        disable_network()
        apply_limits()
        diagnostics = run_checks(package_dir=package_dir, manifest=manifest)
        result = {"diagnostics": diagnostics}
    except Exception as exc:  # pragma: no cover - defensive path
        result = {
            "diagnostics": [
                {
                    "level": "error",
                    "code": "validator.exception",
                    "path": "",
                    "message": f"Validator worker failed: {exc}",
                    "hint": None,
                }
            ]
        }
        traceback.print_exc()
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()


def apply_limits() -> None:
    cpu_seconds = int(os.environ.get("ADE_VALIDATOR_CPU_SECONDS", "10"))
    mem_mb = int(os.environ.get("ADE_VALIDATOR_MEM_MB", "256"))
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    except Exception:  # pragma: no cover
        pass
    try:
        mem_bytes = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except Exception:  # pragma: no cover
        pass


def disable_network() -> None:
    def _blocked(*_args: Any, **_kwargs: Any) -> None:
        raise ConnectionError("Networking is disabled during validation")

    socket.socket = lambda *a, **k: (_blocked(*a, **k))  # type: ignore[assignment]
    socket.create_connection = lambda *a, **k: (_blocked(*a, **k))  # type: ignore[assignment]


def run_checks(*, package_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    sys.path.insert(0, str(package_dir))
    columns = (manifest.get("columns") or {}).get("meta") or {}
    for field_id, meta in columns.items():
        script_rel = meta.get("script")
        if not script_rel or not isinstance(script_rel, str):
            continue
        if not meta.get("enabled", True):
            continue
        module_path = package_dir / script_rel
        diagnostics.extend(_load_and_validate_column(field_id, module_path))
    hooks = manifest.get("hooks") or {}
    for hook_name, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            script_rel = entry.get("script") if isinstance(entry, dict) else None
            if not script_rel:
                continue
            module_path = package_dir / script_rel
            diagnostics.extend(_validate_hook_module(hook_name, index, module_path))
    return diagnostics


def _load_module(module_path: Path) -> tuple[Any | None, list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    if not module_path.exists():
        diagnostics.append(
            {
                "level": "error",
                "code": "module.missing",
                "path": module_path.as_posix(),
                "message": "Referenced module is missing from the package",
                "hint": None,
            }
        )
        return None, diagnostics
    spec = importlib.util.spec_from_file_location(f"ade_config.{module_path.stem}", module_path)
    module = importlib.util.module_from_spec(spec) if spec and spec.loader else None
    if module is None or spec is None or spec.loader is None:
        diagnostics.append(
            {
                "level": "error",
                "code": "module.load_failed",
                "path": module_path.as_posix(),
                "message": "Unable to load module for validation",
                "hint": None,
            }
        )
        return None, diagnostics
    try:
        spec.loader.exec_module(module)  # type: ignore[misc]
    except Exception as exc:
        diagnostics.append(
            {
                "level": "error",
                "code": "module.import_error",
                "path": module_path.as_posix(),
                "message": f"Import failed: {exc}",
                "hint": None,
            }
        )
        return None, diagnostics
    return module, diagnostics


def _load_and_validate_column(field_id: str, module_path: Path) -> list[dict[str, Any]]:
    module, diagnostics = _load_module(module_path)
    if module is None:
        return diagnostics
    transform = getattr(module, "transform", None)
    if transform is not None:
        if not callable(transform):
            diagnostics.append(
                {
                    "level": "error",
                    "code": "column.transform.invalid",
                    "path": module_path.as_posix(),
                    "message": "Column module transform must be callable when provided",
                    "hint": "Define transform(*, values, **_) to opt in to column transforms.",
                }
            )
        else:
            diagnostics.extend(_validate_transform_signature(module_path, transform))
            diagnostics.extend(_exercise_transform(module_path, transform))
    for name, attr in inspect.getmembers(module, inspect.isfunction):
        if name.startswith("detect_"):
            diagnostics.extend(_exercise_detector(module_path, name, attr))
    return diagnostics


def _validate_transform_signature(module_path: Path, transform: Callable[..., Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    sig = inspect.signature(transform)
    accepts_kwargs = any(param.kind is inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values())
    has_values_param = any(
        param.kind in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and param.name == "values"
        for param in sig.parameters.values()
    )
    if any(param.kind is inspect.Parameter.POSITIONAL_ONLY for param in sig.parameters.values()):
        diagnostics.append(
            {
                "level": "error",
                "code": "column.transform.signature",
                "path": module_path.as_posix(),
                "message": "transform() may not define positional-only parameters",
                "hint": (
                    "Use keyword-only arguments as part of the script API contract. "
                    "Recommended signature: transform(*, values, header=None, "
                    "column_index=None, **_)."
                ),
            }
        )
        return diagnostics
    if not has_values_param and not accepts_kwargs:
        diagnostics.append(
            {
                "level": "error",
                "code": "column.transform.signature",
                "path": module_path.as_posix(),
                "message": "transform() must accept a 'values' keyword argument",
                "hint": (
                    "Recommended signature: transform(*, values, header=None, "
                    "column_index=None, **_)."
                ),
            }
        )
    return diagnostics


def _exercise_transform(module_path: Path, transform: Callable[..., Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    signature = None
    try:
        signature = inspect.signature(transform)
    except (TypeError, ValueError):
        signature = None

    accepts_kwargs = False
    supported_params: set[str] = set()
    if signature is not None:
        for name, param in signature.parameters.items():
            if name == "self":
                continue
            if param.kind is inspect.Parameter.VAR_KEYWORD:
                accepts_kwargs = True
            if param.kind in (
                inspect.Parameter.KEYWORD_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                supported_params.add(name)
    else:
        accepts_kwargs = True

    payload = {
        "header": "Sample Header",
        "values": ["a", "b"],
        "column_index": 1,
        "table": {"id": "table-1"},
        "job_context": {"job_id": "validator"},
        "env": {},
    }
    kwargs: dict[str, Any] = {}
    for key, value in payload.items():
        if key == "values":
            kwargs[key] = value
            continue
        if key in supported_params or accepts_kwargs:
            kwargs[key] = value

    if "values" not in kwargs and ("values" in supported_params or accepts_kwargs):
        kwargs["values"] = payload["values"]

    try:
        result = transform(**kwargs)
    except Exception as exc:
        diagnostics.append(
            {
                "level": "error",
                "code": "column.transform.runtime",
                "path": module_path.as_posix(),
                "message": f"transform() raised an exception: {exc}",
                "hint": None,
            }
        )
        return diagnostics
    if not isinstance(result, dict):
        diagnostics.append(
            {
                "level": "error",
                "code": "column.transform.return",
                "path": module_path.as_posix(),
                "message": "transform() must return a dict",
                "hint": None,
            }
        )
        return diagnostics
    values = result.get("values")
    if not isinstance(values, list):
        diagnostics.append(
            {
                "level": "error",
                "code": "column.transform.values",
                "path": module_path.as_posix(),
                "message": "transform() must return a 'values' list",
                "hint": "Return {'values': [...], 'warnings': []}.",
            }
        )
    elif len(values) != 2:
        diagnostics.append(
            {
                "level": "error",
                "code": "column.transform.values.length",
                "path": module_path.as_posix(),
                "message": "transform() must return the same number of values it receives",
                "hint": None,
            }
        )
    warnings = result.get("warnings", [])
    if warnings is not None and not isinstance(warnings, list):
        diagnostics.append(
            {
                "level": "error",
                "code": "column.transform.warnings",
                "path": module_path.as_posix(),
                "message": "transform() warnings must be a list",
                "hint": None,
            }
        )
    return diagnostics


def _exercise_detector(module_path: Path, name: str, func: Callable[..., Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    try:
        result = func(
            header="Sample Header",
            values_sample=["a", "b"],
            column_index=1,
            table={"id": "table-1"},
            job_context={"job_id": "validator"},
            env={},
        )
    except Exception as exc:
        diagnostics.append(
            {
                "level": "error",
                "code": "column.detector.runtime",
                "path": module_path.as_posix(),
                "message": f"{name} raised an exception: {exc}",
                "hint": None,
            }
        )
        return diagnostics
    if not isinstance(result, dict):
        diagnostics.append(
            {
                "level": "error",
                "code": "column.detector.return",
                "path": module_path.as_posix(),
                "message": f"{name} must return a dict",
                "hint": None,
            }
        )
        return diagnostics
    scores = result.get("scores", {})
    if not isinstance(scores, dict):
        diagnostics.append(
            {
                "level": "error",
                "code": "column.detector.scores",
                "path": module_path.as_posix(),
                "message": f"{name} must return a scores mapping",
                "hint": "Return {'scores': {'field': 0.5}} with values between -1.0 and 1.0.",
            }
        )
        return diagnostics
    for value in scores.values():
        if not isinstance(value, (int, float)) or value < -1.0 or value > 1.0:
            diagnostics.append(
                {
                    "level": "error",
                    "code": "column.detector.score-range",
                    "path": module_path.as_posix(),
                    "message": f"{name} emitted score outside [-1.0, 1.0]",
                    "hint": "Clamp detector scores to the allowed range.",
                }
            )
            break
    return diagnostics


def _validate_hook_module(hook_name: str, index: int, module_path: Path) -> list[dict[str, Any]]:
    module, diagnostics = _load_module(module_path)
    if module is None:
        return diagnostics
    run = getattr(module, "run", None)
    if run is None or not callable(run):
        diagnostics.append(
            {
                "level": "error",
                "code": "hook.run.missing",
                "path": module_path.as_posix(),
                "message": "Hook module must expose a callable run() function",
                "hint": None,
            }
        )
        return diagnostics
    try:
        run(job_context={"job_id": "validator"}, manifest={}, env={}, artifact={})
    except Exception as exc:
        diagnostics.append(
            {
                "level": "error",
                "code": "hook.run.runtime",
                "path": module_path.as_posix(),
                "message": f"Hook run() raised an exception: {exc}",
                "hint": None,
            }
        )
    return diagnostics


if __name__ == "__main__":
    main()
