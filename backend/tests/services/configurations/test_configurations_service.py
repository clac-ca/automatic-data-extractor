"""Unit tests for the configurations service layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
from typing import Any
from unittest.mock import Mock

import pytest

from backend.app.features.configurations.exceptions import ConfigurationScriptValidationError
from backend.app.features.configurations.schemas import ConfigurationScriptVersionIn
from backend.app.features.configurations.service import ConfigurationsService
from backend.app.features.configurations.validation import ScriptValidationOutcome


@dataclass
class _DummyConfiguration:
    id: str


@dataclass
class _DummyScript:
    script_version_id: str
    configuration_id: str
    canonical_key: str
    version: int
    code: str = "print('example')"
    code_sha256: str = ""
    language: str = "python"
    doc_name: str | None = None
    doc_description: str | None = None
    doc_declared_version: int | None = None
    validated_at: datetime | None = None
    validation_errors: dict[str, Any] | None = None
    created_by_user_id: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(tz=UTC).replace(microsecond=0)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(tz=UTC).replace(microsecond=0)
    )

    @property
    def id(self) -> str:
        return self.script_version_id


class _ValidationRepository:
    """Stub repository that supplies configuration and script fixtures."""

    def __init__(self, configuration: _DummyConfiguration, script: _DummyScript) -> None:
        self.configuration = configuration
        self.script = script
        self.update_calls: list[dict[str, Any]] = []

    async def get_configuration(self, *_args: Any, **_kwargs: Any) -> _DummyConfiguration:
        return self.configuration

    async def get_script_version(self, *_args: Any, **_kwargs: Any) -> _DummyScript:
        return self.script

    async def update_script_validation(
        self,
        script: _DummyScript,
        *,
        doc_name: str | None,
        doc_description: str | None,
        doc_version: int | None,
        validated_at: datetime | None,
        validation_errors: dict[str, list[str]] | None,
    ) -> _DummyScript:
        self.update_calls.append(
            {
                "doc_name": doc_name,
                "doc_description": doc_description,
                "doc_version": doc_version,
                "validated_at": validated_at,
                "validation_errors": validation_errors,
            }
        )
        script.doc_name = doc_name
        script.doc_description = doc_description
        script.doc_declared_version = doc_version
        script.validated_at = validated_at
        script.validation_errors = validation_errors
        script.updated_at = validated_at or script.updated_at
        return script


@pytest.mark.asyncio
async def test_validate_script_version_requires_if_match() -> None:
    """Service should block revalidation without an If-Match header."""

    configuration = _DummyConfiguration(id="cfg-1")
    script = _DummyScript(
        script_version_id="script-1",
        configuration_id="cfg-1",
        canonical_key="sample",
        version=1,
        code_sha256="abc123",
    )
    repository = _ValidationRepository(configuration, script)
    service = ConfigurationsService(session=Mock(), repository=repository)

    with pytest.raises(ConfigurationScriptValidationError) as excinfo:
        await service.validate_script_version(
            workspace_id="workspace-1",
            configuration_id="cfg-1",
            canonical_key="sample",
            script_version_id="script-1",
            if_match=None,
        )

    assert "If-Match header is required" in excinfo.value.errors["if-match"][0]


@pytest.mark.asyncio
async def test_validate_script_version_rejects_stale_if_match() -> None:
    """Service should raise a validation error when the checksum is stale."""

    configuration = _DummyConfiguration(id="cfg-1")
    script = _DummyScript(
        script_version_id="script-1",
        configuration_id="cfg-1",
        canonical_key="sample",
        version=1,
        code_sha256="abc123",
    )
    repository = _ValidationRepository(configuration, script)
    service = ConfigurationsService(session=Mock(), repository=repository)

    with pytest.raises(ConfigurationScriptValidationError) as excinfo:
        await service.validate_script_version(
            workspace_id="workspace-1",
            configuration_id="cfg-1",
            canonical_key="sample",
            script_version_id="script-1",
            if_match='W/"stale"',
        )

    assert "ETag mismatch" in excinfo.value.errors["if-match"][0]


@pytest.mark.asyncio
async def test_validate_script_version_updates_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful revalidation should refresh metadata and return the checksum."""

    configuration = _DummyConfiguration(id="cfg-1")
    script = _DummyScript(
        script_version_id="script-1",
        configuration_id="cfg-1",
        canonical_key="sample",
        version=1,
        code="print('hello world')",
    )
    script.code_sha256 = hashlib.sha256(script.code.encode("utf-8")).hexdigest()
    repository = _ValidationRepository(configuration, script)

    service = ConfigurationsService(session=Mock(), repository=repository)

    validated_at = datetime.now(tz=UTC).replace(microsecond=0)
    outcome = ScriptValidationOutcome(
        success=True,
        code_sha256=script.code_sha256,
        doc_name="sample",
        doc_description="Sample script",
        doc_version=2,
        errors=None,
        validated_at=validated_at,
    )
    monkeypatch.setattr(
        "backend.app.features.configurations.service.validate_configuration_script",
        lambda **_: outcome,
    )

    record, etag = await service.validate_script_version(
        workspace_id="workspace-1",
        configuration_id="cfg-1",
        canonical_key="sample",
        script_version_id="script-1",
        if_match=f'W/"{script.code_sha256}"',
    )

    assert etag == script.code_sha256
    assert record.doc_name == "sample"
    assert record.doc_description == "Sample script"
    assert record.doc_declared_version == 2
    assert record.validated_at == validated_at
    assert record.validation_errors is None
    assert record.code is None
    assert repository.update_calls, "validation metadata should be persisted"


