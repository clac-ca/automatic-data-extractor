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
        self._process: asyncio.subprocess.Process | None = None

    async def stream(self) -> AsyncIterator[StdoutFrame]:
        process = await asyncio.create_subprocess_exec(
            *self._command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        self._process = process
        assert process.stdout is not None and process.stderr is not None

        async def drain(
            pipe: asyncio.StreamReader, stream: Literal["stdout", "stderr"]
        ) -> AsyncIterator[StdoutFrame]:
            buffer = bytearray()

            while True:
                chunk = await pipe.read(64 * 1024)
                if not chunk:
                    break
                buffer.extend(chunk)

                while True:
                    newline_index = buffer.find(b"\n")
                    if newline_index < 0:
                        break
                    raw_line = buffer[:newline_index]
                    del buffer[: newline_index + 1]
                    line = raw_line.decode("utf-8", errors="replace")
                    if line:
                        yield StdoutFrame(message=line, stream=stream)

            if buffer:
                line = buffer.decode("utf-8", errors="replace").rstrip("\n")
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

        try:
            async for frame in merged():
                yield frame
            self.returncode = await process.wait()
        except asyncio.CancelledError:
            await self.terminate()
            raise

    async def terminate(self) -> None:
        process = self._process
        if process is None or process.returncode is not None:
            return
        process.kill()
        await process.wait()


__all__ = ["EngineSubprocessRunner", "StdoutFrame"]
