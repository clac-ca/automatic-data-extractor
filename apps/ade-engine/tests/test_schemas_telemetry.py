from datetime import datetime, timezone

from ade_engine.schemas.telemetry import AdeEvent


def test_telemetry_envelope_defaults():
    envelope = AdeEvent(
        type="run.started",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        run_id="run-uuid",
        workspace_id="ws-1",
        configuration_id="cfg-1",
        payload={"engine_version": "0.2.0"},
    )

    assert envelope.payload_dict()["engine_version"] == "0.2.0"
    assert envelope.workspace_id == "ws-1"
    assert envelope.configuration_id == "cfg-1"


def test_telemetry_serialization_round_trip():
    envelope = AdeEvent(
        type="run.phase.started",
        created_at=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        run_id="run-uuid",
        payload={"phase": "extracting", "level": "debug"},
    )

    data = envelope.model_dump()
    assert data["type"] == "run.phase.started"
    assert data["payload"]["phase"] == "extracting"
