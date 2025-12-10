"""Decorator helpers for config packages."""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from ade_engine.registry.current import get_current_registry
from ade_engine.registry.models import FieldDef, HookName, RowKind


def field_meta(*, name: str, label: str | None = None, required: bool | None = None,
               dtype: str | None = None, synonyms: list[str] | None = None, **meta: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register or enrich a field definition.

    Intended to be used either standalone or stacked above detectors/transforms.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        registry = get_current_registry()
        existing = registry.fields.get(name)
        if existing:
            # Merge metadata onto the existing definition
            if label:
                existing.label = label
            if required is not None:
                existing.required = required
            if dtype:
                existing.dtype = dtype
            if synonyms:
                existing.synonyms = list(dict.fromkeys([*existing.synonyms, *synonyms]))
            if meta:
                existing.meta.update(meta)
        else:
            registry.register_field(
                FieldDef(
                    name=name,
                    label=label,
                    required=required or False,
                    dtype=dtype,
                    synonyms=synonyms or [],
                    meta=meta or {},
                )
            )
        return fn

    return decorator


def define_field(**kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    return field_meta(**kwargs)


def row_detector(*, row_kind: RowKind | str = RowKind.UNKNOWN, priority: int = 0):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        registry = get_current_registry()
        kind = row_kind.value if isinstance(row_kind, RowKind) else str(row_kind)
        registry.register_row_detector(fn, row_kind=kind, priority=priority)
        return fn

    return decorator


def column_detector(*, field: str, priority: int = 0):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        registry = get_current_registry()
        registry.register_column_detector(fn, field=field, priority=priority)
        return fn

    return decorator


def column_transform(*, field: str, priority: int = 0):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        registry = get_current_registry()
        registry.register_column_transform(fn, field=field, priority=priority)
        return fn

    return decorator


def cell_transformer(*, field: str, priority: int = 0):
    """Sugar to wrap a per-cell transformer into a column_transform."""

    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        @column_transform(field=field, priority=priority)
        @wraps(fn)
        def _column_transform(ctx):
            results = []
            for row_index, value in enumerate(ctx.values):
                res = fn(
                    value=value,
                    row_index=row_index,
                    field_name=ctx.field_name,
                    state=ctx.state,
                    metadata=ctx.metadata,
                    input_file_name=ctx.input_file_name,
                    logger=ctx.logger,
                )
                results.append(res)
            return results

        return _column_transform

    return wrapper


def column_validator(*, field: str, priority: int = 0):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        registry = get_current_registry()
        registry.register_column_validator(fn, field=field, priority=priority)
        return fn

    return decorator


def cell_validator(*, field: str, priority: int = 0):
    """Sugar to wrap per-cell validation into a column_validator."""

    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        @column_validator(field=field, priority=priority)
        @wraps(fn)
        def _validator(ctx):
            results = []
            for idx, value in enumerate(ctx.values):
                res = fn(
                    value=value,
                    row_index=idx,
                    field_name=ctx.field_name,
                    state=ctx.state,
                    metadata=ctx.metadata,
                    input_file_name=ctx.input_file_name,
                    logger=ctx.logger,
                )
                if res is not None:
                    results.append(res)
            return results

        return _validator

    return wrapper


def hook(hook_name: HookName, *, priority: int = 0):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        registry = get_current_registry()
        registry.register_hook(fn, hook_name=hook_name, priority=priority)
        return fn

    return decorator


__all__ = [
    "cell_transformer",
    "cell_validator",
    "column_detector",
    "column_transform",
    "column_validator",
    "define_field",
    "field_meta",
    "hook",
    "row_detector",
]
