from __future__ import annotations


class ExtractedTableNotFoundError(Exception):
    """Raised when a stored extraction table cannot be located."""

    def __init__(self, table_id: str) -> None:
        super().__init__(f"Extracted table '{table_id}' was not found")
        self.table_id = table_id


__all__ = ["ExtractedTableNotFoundError"]
