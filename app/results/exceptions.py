from __future__ import annotations


class ExtractedTableNotFoundError(Exception):
    """Raised when a stored extraction table cannot be located."""

    def __init__(self, table_id: str) -> None:
        super().__init__(f"Extracted table '{table_id}' was not found")
        self.table_id = table_id


class JobResultsUnavailableError(Exception):
    """Raised when tables are requested for a job that is not yet accessible."""

    def __init__(self, job_id: str, status: str) -> None:
        message = (
            f"Results for job '{job_id}' are not available while status is '{status}'"
        )
        super().__init__(message)
        self.job_id = job_id
        self.status = status


__all__ = ["ExtractedTableNotFoundError", "JobResultsUnavailableError"]
