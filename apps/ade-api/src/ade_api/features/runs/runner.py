"""Minimal async subprocess runner used by run execution."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StdoutFrame:
    """Single line emitted by the ADE engine process."""

    message: str
    stream: Literal["stdout", "stderr"] = "stdout"


class EngineSubprocessRunner:
    """Spawn the engine subprocess and yield stdout/stderr lines."""

    def __init__(self, *, command: list[str], env: dict[str, str]) -> None:
        self._command = command
        self._env = env
        self.returncode: int | None = None

    async def stream(self) -> AsyncIterator[StdoutFrame]:
        process = await asyncio.create_subprocess_exec(
            *self._command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        assert process.stdout is not None and process.stderr is not None

        async def drain(pipe, stream: Literal["stdout", "stderr"]):
            async for raw in pipe:  # type: ignore[attr-defined]
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                if line:
                    yield StdoutFrame(message=line, stream=stream)

        stdout_iter = drain(process.stdout, "stdout")
        stderr_iter = drain(process.stderr, "stderr")

        async def merged() -> AsyncIterator[StdoutFrame]:
            tasks = {
                asyncio.create_task(stdout_iter.__anext__()): "stdout",
                asyncio.create_task(stderr_iter.__anext__()): "stderr",
            }
            while tasks:
                done, _ = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    stream_name = tasks.pop(task)
                    try:
                        frame = task.result()
                    except StopAsyncIteration:
                        continue
                    yield frame
                    # schedule next
                    next_task = asyncio.create_task(
                        (stdout_iter if stream_name == "stdout" else stderr_iter).__anext__()
                    )
                    tasks[next_task] = stream_name

        async for frame in merged():
            yield frame

        self.returncode = await process.wait()


__all__ = ["EngineSubprocessRunner", "StdoutFrame"]
