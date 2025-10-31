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


class ActiveConfigNotFoundError(Exception):
    """Raised when a workspace does not have an active configuration."""

    def __init__(self, workspace_id: str) -> None:
        super().__init__(f"Workspace '{workspace_id}' does not have an active configuration")
        self.workspace_id = workspace_id


class JobExecutionError(Exception):
    """Raised when the extractor fails during job execution."""

    def __init__(self, job_id: str, message: str) -> None:
        super().__init__(message)
        self.job_id = job_id


__all__ = [
    "ActiveConfigNotFoundError",
    "InputDocumentNotFoundError",
    "JobExecutionError",
    "JobNotFoundError",
]
