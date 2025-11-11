"""Pydantic schemas for configuration build API payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import BuildStatus

__all__ = [
    "BuildEnsureRequest",
    "BuildEnsureResponse",
    "BuildRecord",
]


class BuildRecord(BaseModel):
    """Serialized representation of a configuration build pointer."""

    model_config = ConfigDict(from_attributes=True)

    workspace_id: str = Field(..., description="Workspace identifier")
    config_id: str = Field(..., description="Configuration identifier")
    build_id: str = Field(..., description="Build identifier (ULID)")
    status: BuildStatus = Field(..., description="Current lifecycle status")
    venv_path: str = Field(..., description="Absolute path to the venv root")

    config_version: int | None = Field(None, description="Configuration version when built")
    content_digest: str | None = Field(None, description="Content fingerprint of the config")
    engine_version: str | None = Field(None, description="Installed ADE engine version")
    engine_spec: str | None = Field(None, description="Engine installation spec")
    python_version: str | None = Field(None, description="Interpreter version used")
    python_interpreter: str | None = Field(
        None, description="Path to the interpreter used for venv creation"
    )

    started_at: datetime | None = Field(None, description="When the build began")
    built_at: datetime | None = Field(None, description="When the build completed")
    expires_at: datetime | None = Field(None, description="When the build expires, if set")
    last_used_at: datetime | None = Field(None, description="Last time the build was used")
    error: str | None = Field(None, description="Error message, if build failed")


class BuildEnsureRequest(BaseModel):
    """Body accepted by PUT /build to trigger a rebuild."""

    model_config = ConfigDict(extra="forbid")

    force: bool = Field(False, description="Force rebuild even if fingerprint matches")
    wait: bool | None = Field(
        None,
        description=(
            "When true, wait up to ADE_BUILD_ENSURE_WAIT_SECONDS for an in-progress "
            "build to finish. When omitted, the default depends on the caller."
        ),
    )


class BuildEnsureResponse(BaseModel):
    """Response returned by ensure_build endpoints."""

    model_config = ConfigDict(extra="forbid")

    status: BuildStatus = Field(..., description="Resulting build status")
    build: BuildRecord | None = Field(
        None,
        description="Active build pointer when available",
    )

    def model_dump(self, *args, **kwargs):  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)
