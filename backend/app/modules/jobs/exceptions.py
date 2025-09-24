"""Exception stubs for the jobs module rewrite."""

from __future__ import annotations


class JobNotFoundError(Exception):
    """Raised when a job identifier cannot be located."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job '{job_id}' was not found")
        self.job_id = job_id


class InputDocumentNotFoundError(Exception):
    """Raised when the referenced input document cannot be found."""

    def __init__(self, document_id: str) -> None:
        super().__init__(f"Document '{document_id}' was not found")
        self.document_id = document_id


__all__ = ["InputDocumentNotFoundError", "JobNotFoundError"]
