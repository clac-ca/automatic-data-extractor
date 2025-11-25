from ade_engine.schemas.telemetry import TelemetryEnvelope, TelemetryEvent


def test_telemetry_envelope_defaults():
    event = TelemetryEvent(event="run_started", level="info", payload={"source_files": 1})
    envelope = TelemetryEnvelope(
        run_id="run-uuid",
        timestamp="2024-01-01T00:00:00Z",
        metadata={"run_id": "run-123"},
        event=event,
    )

    assert envelope.schema == "ade.telemetry/run-event.v1"
    assert envelope.version == "1.0.0"
    assert envelope.event.level == "info"
    assert envelope.event.payload["source_files"] == 1


def test_telemetry_serialization_round_trip():
    event = TelemetryEvent(event="pipeline_transition", level="debug", payload={"phase": "extracting"})
    envelope = TelemetryEnvelope(
        run_id="run-uuid",
        timestamp="2024-01-01T00:00:01Z",
        event=event,
    )

    data = envelope.model_dump()
    assert data["event"]["event"] == "pipeline_transition"
    assert data["metadata"] == {}
