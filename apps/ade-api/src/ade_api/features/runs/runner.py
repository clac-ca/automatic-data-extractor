"""Asynchronous supervisor for ADE engine subprocess streams."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from ade_api.common.logging import log_context

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StdoutFrame:
    """Single line emitted by the ADE engine process."""

    message: str
    stream: Literal["stdout", "stderr"] = "stdout"


# For now, runner frames are just stdout/stderr lines.
RunnerFrame = StdoutFrame


class EngineSubprocessRunner:
    """Manage a single ADE engine subprocess and stream its output."""

    def __init__(
        self,
        *,
        command: list[str],
        env: dict[str, str],
    ) -> None:
        self._command = command
        self._env = env
        self._queue: asyncio.Queue[RunnerFrame | None] = asyncio.Queue()
        self.returncode: int | None = None

    async def stream(self) -> AsyncIterator[RunnerFrame]:
        """Yield stdout/stderr lines as they are produced."""

        logger.debug(
            "run.engine.subprocess.start",
            extra=log_context(command=" ".join(self._command)),
        )

        process = await asyncio.create_subprocess_exec(
            *self._command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )

        assert process.stdout is not None
        assert process.stderr is not None

        stdout_task = asyncio.create_task(self._capture_stdout(process))
        stderr_task = asyncio.create_task(self._capture_stderr(process))

        completed = 0
        try:
            while completed < 2:
                item = await self._queue.get()
                if item is None:
                    completed += 1
                    continue
                yield item
        finally:
            stdout_task.cancel()
            stderr_task.cancel()
            with contextlib.suppress(Exception):
                await stdout_task
            with contextlib.suppress(Exception):
                await stderr_task

        self.returncode = await process.wait()
        logger.debug(
            "run.engine.subprocess.exit",
            extra=log_context(
                command=" ".join(self._command),
                returncode=self.returncode,
            ),
        )

    async def _capture_stdout(self, process: asyncio.subprocess.Process) -> None:
        assert process.stdout is not None
        try:
            async for raw_line in process.stdout:  # type: ignore[attr-defined]
                text = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if not text:
                    continue
                await self._queue.put(StdoutFrame(message=text, stream="stdout"))
        finally:
            await self._queue.put(None)

    async def _capture_stderr(self, process: asyncio.subprocess.Process) -> None:
        assert process.stderr is not None
        try:
            async for raw_line in process.stderr:  # type: ignore[attr-defined]
                text = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if not text:
                    continue
                await self._queue.put(StdoutFrame(message=text, stream="stderr"))
        finally:
            await self._queue.put(None)


__all__ = ["EngineSubprocessRunner", "RunnerFrame", "StdoutFrame"]