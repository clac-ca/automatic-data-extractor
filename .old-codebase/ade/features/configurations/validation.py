"""Helpers for validating configuration script uploads."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import ast
import builtins
import hashlib
from multiprocessing import get_context
from queue import Empty
import textwrap
from types import MappingProxyType
from typing import Any


_MAX_SCRIPT_SIZE_BYTES = 32_768
_VALIDATION_TIMEOUT_SECONDS = 5.0


_ALLOWED_IMPORTS = {
    "math",
    "statistics",
    "decimal",
    "datetime",
    "json",
    "re",
    "itertools",
    "functools",
    "collections",
    "operator",
}

_ALLOWED_BUILTINS = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "pow",
    "range",
    "reversed",
    "round",
    "sorted",
    "sum",
    "tuple",
    "set",
    "frozenset",
    "zip",
    "map",
    "filter",
    "next",
    "isinstance",
    "issubclass",
    "Exception",
    "ValueError",
    "TypeError",
    "RuntimeError",
    "StopIteration",
    "object",
    "print",
    "slice",
    "property",
    "staticmethod",
    "classmethod",
    "NotImplemented",
    "NotImplementedError",
}


class ScriptValidationError(Exception):
    """Raised when script validation fails."""


@dataclass(slots=True, frozen=True)
class ScriptValidationOutcome:
    """Structured validation outcome for configuration scripts."""

    success: bool
    code_sha256: str
    doc_name: str | None
    doc_description: str | None
    doc_version: int | None
    errors: dict[str, list[str]] | None
    validated_at: datetime | None


def _restricted_import(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[str, ...] = (), level: int = 0):
    root = name.split(".", 1)[0]
    if root not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import of module '{root}' is not permitted in configuration scripts")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _build_restricted_builtins() -> MappingProxyType[str, Any]:
    allowed = {name: getattr(builtins, name) for name in _ALLOWED_BUILTINS if hasattr(builtins, name)}
    allowed["__import__"] = _restricted_import
    allowed["__build_class__"] = builtins.__build_class__
    allowed["__name__"] = "configuration_script"
    return MappingProxyType(allowed)


_RESTRICTED_GLOBALS = {
    "__builtins__": _build_restricted_builtins(),
    "__name__": "configuration_script",
}


def _parse_metadata(docstring: str | None) -> tuple[str | None, str | None, int | None, dict[str, list[str]]]:
    errors: dict[str, list[str]] = defaultdict(list)
    if not docstring:
        errors["docstring"].append("Module docstring is required with name, description, and version metadata.")
        return None, None, None, errors

    docstring = textwrap.dedent(docstring)
    name: str | None = None
    description: str | None = None
    version: int | None = None

    for raw_line in docstring.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if key == "name":
            name = value
        elif key == "description":
            description = value
        elif key == "version":
            try:
                version = int(value)
            except ValueError:
                errors["docstring.version"].append("Version must be an integer.")
        else:
            continue

    if name is None:
        errors["docstring.name"].append("Docstring must include a 'name' entry.")
    if version is None:
        errors["docstring.version"].append("Docstring must include a numeric 'version'.")

    return name, description, version, errors


def _collect_callable(env: dict[str, Any], prefix: str) -> list[Callable[..., Any]]:
    callables: list[Callable[..., Any]] = []
    for value in env.values():
        if callable(value) and getattr(value, "__name__", "").startswith(prefix):
            callables.append(value)
    return callables


def _validate_detect_functions(functions: list[Callable[..., Any]], errors: dict[str, list[str]]) -> None:
    if not functions:
        errors["functions"].append("At least one detect_ function must be defined.")
        return

    for func in functions:
        try:
            result = func(
                header="Synthetic header",
                values=["sample"],
                table=[["sample"]],
                column_index=0,
                sheet_name="Sheet",
                bounds=None,
                state={},
                context={},
            )
        except Exception as exc:  # pragma: no cover - we report the error message
            errors[f"function.{func.__name__}"].append(str(exc))
            continue

        if not isinstance(result, dict):
            errors[f"function.{func.__name__}"].append("detect_* must return a mapping.")
            continue
        scores = result.get("scores")
        if not isinstance(scores, dict) or not scores:
            errors[f"function.{func.__name__}"].append(
                "detect_* return value must include a non-empty 'scores' mapping."
            )
            continue
        for key, value in scores.items():
            if not isinstance(key, str):
                errors[f"function.{func.__name__}"].append("Score keys must be strings.")
            if not isinstance(value, (int, float)):
                errors[f"function.{func.__name__}"].append("Score values must be numeric.")


def _validate_transform_function(func: Callable[..., Any], errors: dict[str, list[str]]) -> None:
    try:
        result = func(
            value="sample",
            row_index=0,
            column_index=0,
            table=[["sample"]],
            context={},
            state={},
        )
    except Exception as exc:  # pragma: no cover - we report the error message
        errors[f"function.{func.__name__}"].append(str(exc))
        return

    if not isinstance(result, dict):
        errors[f"function.{func.__name__}"].append("transform_cell must return a mapping.")
        return
    cells = result.get("cells")
    if not isinstance(cells, dict):
        errors[f"function.{func.__name__}"].append("transform_cell must return a mapping with a 'cells' dictionary.")


def _disable_network_access() -> None:
    """Monkey patch ``socket`` to prevent outbound network calls."""

    try:
        import socket
    except ImportError:  # pragma: no cover - socket is always available but stay defensive
        return

    def _blocked(*_args: Any, **_kwargs: Any) -> None:  # pragma: no cover - defensive guard
        raise RuntimeError("Network access is disabled during validation.")

    class _NetworkDisabledSocket(socket.socket):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - simple guard
            _blocked()

    for name in ("socket", "create_connection", "create_server", "socketpair", "fromfd", "fromshare"):
        if hasattr(socket, name):
            setattr(socket, name, _blocked)
    socket.socket = _NetworkDisabledSocket  # type: ignore[assignment]


def _perform_validation(
    *, code: str, canonical_key: str, code_sha256: str
) -> ScriptValidationOutcome:
    """Execute validation logic inside an isolated process."""

    _disable_network_access()

    errors: dict[str, list[str]] = defaultdict(list)
    try:
        module = ast.parse(code)
    except SyntaxError as exc:
        errors["code"].append(f"Syntax error: {exc.msg} (line {exc.lineno})")
        return ScriptValidationOutcome(False, code_sha256, None, None, None, dict(errors), None)

    doc_name, doc_description, doc_version, metadata_errors = _parse_metadata(
        ast.get_docstring(module, clean=True)
    )
    for field, messages in metadata_errors.items():
        errors[field].extend(messages)

    if doc_name and doc_name != canonical_key:
        errors["docstring.name"].append(
            f"Docstring name '{doc_name}' must match canonical key '{canonical_key}'."
        )

    env: dict[str, Any] = dict(_RESTRICTED_GLOBALS)
    try:
        compiled = compile(module, filename="<configuration_script>", mode="exec")
        exec(compiled, env)  # noqa: S102 - intentional controlled exec
    except Exception as exc:  # pragma: no cover - we capture the message for the response
        errors["import"].append(str(exc))
        return ScriptValidationOutcome(
            False,
            code_sha256,
            doc_name,
            doc_description,
            doc_version,
            dict(errors),
            None,
        )

    detect_functions = _collect_callable(env, "detect_")
    _validate_detect_functions(detect_functions, errors)

    transform = None
    for value in env.values():
        if callable(value) and getattr(value, "__name__", "") == "transform_cell":
            transform = value
            break

    if transform is not None:
        _validate_transform_function(transform, errors)

    if errors:
        return ScriptValidationOutcome(
            False,
            code_sha256,
            doc_name,
            doc_description,
            doc_version,
            dict(errors),
            None,
        )

    return ScriptValidationOutcome(
        True,
        code_sha256,
        doc_name,
        doc_description,
        doc_version,
        None,
        datetime.now(tz=UTC).replace(microsecond=0),
    )


def _validation_worker(
    code: str, canonical_key: str, code_sha256: str, queue: Any
) -> None:
    """Run validation and communicate the outcome back to the parent process."""

    try:
        outcome = _perform_validation(
            code=code,
            canonical_key=canonical_key,
            code_sha256=code_sha256,
        )
    except Exception as exc:  # pragma: no cover - defensive safety net
        outcome = ScriptValidationOutcome(
            False,
            code_sha256,
            None,
            None,
            None,
            {"system": [f"Validation failed due to an internal error: {exc}"]},
            None,
        )
    queue.put(outcome)


def validate_configuration_script(
    *, code: str, canonical_key: str, code_sha256: str | None = None
) -> ScriptValidationOutcome:
    """Validate ``code`` for ``canonical_key`` returning structured feedback."""

    sha = code_sha256 or hashlib.sha256(code.encode("utf-8")).hexdigest()
    script_size = len(code.encode("utf-8"))
    if script_size > _MAX_SCRIPT_SIZE_BYTES:
        return ScriptValidationOutcome(
            False,
            sha,
            None,
            None,
            None,
            {
                "code": [
                    (
                        "Configuration script must be smaller than 32 KiB "
                        f"(received {script_size} bytes)."
                    )
                ]
            },
            None,
        )

    ctx = get_context("spawn")
    queue = ctx.Queue(maxsize=1)
    process = ctx.Process(
        target=_validation_worker,
        args=(code, canonical_key, sha, queue),
    )
    process.start()

    try:
        outcome = queue.get(timeout=_VALIDATION_TIMEOUT_SECONDS)
    except Empty:
        process.join(0.0)
        if process.is_alive():
            process.terminate()
            process.join()
            return ScriptValidationOutcome(
                False,
                sha,
                None,
                None,
                None,
                {
                    "timeout": [
                        (
                            "Validation exceeded 5.0 seconds and was terminated."
                        )
                    ]
                },
                None,
            )

        process.join()
        return ScriptValidationOutcome(
            False,
            sha,
            None,
            None,
            None,
            {
                "system": [
                    "Validation process exited unexpectedly. Please retry."
                ]
            },
            None,
        )
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        queue.close()

    return outcome


__all__ = [
    "ScriptValidationError",
    "ScriptValidationOutcome",
    "validate_configuration_script",
]

