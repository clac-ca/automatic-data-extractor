"""on_after_extract hook.

Runs after ExtractedTable objects have been built, before column mapping.
"""

from typing import Any


def run(
    *,
    tables: list[Any] | None = None,      # ExtractedTable[]
    run: Any | None = None,
    state: dict[str, Any] | None = None,
    manifest: Any | None = None,
    logger=None,
    event_emitter=None,
    stage: Any | None = None,
    **_: Any,
) -> list[Any] | None:
    """
    on_after_extract: inspect or reshape ExtractedTable objects.

    The engine passes in the ExtractedTable list as `tables` and expects you to
    return the list you want the mapping stage to see.

    Return:
        - list of ExtractedTable: to reorder/filter/modify tables.
        - None: to keep the original list (mutate in place if you wish).
    """
    if tables is None:
        return None

    if logger is not None:
        logger.info("Finished extract phase: %s tables", len(tables))

    # Example: drop empty tables
    filtered = []
    for t in tables:
        data_rows = getattr(t, "data_rows", []) or []
        if data_rows:
            filtered.append(t)
        elif logger is not None:
            logger.info(
                "Dropping empty table file=%s sheet=%s",
                getattr(t, "source_file", ""),
                getattr(t, "source_sheet", None),
            )

    return filtered
