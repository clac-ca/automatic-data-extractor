from datetime import datetime, timezone
from types import SimpleNamespace

from ade_engine.schemas.manifest import ColumnMeta

from ade_engine.pipeline.models import ColumnMapping, ColumnModule
from ade_engine.pipeline.normalize import normalize_rows
from ade_engine.core.models import JobContext, JobPaths


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


def test_normalize_rows_applies_transforms_and_validators() -> None:
    def transform(**kwargs):
        value = kwargs.get("value")
        if value:
            normalized = str(value).strip().lower()
            row = kwargs["row"]
            row[kwargs["field_name"]] = normalized
            return {kwargs["field_name"]: normalized}
        return None

    def validate(**kwargs):
        if not kwargs.get("value"):
            return [{"code": "missing"}]
        return []

    definition = ColumnMeta(label="Email", script="tests.email")
    module = ColumnModule(
        field="email",
        meta=definition.model_dump(),
        definition=definition,
        module=SimpleNamespace(),
        detectors=(),
        transformer=transform,
        validator=validate,
    )

    rows, issues = normalize_rows(
        _job(),
        [["USER@example.com"], [""]],
        ["email"],
        [ColumnMapping(field="email", header="Email", index=0, score=1.0, contributions=tuple())],
        [],
        {"email": module},
        {"email": module.meta},
        state={},
        logger=_DummyLogger(),
    )

    assert rows[0][0] == "user@example.com"
    assert issues[0]["code"] == "missing"


class _DummyLogger:
    def __getattr__(self, name):  # pragma: no cover - allow silent logging
        def _noop(*_args, **_kwargs):
            return None

        return _noop
