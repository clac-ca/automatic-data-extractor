from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from ade_api.features.runs.runner import EngineSubprocessRunner, StdoutFrame

pytestmark = pytest.mark.asyncio()


async def test_runner_streams_stdout_frames_and_stderr_lines(tmp_path: Path) -> None:
    script = tmp_path / "writer.py"
    script.write_text(
        "import json, sys, time\n"
        "frame = {\n"
        "    'schema_id': 'ade.engine.events.v1',\n"
        "    'event_id': '00000000-0000-0000-0000-000000000000',\n"
        "    'created_at': '2024-01-01T00:00:00Z',\n"
        "    'type': 'engine.phase.start',\n"
        "    'payload': {'phase': 'mapping'},\n"
        "}\n"
        "print(json.dumps(frame), flush=True)\n"
        "print('not-json', flush=True)\n"
        "time.sleep(0.05)\n"
        "sys.stderr.write('stderr-line\\n')\n"
        "sys.stderr.flush()\n",
        encoding="utf-8",
    )

    command = [sys.executable, str(script)]
    runner = EngineSubprocessRunner(command=command, env=os.environ.copy())

    frames = []
    async for frame in runner.stream():
        frames.append(frame)

    stdout_frames = [frame for frame in frames if isinstance(frame, StdoutFrame)]
    assert any(frame.stream == "stdout" for frame in stdout_frames)
    assert any(frame.stream == "stderr" for frame in stdout_frames)

    stdout_messages = [frame.message for frame in stdout_frames if frame.stream == "stdout"]
    parsed = json.loads(stdout_messages[0])
    assert parsed["type"] == "engine.phase.start"
