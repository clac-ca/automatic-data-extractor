"""on_after_mapping hook.

Runs after MappedTable objects have been produced, before normalization.
"""

from typing import Any


def run(
    *,
    tables: list[Any] | None = None,    # MappedTable[]
    run: Any | None = None,
    state: dict[str, Any] | None = None,
    manifest: Any | None = None,
    logger=None,
    event_emitter=None,
    stage: Any | None = None,
    **_: Any,
) -> list[Any] | None:
    """
    on_after_mapping: tweak mapped columns before normalization.

    Args:
        tables: list of MappedTable objects (mapping + extras metadata).

    Return:
        - list of MappedTable: to modify/reorder/drop tables.
        - None: to keep the original list (mutate in place if you wish).
    """
    if tables is None or logger is None:
        return tables

    for mapped_table in tables:
        extracted = getattr(mapped_table, "extracted", None)
        source_file = getattr(getattr(extracted, "source_file", None), "name", None)
        source_sheet = getattr(extracted, "source_sheet", None)
        mapping = getattr(mapped_table, "mapping", []) or []
        extras = getattr(mapped_table, "extras", []) or []

        logger.info(
            "Mapped table file=%s sheet=%s mapped=%s extras=%s",
            source_file,
            source_sheet,
            len(mapping),
            len(extras),
        )
        if event_emitter is not None:
            event_emitter.custom(
                "hook.mapping_checked",
                table_index=getattr(extracted, "table_index", None),
                mapped_columns=len(mapping),
                extra_columns=len(extras),
            )

    # Example: just log, no structural change.
    return tables
