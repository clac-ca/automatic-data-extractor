"""Queue handlers and helpers for job submission tasks."""

from __future__ import annotations

from typing import Any

from ade.db.session import get_sessionmaker
from ade.platform.config import get_settings
from ade.workers.task_queue import TaskMessage, TaskQueue

from .service import JobsService

JOB_SUBMISSION_TASK = "jobs.submit"


async def process_job_submission(message: TaskMessage) -> None:
    """Execute a queued job submission using the JobsService."""

    payload = dict(message.payload or {})
    settings = get_settings()
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        service = JobsService(session=session, settings=settings)
        await service.submit_job(
            workspace_id=str(payload["workspace_id"]),
            input_document_id=str(payload["input_document_id"]),
            configuration_id=str(payload["configuration_id"]),
            configuration_version=payload.get("configuration_version"),
            actor_id=payload.get("actor_id"),
        )


def register_job_tasks(queue: TaskQueue) -> None:
    """Subscribe the job submission handler to ``queue``."""

    async def _handler(message: TaskMessage) -> None:
        if message.name != JOB_SUBMISSION_TASK:
            return
        await process_job_submission(message)

    queue.subscribe(_handler)


async def enqueue_job_submission(
    queue: TaskQueue,
    *,
    workspace_id: str,
    input_document_id: str,
    configuration_id: str,
    configuration_version: int | None = None,
    actor_id: str | None = None,
) -> TaskMessage:
    """Enqueue a job submission task on ``queue``."""

    payload: dict[str, Any] = {
        "workspace_id": workspace_id,
        "input_document_id": input_document_id,
        "configuration_id": configuration_id,
    }
    if configuration_version is not None:
        payload["configuration_version"] = configuration_version
    if actor_id is not None:
        payload["actor_id"] = actor_id

    return await queue.enqueue(JOB_SUBMISSION_TASK, payload)


__all__ = [
    "JOB_SUBMISSION_TASK",
    "enqueue_job_submission",
    "process_job_submission",
    "register_job_tasks",
]
