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
    logger: Any | None = None,
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

        logger.note(
            "Mapped table",
            file=source_file,
            sheet=source_sheet,
            mapped_columns=len(mapping),
            extra_columns=len(extras),
            stage=stage,
        )

    # Example: just log, no structural change.
    return tables
