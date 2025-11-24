from ade_engine.schemas.artifact import (
    ArtifactError,
    ArtifactV1,
    ConfigArtifact,
    RunArtifact,
    TableArtifact,
    TableHeader,
    ValidationIssue,
)
from ade_engine.core.types import RunErrorCode, RunPhase, RunStatus


def build_sample_artifact() -> ArtifactV1:
    return ArtifactV1(
        run=RunArtifact(
            id="run-uuid",
            status=RunStatus.SUCCEEDED,
            started_at="2024-01-01T00:00:00Z",
            completed_at="2024-01-01T00:00:05Z",
            outputs=["normalized.xlsx"],
            engine_version="0.1.0",
        ),
        config=ConfigArtifact(schema="ade.manifest/v1", version="1.2.3", name="Config"),
        tables=[
            TableArtifact(
                source_file="input.xlsx",
                source_sheet="Sheet1",
                table_index=0,
                header=TableHeader(row_index=5, cells=["ID", "Email"]),
                mapped_columns=[],
                unmapped_columns=[],
                validation_issues=[
                    ValidationIssue(
                        row_index=10,
                        field="email",
                        code="invalid_format",
                        severity="error",
                        message="Email must look like user@domain.tld",
                        details={"value": "foo@"},
                    )
                ],
            )
        ],
        notes=[],
    )


def test_artifact_accepts_run_status_enum():
    artifact = build_sample_artifact()
    assert artifact.run.status is RunStatus.SUCCEEDED
    assert artifact.schema == "ade.artifact/v1"
    assert artifact.version == "1.0.0"


def test_artifact_error_shape():
    error = ArtifactError(
        code=RunErrorCode.INPUT_ERROR,
        stage=RunPhase.EXTRACTING,
        message="Missing source file",
        details={"source_file": "missing.xlsx"},
    )
    artifact = build_sample_artifact()
    artifact.run.error = error
    artifact.run.status = RunStatus.FAILED

    serialized = artifact.model_dump()
    assert serialized["run"]["error"]["code"] == RunErrorCode.INPUT_ERROR
    assert serialized["run"]["error"]["stage"] == RunPhase.EXTRACTING
    assert serialized["run"]["error"]["message"] == "Missing source file"


def test_artifact_validation_issue_round_trip():
    artifact = build_sample_artifact()
    assert artifact.tables[0].validation_issues[0].field == "email"
    schema = artifact.model_json_schema()
    assert "tables" in schema["properties"]
