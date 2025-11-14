from datetime import datetime, timezone
from types import SimpleNamespace

from ade_engine.pipeline.mapping import (
    build_unmapped_header,
    column_sample,
    map_columns,
    match_header,
)
from ade_engine.pipeline.models import ColumnModule
from ade_engine.model import JobContext, JobPaths


class _DetectorModule(SimpleNamespace):
    pass


def _job() -> JobContext:
    paths = JobPaths(
        jobs_root=SimpleNamespace(),
        job_dir=SimpleNamespace(),
        input_dir=SimpleNamespace(),
        output_dir=SimpleNamespace(),
        logs_dir=SimpleNamespace(),
        artifact_path=SimpleNamespace(),
        events_path=SimpleNamespace(),
    )
    return JobContext(job_id="job", manifest={}, paths=paths, started_at=datetime.now(timezone.utc))


def test_map_columns_scores_best_match() -> None:
    def detect_email(**kwargs):
        header = kwargs.get("header")
        if header == "email":
            return {"scores": {"email": 2.0}}
        return {"scores": {}}

    modules = {
        "email": ColumnModule(
            field="email",
            meta={"label": "Email"},
            module=_DetectorModule(),
            detectors=(detect_email,),
            transformer=None,
            validator=None,
        )
    }

    mapping, extras = map_columns(
        _job(),
        ["Email", "Name"],
        [["test@example.com", "Jane"]],
        ["email"],
        {"email": {"label": "Email"}},
        modules,
        threshold=0.5,
        sample_size=4,
        append_unmapped=True,
        prefix="raw_",
        table_info={},
        state={},
        logger=_DummyLogger(),
    )

    assert mapping[0].field == "email"
    assert extras and extras[0].output_header.startswith("raw_")


def test_match_header_uses_synonyms() -> None:
    result = match_header(
        ["member_id"],
        {"member_id": {"label": "Member", "synonyms": ["ID"]}},
        "id",
        set(),
    )
    assert result == "member_id"


def test_column_sample_evenly_distributes_values() -> None:
    values = list(range(10))
    sample = column_sample(values, 4)
    assert len(sample) == 4
    assert sample[-1] == values[-1]


def test_build_unmapped_header_sanitizes_text() -> None:
    assert build_unmapped_header("raw_", "Employee Name", 0).startswith("raw_employee")


class _DummyLogger:
    def __getattr__(self, name):  # pragma: no cover - allow silent logging
        def _noop(*_args, **_kwargs):
            return None

        return _noop
