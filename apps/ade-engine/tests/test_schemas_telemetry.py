from datetime import datetime, timezone

from ade_engine.schemas.telemetry import AdeEvent


def test_telemetry_envelope_defaults():
    envelope = AdeEvent(
        type="run.started",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        run_id="run-uuid",
        workspace_id="ws-1",
        configuration_id="cfg-1",
        run={"engine_version": "0.2.0"},
    )

    assert envelope.schema == "ade.event/v1"
    assert envelope.version == "1.0.0"
    assert envelope.run["engine_version"] == "0.2.0"
    assert envelope.workspace_id == "ws-1"
    assert envelope.configuration_id == "cfg-1"


def test_telemetry_serialization_round_trip():
    envelope = AdeEvent(
        type="run.pipeline.progress",
        created_at=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        run_id="run-uuid",
        run={"phase": "extracting", "level": "debug"},
    )

    data = envelope.model_dump()
    assert data["type"] == "run.pipeline.progress"
    assert data["run"]["phase"] == "extracting"
