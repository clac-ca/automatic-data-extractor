from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from ade_engine.core.models import JobContext, JobPaths
from ade_engine.core.pipeline_types import FileExtraction
from ade_engine.pipeline.runner import PipelineRunner


class DummyLogger:
    def __init__(self) -> None:
        self.transitions: list[tuple[str, dict]] = []

    def transition(self, phase: str, **payload):
        self.transitions.append((phase, payload))


def _job(tmp_path: Path) -> JobContext:
    paths = JobPaths(
        jobs_root=tmp_path,
        job_dir=tmp_path / "job",
        input_dir=tmp_path / "job" / "input",
        output_dir=tmp_path / "job" / "output",
        logs_dir=tmp_path / "job" / "logs",
        artifact_path=tmp_path / "job" / "logs" / "artifact.json",
        events_path=tmp_path / "job" / "logs" / "events.ndjson",
    )
    return JobContext(
        job_id="test-job",
        manifest={},
        paths=paths,
        started_at=datetime.utcnow(),
    )


def test_pipeline_runner_success(tmp_path: Path):
    job = _job(tmp_path)
    logger = DummyLogger()
    runner = PipelineRunner(job, logger)

    extraction = FileExtraction(
        source_name="input.csv",
        sheet_name="Sheet1",
        mapped_columns=[],
        extra_columns=[],
        rows=[["a"]],
        header_row=["col"],
        validation_issues=[],
    )

    output = tmp_path / "out.xlsx"

    runner.run(
        extract_stage=lambda *_: [extraction],
        write_stage=lambda *_: output,
    )

    assert runner.phase.name == "COMPLETED"
    assert runner.tables == [extraction]
    assert runner.output_paths == (output,)
    assert any(phase == "writing_output" for phase, _ in logger.transitions)


def test_pipeline_runner_failure_marks_failed(tmp_path: Path):
    job = _job(tmp_path)
    logger = DummyLogger()
    runner = PipelineRunner(job, logger)

    with pytest.raises(RuntimeError):
        runner.run(
            extract_stage=lambda *_: [],
            write_stage=lambda *_: (_ for _ in ()).throw(RuntimeError("boom")),
        )

    assert runner.phase.name == "FAILED"
    assert any(phase == "failed" for phase, _ in logger.transitions)
