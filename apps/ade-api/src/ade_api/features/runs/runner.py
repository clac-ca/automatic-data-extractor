"""Asynchronous supervisor for ADE engine subprocess streams."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ade_engine.schemas import AdeEvent
from pydantic import ValidationError
from ade_api.shared.core.logging import log_context

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StdoutFrame:
    """Single stdout line emitted by the ADE engine process."""

    message: str
    stream: Literal["stdout", "stderr"] = "stdout"


RunnerFrame = StdoutFrame | AdeEvent


class EngineSubprocessRunner:
    """Manage a single ADE engine subprocess and stream its telemetry."""

    def __init__(
        self,
        *,
        command: list[str],
        run_dir: Path,
        env: dict[str, str],
        poll_interval: float = 0.2,
    ) -> None:
        self._command = command
        self._run_dir = run_dir
        self._env = env
        self._poll_interval = poll_interval
        self._queue: asyncio.Queue[RunnerFrame | None] = asyncio.Queue()
        self.returncode: int | None = None

    async def stream(self) -> AsyncIterator[RunnerFrame]:
        """Yield stdout lines and ADE events as they are produced."""

        process = await asyncio.create_subprocess_exec(
            *self._command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=self._env,
        )
        assert process.stdout is not None

        stdout_task = asyncio.create_task(self._capture_stdout(process))
        telemetry_task = asyncio.create_task(self._capture_telemetry(process))

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
            telemetry_task.cancel()
            with contextlib.suppress(Exception):
                await stdout_task
            with contextlib.suppress(Exception):
                await telemetry_task

        self.returncode = await process.wait()

    async def _capture_stdout(self, process: asyncio.subprocess.Process) -> None:
        assert process.stdout is not None
        try:
            async for raw_line in process.stdout:  # type: ignore[attr-defined]
                text = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if not text:
                    continue
                await self._queue.put(StdoutFrame(message=text))
        finally:
            await self._queue.put(None)

    async def _capture_telemetry(self, process: asyncio.subprocess.Process) -> None:
        events_path = self._run_dir / "logs" / "events.ndjson"
        position = 0
        try:
            while True:
                position, lines = await asyncio.to_thread(
                    _read_new_event_lines,
                    events_path,
                    position,
                )
                for line in lines:
                    if not line:
                        continue
                    try:
                        envelope = AdeEvent.model_validate_json(line)
                    except ValidationError as exc:
                        logger.warning(
                            "run.telemetry.invalid",
                            extra=log_context(
                                run_dir=str(self._run_dir),
                                line=line,
                                error=str(exc),
                            ),
                        )
                        continue
                    await self._queue.put(envelope)
                if process.returncode is not None and not lines:
                    break
                await asyncio.sleep(self._poll_interval)
        finally:
            await self._queue.put(None)


def _read_new_event_lines(path: Path, position: int) -> tuple[int, list[str]]:
    if not path.exists():
        return position, []
    with path.open("r", encoding="utf-8") as handle:
        handle.seek(position)
        data = handle.readlines()
        position = handle.tell()
    return position, [line.rstrip("\n") for line in data]


__all__ = ["EngineSubprocessRunner", "RunnerFrame", "StdoutFrame"]
