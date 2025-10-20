"""JobWorker dispatch tests."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.shared.workers.task_queue import TaskQueue
from backend.app.shared.workers.run_jobs import JobWorker


pytestmark = pytest.mark.asyncio


async def test_worker_dispatches_registered_handler() -> None:
    queue = TaskQueue()
    worker = JobWorker(queue)

    received: list[str] = []

    async def handler(message) -> None:  # type: ignore[no-untyped-def]
        received.append(f"{message.name}:{message.payload.get('x')}")

    worker.register("test.task", handler)

    stop_event = asyncio.Event()
    task = asyncio.create_task(worker.run(shutdown_event=stop_event))
    # Ensure the worker has subscribed before enqueueing
    await asyncio.sleep(0)
    try:
        await queue.enqueue("test.task", {"x": 42})

        # Wait until the handler observes the message
        async def _wait_for_result():
            while not received:
                await asyncio.sleep(0.01)

        await asyncio.wait_for(_wait_for_result(), timeout=2)
        assert received == ["test.task:42"]
    finally:
        stop_event.set()
        await asyncio.wait_for(task, timeout=2)
