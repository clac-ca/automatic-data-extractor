"""Errors raised by the jobs service."""


class JobNotFoundError(Exception):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job {job_id} not found")
        self.job_id = job_id


class JobSubmissionError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


__all__ = ["JobNotFoundError", "JobSubmissionError"]
