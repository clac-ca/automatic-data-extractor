from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ade_schemas import ADE_TELEMETRY_EVENT_SCHEMA

from apps.api.app.features.runs.runner import ADEProcessRunner, StdoutFrame

pytestmark = pytest.mark.asyncio()


async def test_runner_streams_stdout_and_telemetry(tmp_path: Path) -> None:
    script = tmp_path / "writer.py"
    events_path = tmp_path / "logs" / "events.ndjson"
    script.write_text(
        "import json, sys, time, pathlib\n"
        "events = pathlib.Path(sys.argv[1])\n"
        "events.parent.mkdir(parents=True, exist_ok=True)\n"
        "print('engine ready', flush=True)\n"
        "payload = {\n"
        "    'schema': 'ade.telemetry/run-event.v1',\n"
        "    'version': '1.0.0',\n"
        "    'job_id': 'job-1',\n"
        "    'run_id': 'run-1',\n"
        "    'timestamp': '2024-01-01T00:00:00Z',\n"
        "    'event': {'event': 'pipeline_transition', 'level': 'info', 'phase': 'mapping'},\n"
        "}\n"
        "time.sleep(0.05)\n"
        "events.write_text(json.dumps(payload) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )

    command = [sys.executable, str(script), str(events_path)]
    runner = ADEProcessRunner(command=command, job_dir=tmp_path, env=os.environ.copy())

    frames = []
    async for frame in runner.stream():
        frames.append(frame)

    stdout_frames = [frame for frame in frames if isinstance(frame, StdoutFrame)]
    assert stdout_frames, "expected stdout frames"
    telemetry = next(frame for frame in frames if not isinstance(frame, StdoutFrame))
    assert telemetry.schema == ADE_TELEMETRY_EVENT_SCHEMA
    assert telemetry.event.name == "pipeline_transition"
    assert telemetry.event.level == "info"
