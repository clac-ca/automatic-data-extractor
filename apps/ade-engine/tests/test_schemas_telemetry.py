from datetime import datetime, timezone
from uuid import uuid4

from ade_engine.schemas.telemetry import AdeEvent


def test_telemetry_envelope_defaults():
    run_id = uuid4()
    workspace_id = uuid4()
    configuration_id = uuid4()
    envelope = AdeEvent(
        type="run.started",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        payload={"engine_version": "0.2.0"},
    )

    assert envelope.payload_dict()["engine_version"] == "0.2.0"
    assert envelope.workspace_id == workspace_id
    assert envelope.configuration_id == configuration_id
    assert envelope.run_id == run_id


def test_telemetry_serialization_round_trip():
    envelope = AdeEvent(
        type="run.phase.started",
        created_at=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        run_id=uuid4(),
        payload={"phase": "extracting", "level": "debug"},
    )

    data = envelope.model_dump()
    assert data["type"] == "run.phase.started"
    assert data["payload"]["phase"] == "extracting"
