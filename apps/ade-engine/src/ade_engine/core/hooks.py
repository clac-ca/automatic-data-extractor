"""Hook execution utilities."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from openpyxl import Workbook

from ade_engine.config.hook_registry import HookContext, HookRegistry, HookStage
from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.errors import HookError
from ade_engine.core.types import MappedTable, NormalizedTable, RawTable, RunContext, RunResult
from ade_engine.infra.telemetry import PipelineLogger

HookTables = list[RawTable | MappedTable | NormalizedTable] | None


def _build_kwargs(context: HookContext) -> dict[str, Any]:
    return {
        "context": context,
        "run": context.run,
        "state": context.state,
        "manifest": context.manifest,
        "tables": context.tables,
        "workbook": context.workbook,
        "result": context.result,
        "logger": context.logger,
        "stage": context.stage,
    }


def _invoke_hook(hook: Callable[..., Any], context: HookContext) -> None:
    signature = inspect.signature(hook)
    parameters = list(signature.parameters.values())

    if not parameters:
        hook(context)
        return

    first = parameters[0]
    if len(parameters) == 1 and first.kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        hook(context)
        return

    kwargs = _build_kwargs(context)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters):
        hook(**kwargs)
        return

    filtered_kwargs = {name: kwargs[name] for name in signature.parameters if name in kwargs}
    hook(**filtered_kwargs)


def run_hooks(
    stage: HookStage,
    registry: HookRegistry,
    *,
    run: RunContext,
    manifest: ManifestContext,
    logger: PipelineLogger,
    tables: HookTables = None,
    workbook: Workbook | None = None,
    result: RunResult | None = None,
) -> None:
    """Execute configured hooks for a stage with a rich context."""

    hooks = registry.get(stage, []) if registry else []
    if not hooks:
        return

    context = HookContext(
        run=run,
        state=run.state,
        manifest=manifest,
        tables=tables,
        workbook=workbook,
        result=result,
        logger=logger,
        stage=stage,
    )

    for hook in hooks:
        try:
            _invoke_hook(hook, context)
        except Exception as exc:
            module = hook.__module__
            name = getattr(hook, "__name__", "<callable>")
            raise HookError(f"Hook '{module}.{name}' failed during {stage.value}") from exc
