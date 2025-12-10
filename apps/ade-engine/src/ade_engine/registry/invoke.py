from __future__ import annotations

import inspect
from typing import Any, Callable

from ade_engine.exceptions import PipelineError


def _context_values(ctx: Any) -> dict[str, Any]:
    fields = getattr(ctx, "__dataclass_fields__", None)
    if fields:
        return {name: getattr(ctx, name) for name in fields}
    return getattr(ctx, "__dict__", {}).copy()


def call_extension(fn: Callable[..., Any], ctx: Any, *, label: str) -> Any:
    """Invoke an extension function using keyword/positional args sourced from context fields."""

    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    ctx_data = _context_values(ctx)

    args: list[Any] = []
    kwargs: list[tuple[str, Any]] = []
    missing: list[str] = []

    for param in params:
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            continue  # extensions shouldn't rely on *args
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            continue  # allow **kwargs as a catch-all if present

        if param.name not in ctx_data:
            if param.default is inspect.Parameter.empty:
                missing.append(param.name)
            continue

        value = ctx_data[param.name]
        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            args.append(value)
        else:
            kwargs.append((param.name, value))

    if missing:
        missing_list = ", ".join(missing)
        raise PipelineError(f"{label} is missing required parameters: {missing_list}")

    try:
        return fn(*args, **dict(kwargs))
    except TypeError as exc:
        raise PipelineError(f"{label} has an incompatible signature: {exc}") from exc


__all__ = ["call_extension"]
