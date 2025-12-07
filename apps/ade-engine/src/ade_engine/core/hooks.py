"""Hook execution utilities."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable

from openpyxl import Workbook

from ade_engine.config.hook_registry import HookContext, HookRegistry, HookStage
from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.errors import ConfigError, HookError
from ade_engine.core.types import (
    ExtractedTable,
    MappedTable,
    NormalizedTable,
    RunContext,
    RunResult,
)
from ade_engine.infra.event_emitter import ConfigEventEmitter

HookTable = ExtractedTable | MappedTable | NormalizedTable
HookTables = list[HookTable] | None


def _build_kwargs(context: HookContext) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "context": context,
        "run": context.run,
        "state": context.state,
        "input_file_name": context.input_file_name,
        "file_name": context.input_file_name,
        "manifest": context.manifest,
        "logger": context.logger,
        "event_emitter": context.event_emitter,
    }
    if context.table is not None:
        kwargs["table"] = context.table
    if context.tables is not None:
        kwargs["tables"] = context.tables
    if context.workbook is not None:
        kwargs["workbook"] = context.workbook
    if context.result is not None:
        kwargs["result"] = context.result

    return kwargs


def _validate_signature(hook: Callable[..., Any], *, stage: HookStage) -> None:
    signature = inspect.signature(hook)
    invalid_params = [
        p.name
        for p in signature.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY)
    ]
    if invalid_params:
        raise ConfigError(
            f"Hook '{hook.__module__}.{getattr(hook, '__name__', '<callable>')}' must use keyword-only parameters "
            f"(invalid: {', '.join(invalid_params)})"
        )

    if not any(param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        raise ConfigError(
            f"Hook '{hook.__module__}.{getattr(hook, '__name__', '<callable>')}' must accept **_ for forwards compatibility"
        )


def _invoke_hook(hook: Callable[..., Any], context: HookContext) -> Any:
    _validate_signature(hook, stage=context.stage)
    signature = inspect.signature(hook)
    kwargs = _build_kwargs(context)
    if any(param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return hook(**kwargs)
    filtered_kwargs = {name: kwargs[name] for name in signature.parameters if name in kwargs}
    return hook(**filtered_kwargs)


def run_hooks(
    stage: HookStage,
    registry: HookRegistry,
    *,
    run: RunContext,
    input_file_name: str | None = None,
    manifest: ManifestContext,
    logger: logging.Logger,
    event_emitter: ConfigEventEmitter,
    table: HookTable | None = None,
    tables: HookTables = None,
    workbook: Workbook | None = None,
    result: RunResult | None = None,
) -> HookContext:
    """Execute configured hooks for a stage with a rich context."""

    context = HookContext(
        run=run,
        state=run.state,
        input_file_name=input_file_name,
        manifest=manifest,
        table=table,
        tables=tables,
        workbook=workbook,
        result=result,
        logger=logger,
        event_emitter=event_emitter,
        stage=stage,
    )
    hooks = registry.get(stage, []) if registry else []
    if not hooks:
        return context

    for hook in hooks:
        try:
            ret = _invoke_hook(hook, context)
        except ConfigError:
            raise
        except Exception as exc:
            module = hook.__module__
            name = getattr(hook, "__name__", "<callable>")
            raise HookError(f"Hook '{module}.{name}' failed during {stage.value}") from exc

        if ret is None:
            continue

        if stage in {HookStage.ON_AFTER_EXTRACT, HookStage.ON_AFTER_MAPPING}:
            context.table = ret
        elif stage is HookStage.ON_BEFORE_SAVE:
            context.workbook = ret

    return context
