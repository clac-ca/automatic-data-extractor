from __future__ import annotations

from ade_engine.registry.models import HookName


def register(registry):
    registry.register_hook(on_table_mapped, hook_name=HookName.ON_TABLE_MAPPED, priority=0)


def on_table_mapped(
    *,
    hook_name,
    metadata,
    state,
    workbook,
    sheet,
    table,
    input_file_name,
    logger,
):
    """Optional mapping patch hook.

    Return a ColumnMappingPatch (or None). This is the place to:
      - call an LLM with the extracted headers
      - propose a patch for unmapped/incorrect fields
      - rename/drop passthrough columns

    This template returns None by default.
    """

    if logger and table:
        mapped_fields = [col.field_name for col in getattr(table, "mapped_columns", [])]
        logger.info("Config hook: table mapped (fields=%s)", mapped_fields)
    return None
