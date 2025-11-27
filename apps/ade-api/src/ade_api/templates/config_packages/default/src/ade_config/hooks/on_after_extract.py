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
    logger: Any | None = None,
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
        logger.note(
            "Finished extract phase",
            stage=stage,
            table_count=len(tables),
        )

    # Example: drop empty tables
    filtered = []
    for t in tables:
        data_rows = getattr(t, "data_rows", []) or []
        if data_rows:
            filtered.append(t)
        elif logger is not None:
            logger.note(
                "Dropping empty table",
                file=str(getattr(t, "source_file", "")),
                sheet=getattr(t, "source_sheet", None),
                stage=stage,
            )

    return filtered
