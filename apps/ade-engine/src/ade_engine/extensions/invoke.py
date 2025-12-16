from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable
from weakref import WeakKeyDictionary

from ade_engine.models.errors import PipelineError


def _context_values(ctx: Any) -> dict[str, Any]:
    fields = getattr(ctx, "__dataclass_fields__", None)
    if fields:
        return {name: getattr(ctx, name) for name in fields}
    return getattr(ctx, "__dict__", {}).copy()


@dataclass(frozen=True)
class _CompiledExtension:
    positional_only: tuple[str, ...]
    keyword_params: tuple[str, ...]
    required: frozenset[str]
    accepts_kwargs: bool


_CACHE: WeakKeyDictionary[Callable[..., Any], _CompiledExtension] = WeakKeyDictionary()


def _compile_extension(fn: Callable[..., Any]) -> _CompiledExtension:
    sig = inspect.signature(fn)

    positional_only: list[str] = []
    keyword_params: list[str] = []
    required: set[str] = set()
    accepts_kwargs = False

    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            continue
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            accepts_kwargs = True
            continue

        if param.default is inspect.Parameter.empty:
            required.add(param.name)

        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            positional_only.append(param.name)
        else:
            keyword_params.append(param.name)

    return _CompiledExtension(
        positional_only=tuple(positional_only),
        keyword_params=tuple(keyword_params),
        required=frozenset(required),
        accepts_kwargs=accepts_kwargs,
    )


def _get_compiled(fn: Callable[..., Any]) -> _CompiledExtension:
    compiled = _CACHE.get(fn)
    if compiled is None:
        compiled = _compile_extension(fn)
        _CACHE[fn] = compiled
    return compiled


def call_extension(fn: Callable[..., Any], ctx: Any, *, label: str) -> Any:
    """
    Invoke an extension by mapping context fields to the function’s parameters.

    Instead of calling something opaque like:
        detect_email_header(ctx)

    We expand the context and call it the way config authors expect:

        detect_email_header(
            column_index=3,
            header="Email",
            values=["a@x.com", "b@y.com", None],
            values_sample=["a@x.com", "b@y.com"],
            sheet_name="Sheet1",
            metadata={...},
            state={...},
            input_file_name="input.xlsx",
            logger=...
        )

    Because:
        • Config authors should NOT need to understand the full internal ctx object.
        • Config code should be explicit about what data it uses.

    """

    compiled = _get_compiled(fn)
    ctx_data = _context_values(ctx)

    missing = sorted(name for name in compiled.required if name not in ctx_data)
    if missing:
        missing_list = ", ".join(missing)
        raise PipelineError(f"{label} is missing required parameters: {missing_list}")

    args = [ctx_data[name] for name in compiled.positional_only if name in ctx_data]
    kwargs = {name: ctx_data[name] for name in compiled.keyword_params if name in ctx_data}

    if compiled.accepts_kwargs:
        consumed = set(compiled.positional_only) | set(compiled.keyword_params)
        for key, value in ctx_data.items():
            if key not in consumed and key not in kwargs:
                kwargs[key] = value

    try:
        return fn(*args, **kwargs)
    except TypeError as exc:
        raise PipelineError(f"{label} has an incompatible signature: {exc}") from exc


__all__ = ["call_extension"]
