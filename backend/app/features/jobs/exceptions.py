"""Errors raised by the jobs service."""


class JobNotFoundError(Exception):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job {job_id} not found")
        self.job_id = job_id


class JobSubmissionError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class JobQueueFullError(Exception):
    def __init__(
        self,
        *,
        max_size: int,
        queue_size: int,
        max_concurrency: int,
    ) -> None:
        super().__init__(f"Job queue is full (max {max_size} items)")
        self.max_size = max_size
        self.queue_size = queue_size
        self.max_concurrency = max_concurrency


class JobQueueUnavailableError(Exception):
    def __init__(self) -> None:
        super().__init__("Job queue is not available")


__all__ = [
    "JobNotFoundError",
    "JobQueueFullError",
    "JobQueueUnavailableError",
    "JobSubmissionError",
]