@pytest.mark.asyncio
async def test_create_script_version_hashes_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """Creating a script should persist the checksum returned by validation."""

    configuration = _DummyConfiguration(id="cfg-1")
    created_script = _DummyScript(
        script_version_id="script-2",
        configuration_id="cfg-1",
        canonical_key="sample",
        version=2,
    )

    class _CreateRepository(_ValidationRepository):
        async def determine_next_script_version(self, *_args: Any, **_kwargs: Any) -> int:
            return 2

        async def create_script_version(self, **kwargs: Any) -> _DummyScript:
            self.create_kwargs = kwargs
            self.script.script_version_id = "script-2"
            self.script.configuration_id = kwargs["configuration_id"]
            self.script.canonical_key = kwargs["canonical_key"]
            self.script.version = kwargs["version"]
            self.script.language = kwargs["language"]
            self.script.code = kwargs["code"]
            self.script.code_sha256 = kwargs["code_sha256"]
            self.script.doc_name = kwargs["doc_name"]
            self.script.doc_description = kwargs["doc_description"]
            self.script.doc_declared_version = kwargs["doc_version"]
            self.script.validated_at = kwargs["validated_at"]
            self.script.validation_errors = kwargs["validation_errors"]
            self.script.created_by_user_id = kwargs["created_by_user_id"]
            return self.script

    repository = _CreateRepository(configuration, created_script)
    service = ConfigurationsService(session=Mock(), repository=repository)

    payload = ConfigurationScriptVersionIn(
        canonical_key="sample",
        language="python",
        code="print('hello world')",
    )
    expected_sha = hashlib.sha256(payload.code.encode("utf-8")).hexdigest()
    validated_at = datetime.now(tz=UTC).replace(microsecond=0)
    outcome = ScriptValidationOutcome(
        success=True,
        code_sha256=expected_sha,
        doc_name="sample",
        doc_description="Sample script",
        doc_version=1,
        errors=None,
        validated_at=validated_at,
    )
    monkeypatch.setattr(
        "backend.app.features.configurations.service.validate_configuration_script",
        lambda **_: outcome,
    )

    record, etag = await service.create_script_version(
        workspace_id="workspace-1",
        configuration_id="cfg-1",
        canonical_key="sample",
        payload=payload,
        actor_id="user-1",
    )

    assert etag == expected_sha
    assert record.script_version_id == "script-2"
    assert record.doc_name == "sample"
    assert record.doc_declared_version == 1
    assert repository.create_kwargs["code_sha256"] == expected_sha
