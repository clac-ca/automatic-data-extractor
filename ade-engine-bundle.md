# Logical module layout (source -> sections below):
# - apps/ade-engine/pyproject.toml
# - apps/ade-engine/src/ade_engine.egg-info/PKG-INFO
# - apps/ade-engine/src/ade_engine.egg-info/SOURCES.txt
# - apps/ade-engine/src/ade_engine.egg-info/dependency_links.txt
# - apps/ade-engine/src/ade_engine.egg-info/requires.txt
# - apps/ade-engine/src/ade_engine.egg-info/top_level.txt
# - apps/ade-engine/src/ade_engine/__init__.py - ade_engine runtime package scaffold.
# - apps/ade-engine/src/ade_engine/__main__.py - Module entrypoint shim for ``python -m ade_engine``.
# - apps/ade-engine/src/ade_engine/config/__init__.py - Configuration and manifest loading helpers.
# - apps/ade-engine/src/ade_engine/config/loader.py - Manifest and environment resolution helpers.
# - apps/ade-engine/src/ade_engine/core/__init__.py - Core engine data structures shared across modules.
# - apps/ade-engine/src/ade_engine/core/manifest.py - Typed manifest models and helpers.
# - apps/ade-engine/src/ade_engine/core/models.py - Core engine data models.
# - apps/ade-engine/src/ade_engine/core/phases.py - Shared pipeline/job phase markers.
# - apps/ade-engine/src/ade_engine/core/pipeline_types.py - Dataclasses shared across pipeline stages.
# - apps/ade-engine/src/ade_engine/entrypoint.py - Console entrypoint for ``python -m ade_engine``.
# - apps/ade-engine/src/ade_engine/hooks/__init__.py - Hook loading and execution helpers.
# - apps/ade-engine/src/ade_engine/hooks/registry.py - Typed hook registry.
# - apps/ade-engine/src/ade_engine/job_service.py - Service object that encapsulates ADE job preparation and finalization.
# - apps/ade-engine/src/ade_engine/logging.py - Compatibility shim for legacy StructuredLogger imports.
# - apps/ade-engine/src/ade_engine/pipeline/__init__.py - Pipeline stage helpers for the ADE engine.
# - apps/ade-engine/src/ade_engine/pipeline/extract.py - Extract and normalize inputs into structured tables.
# - apps/ade-engine/src/ade_engine/pipeline/io.py - Input discovery and ingestion helpers.
# - apps/ade-engine/src/ade_engine/pipeline/mapping.py - Column mapping utilities.
# - apps/ade-engine/src/ade_engine/pipeline/models.py - Compatibility re-exports for pipeline dataclasses.
# - apps/ade-engine/src/ade_engine/pipeline/normalize.py - Row normalization and validation.
# - apps/ade-engine/src/ade_engine/pipeline/output.py - Output composition helpers.
# - apps/ade-engine/src/ade_engine/pipeline/processing.py - Pure helpers for transforming raw tables into normalized structures.
# - apps/ade-engine/src/ade_engine/pipeline/registry.py - Load and validate manifest-declared column modules.
# - apps/ade-engine/src/ade_engine/pipeline/runner.py - Composable pipeline runner for extract/write stages.
# - apps/ade-engine/src/ade_engine/pipeline/stages.py - Extract and write pipeline stages used by :class:`PipelineRunner`.
# - apps/ade-engine/src/ade_engine/pipeline/util.py - Small pipeline utility helpers.
# - apps/ade-engine/src/ade_engine/plugins/__init__.py - Plugin utilities.
# - apps/ade-engine/src/ade_engine/plugins/utils.py - Shared helpers for plugin/hook resolution.
# - apps/ade-engine/src/ade_engine/runtime.py - Runtime helpers for :mod:`ade_engine`.
# - apps/ade-engine/src/ade_engine/schemas/__init__.py - Shared schema models and JSON definitions used by the ADE engine.
# - apps/ade-engine/src/ade_engine/schemas/manifest.py - Compatibility re-exports for manifest schema models.
# - apps/ade-engine/src/ade_engine/schemas/manifest.v1.schema.json
# - apps/ade-engine/src/ade_engine/schemas/models.py - Compatibility re-exports for manifest schemas bundled with :mod:`ade_engine`.
# - apps/ade-engine/src/ade_engine/schemas/telemetry.event.v1.schema.json
# - apps/ade-engine/src/ade_engine/schemas/telemetry.py - Telemetry envelope schemas shared across ADE components.
# - apps/ade-engine/src/ade_engine/sinks.py - Compatibility shim; prefer :mod:`ade_engine.telemetry.sinks`.
# - apps/ade-engine/src/ade_engine/telemetry.py - Compatibility shim; prefer :mod:`ade_engine.telemetry.types`.
# - apps/ade-engine/src/ade_engine/telemetry/__init__.py - Telemetry types, sinks, and logging helpers.
# - apps/ade-engine/src/ade_engine/telemetry/logging.py - Pipeline-facing logger abstraction.
# - apps/ade-engine/src/ade_engine/telemetry/sinks.py - Artifact and event sink abstractions.
# - apps/ade-engine/src/ade_engine/telemetry/types.py - Telemetry configuration helpers for ADE runtime instrumentation.
# - apps/ade-engine/src/ade_engine/worker.py - Job orchestration for the ADE engine (legacy adapter).
# - apps/ade-engine/tests/conftest.py
# - apps/ade-engine/tests/pipeline/test_io.py
# - apps/ade-engine/tests/pipeline/test_mapping.py
# - apps/ade-engine/tests/pipeline/test_normalize.py
# - apps/ade-engine/tests/pipeline/test_output.py
# - apps/ade-engine/tests/pipeline/test_registry.py
# - apps/ade-engine/tests/test_hooks_registry.py
# - apps/ade-engine/tests/test_main.py
# - apps/ade-engine/tests/test_pipeline_runner_unit.py
# - apps/ade-engine/tests/test_placeholder.py
# - apps/ade-engine/tests/test_runtime.py
# - apps/ade-engine/tests/test_telemetry.py
# - apps/ade-engine/tests/test_worker.py

# apps/ade-engine/pyproject.toml
```
[build-system]
requires = ["setuptools>=80"]
build-backend = "setuptools.build_meta"

[project]
name = "ade-engine"
version = "0.1.1"
description = "ADE engine runtime package (scaffold)."
requires-python = ">=3.12"
readme = { text = "Placeholder runtime package; implementation forthcoming.", content-type = "text/plain" }
license = { text = "Proprietary" }
dependencies = [
    "openpyxl>=3.1",
    "jsonschema>=4.21",
    "pydantic>=2.6",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"ade_engine.schemas" = ["*.json"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
```

# apps/ade-engine/src/ade_engine.egg-info/PKG-INFO
```
Metadata-Version: 2.4
Name: ade-engine
Version: 0.1.1
Summary: ADE engine runtime package (scaffold).
License: Proprietary
Requires-Python: >=3.12
Description-Content-Type: text/plain
Requires-Dist: openpyxl>=3.1
Requires-Dist: jsonschema>=4.21
Requires-Dist: pydantic>=2.6

Placeholder runtime package; implementation forthcoming.
```

# apps/ade-engine/src/ade_engine.egg-info/SOURCES.txt
```
pyproject.toml
src/ade_engine/__init__.py
src/ade_engine/__main__.py
src/ade_engine/entrypoint.py
src/ade_engine/job_service.py
src/ade_engine/logging.py
src/ade_engine/runtime.py
src/ade_engine/sinks.py
src/ade_engine/telemetry.py
src/ade_engine/worker.py
src/ade_engine.egg-info/PKG-INFO
src/ade_engine.egg-info/SOURCES.txt
src/ade_engine.egg-info/dependency_links.txt
src/ade_engine.egg-info/requires.txt
src/ade_engine.egg-info/top_level.txt
src/ade_engine/config/__init__.py
src/ade_engine/config/loader.py
src/ade_engine/core/__init__.py
src/ade_engine/core/manifest.py
src/ade_engine/core/models.py
src/ade_engine/core/phases.py
src/ade_engine/core/pipeline_types.py
src/ade_engine/hooks/__init__.py
src/ade_engine/hooks/registry.py
src/ade_engine/pipeline/__init__.py
src/ade_engine/pipeline/extract.py
src/ade_engine/pipeline/io.py
src/ade_engine/pipeline/mapping.py
src/ade_engine/pipeline/models.py
src/ade_engine/pipeline/normalize.py
src/ade_engine/pipeline/output.py
src/ade_engine/pipeline/processing.py
src/ade_engine/pipeline/registry.py
src/ade_engine/pipeline/runner.py
src/ade_engine/pipeline/stages.py
src/ade_engine/pipeline/util.py
src/ade_engine/plugins/__init__.py
src/ade_engine/plugins/utils.py
src/ade_engine/schemas/__init__.py
src/ade_engine/schemas/manifest.py
src/ade_engine/schemas/manifest.v1.schema.json
src/ade_engine/schemas/models.py
src/ade_engine/schemas/telemetry.event.v1.schema.json
src/ade_engine/schemas/telemetry.py
src/ade_engine/telemetry/__init__.py
src/ade_engine/telemetry/logging.py
src/ade_engine/telemetry/sinks.py
src/ade_engine/telemetry/types.py
tests/test_hooks_registry.py
tests/test_main.py
tests/test_pipeline_runner_unit.py
tests/test_placeholder.py
tests/test_runtime.py
tests/test_telemetry.py
tests/test_worker.py
```

# apps/ade-engine/src/ade_engine.egg-info/dependency_links.txt
```

```

# apps/ade-engine/src/ade_engine.egg-info/requires.txt
```
openpyxl>=3.1
jsonschema>=4.21
pydantic>=2.6
```

# apps/ade-engine/src/ade_engine.egg-info/top_level.txt
```
ade_engine
```

# apps/ade-engine/src/ade_engine/__init__.py
```python
"""ade_engine runtime package scaffold."""

from __future__ import annotations

from importlib import metadata as _metadata

from pathlib import Path

from ade_engine.core.models import EngineMetadata, JobResult
from ade_engine.core.manifest import ManifestContext
from ade_engine.job_service import JobService
from ade_engine.runtime import (
    ManifestNotFoundError,
    load_config_manifest,
    load_manifest_context,
    resolve_jobs_root,
)
from ade_engine.telemetry.types import TelemetryConfig
from ade_engine.hooks import HookExecutionError, HookLoadError
from ade_engine.sinks import SinkProvider

from . import worker as _worker

try:  # pragma: no cover - executed when package metadata is available
    __version__ = _metadata.version("ade-engine")
except _metadata.PackageNotFoundError:  # pragma: no cover - local source tree fallback
    __version__ = "0.0.0"

DEFAULT_METADATA = EngineMetadata(version=__version__)


def run_job(
    job_id: str,
    *,
    jobs_dir: Path | None = None,
    manifest_path: Path | None = None,
    config_package: str = "ade_config",
    safe_mode: bool = False,
    sink_provider: SinkProvider | None = None,
    telemetry: TelemetryConfig | None = None,
) -> JobResult:
    """Engine interface for running ADE jobs."""

    return _worker.run_job(
        job_id,
        jobs_dir=jobs_dir,
        manifest_path=manifest_path,
        config_package=config_package,
        safe_mode=safe_mode,
        sink_provider=sink_provider,
        telemetry=telemetry,
    )

__all__ = [
    "DEFAULT_METADATA",
    "EngineMetadata",
    "JobService",
    "ManifestContext",
    "ManifestNotFoundError",
    "__version__",
    "load_config_manifest",
    "load_manifest_context",
    "resolve_jobs_root",
    "TelemetryConfig",
    "HookExecutionError",
    "HookLoadError",
    "run_job",
]
```

# apps/ade-engine/src/ade_engine/__main__.py
```python
"""Module entrypoint shim for ``python -m ade_engine``."""

from .entrypoint import console_entrypoint, main

__all__ = ["console_entrypoint", "main"]

if __name__ == "__main__":  # pragma: no cover - manual execution path
    console_entrypoint()
```

# apps/ade-engine/src/ade_engine/config/__init__.py
```python
"""Configuration and manifest loading helpers."""

from .loader import (
    ManifestNotFoundError,
    load_manifest,
    resolve_input_sheets,
    resolve_jobs_root,
)

__all__ = [
    "ManifestNotFoundError",
    "load_manifest",
    "resolve_input_sheets",
    "resolve_jobs_root",
]
```

# apps/ade-engine/src/ade_engine/config/loader.py
```python
"""Manifest and environment resolution helpers."""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, ValidationError

from ade_engine.core.manifest import ManifestContext, ManifestV1


class ManifestNotFoundError(RuntimeError):
    """Raised when the ade_config manifest cannot be located."""


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise ManifestNotFoundError(f"Manifest not found at {path}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - malformed manifest
        raise ManifestNotFoundError(f"Manifest is not valid JSON: {path}") from exc


def _manifest_version(manifest: Mapping[str, Any]) -> str | None:
    if isinstance(manifest.get("info"), Mapping):
        schema_value = manifest["info"].get("schema")
        if isinstance(schema_value, str):
            return schema_value
    return None


def _load_manifest_schema() -> dict[str, Any]:
    schema_resource = resources.files("ade_engine.schemas") / "manifest.v1.schema.json"
    return json.loads(schema_resource.read_text(encoding="utf-8"))


_MANIFEST_VALIDATOR = Draft202012Validator(_load_manifest_schema())


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    schema_tag = _manifest_version(manifest)
    if not schema_tag:
        raise ManifestNotFoundError("Manifest missing required info.schema version tag")
    if not schema_tag.startswith("ade.manifest/v1"):
        raise ManifestNotFoundError(f"Unsupported manifest schema: {schema_tag}")
    try:
        _MANIFEST_VALIDATOR.validate(manifest)
    except ValidationError as exc:  # pragma: no cover - jsonschema formats message
        raise ManifestNotFoundError(f"Manifest failed validation: {exc.message}") from exc


def load_manifest(
    *,
    package: str = "ade_config",
    resource: str = "manifest.json",
    manifest_path: Path | None = None,
) -> ManifestContext:
    """Read, validate, and parse a manifest into a ManifestContext."""

    if manifest_path is not None:
        manifest = _read_manifest(manifest_path)
    else:
        try:
            resource_path = resources.files(package) / resource
        except ModuleNotFoundError as exc:
            raise ManifestNotFoundError(f"Config package '{package}' cannot be imported.") from exc
        else:
            if not resource_path.is_file():
                raise ManifestNotFoundError(f"Resource '{resource}' not found in '{package}'.")
            manifest = _read_manifest(Path(resource_path))

    _validate_manifest(manifest)

    model = ManifestV1.model_validate(manifest)
    return ManifestContext(
        raw=manifest,
        version=_manifest_version(manifest),
        model=model,
    )


def resolve_jobs_root(
    jobs_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the jobs root using explicit args, ADE_JOBS_DIR, or ADE_DATA_DIR."""

    env = os.environ if env is None else env

    if jobs_dir is not None:
        return Path(jobs_dir)

    if env.get("ADE_JOBS_DIR"):
        return Path(env["ADE_JOBS_DIR"])

    data_dir = Path(env.get("ADE_DATA_DIR", "./data"))
    return data_dir / "jobs"


def resolve_input_sheets(env: Mapping[str, str] | None = None) -> list[str] | None:
    """Normalize sheet selection from ADE_RUN_INPUT_SHEET(S) env vars."""

    env = os.environ if env is None else env

    sheets_raw = env.get("ADE_RUN_INPUT_SHEETS")
    if sheets_raw:
        parsed: Any
        try:
            parsed = json.loads(sheets_raw)
        except json.JSONDecodeError:
            parsed = sheets_raw
        candidates: list[str] = []
        if isinstance(parsed, list):
            candidates = [str(value) for value in parsed]
        elif isinstance(parsed, str):
            candidates = [part for part in parsed.split(",")]
        cleaned = [value.strip() for value in candidates if str(value).strip()]
        if cleaned:
            return cleaned

    single_sheet = env.get("ADE_RUN_INPUT_SHEET")
    if single_sheet:
        cleaned = str(single_sheet).strip()
        if cleaned:
            return [cleaned]

    return None


__all__ = [
    "ManifestNotFoundError",
    "load_manifest",
    "resolve_input_sheets",
    "resolve_jobs_root",
]
```

# apps/ade-engine/src/ade_engine/core/__init__.py
```python
"""Core engine data structures shared across modules."""

from .manifest import (
    ColumnMeta,
    ColumnSection,
    EngineDefaults,
    EngineSection,
    EngineWriter,
    HookCollection,
    ManifestContext,
    ManifestInfo,
    ManifestV1,
    ScriptRef,
)
from .models import EngineMetadata, JobContext, JobPaths, JobResult
from .phases import JobStatus, PipelinePhase
from .pipeline_types import (
    ColumnMapping,
    ColumnModule,
    ExtraColumn,
    FileExtraction,
    ScoreContribution,
    TableProcessingResult,
)

__all__ = [
    "ColumnMapping",
    "ColumnMeta",
    "ColumnModule",
    "ColumnSection",
    "EngineDefaults",
    "EngineMetadata",
    "EngineSection",
    "EngineWriter",
    "ExtraColumn",
    "FileExtraction",
    "HookCollection",
    "JobContext",
    "JobPaths",
    "JobResult",
    "JobStatus",
    "ManifestContext",
    "ManifestInfo",
    "ManifestV1",
    "PipelinePhase",
    "ScoreContribution",
    "ScriptRef",
    "TableProcessingResult",
]
```

# apps/ade-engine/src/ade_engine/core/manifest.py
```python
"""Typed manifest models and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field


class ScriptRef(BaseModel):
    """Reference to a hook script."""

    model_config = ConfigDict(extra="forbid")

    script: str
    enabled: bool = True


class HookCollection(BaseModel):
    """Collection of hook definitions grouped by lifecycle stage."""

    model_config = ConfigDict(extra="forbid")

    on_activate: tuple[ScriptRef, ...] = ()
    on_job_start: tuple[ScriptRef, ...] = ()
    on_after_extract: tuple[ScriptRef, ...] = ()
    on_before_save: tuple[ScriptRef, ...] = ()
    on_job_end: tuple[ScriptRef, ...] = ()


class ColumnMeta(BaseModel):
    """Metadata describing an output column."""

    model_config = ConfigDict(extra="forbid")

    label: str
    script: str
    required: bool = False
    enabled: bool = True
    synonyms: tuple[str, ...] = ()
    type_hint: str | None = None


class ColumnSection(BaseModel):
    """Manifest ``columns`` section."""

    model_config = ConfigDict(extra="forbid")

    order: list[str]
    meta: dict[str, ColumnMeta]


class EngineDefaults(BaseModel):
    """Defaults that influence pipeline behaviour."""

    model_config = ConfigDict(extra="forbid")

    timeout_ms: int | None = Field(default=None, ge=1000)
    memory_mb: int | None = Field(default=None, ge=64)
    runtime_network_access: bool = False
    mapping_score_threshold: float | None = Field(default=None, ge=0.0)
    detector_sample_size: int | None = Field(default=None, ge=1)


class EngineWriter(BaseModel):
    """Output writer configuration."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["row_streaming", "in_memory"] = Field(default="row_streaming")
    append_unmapped_columns: bool = True
    unmapped_prefix: str = Field(default="raw_", min_length=1)
    output_sheet: str = Field(default="Normalized", min_length=1, max_length=31)


class EngineSection(BaseModel):
    """Manifest ``engine`` section."""

    model_config = ConfigDict(extra="forbid")

    defaults: EngineDefaults = Field(default_factory=EngineDefaults)
    writer: EngineWriter = Field(default_factory=EngineWriter)


class ManifestInfo(BaseModel):
    """Metadata describing the config package itself."""

    model_config = ConfigDict(extra="forbid")

    schema: Literal["ade.manifest/v1.0"]
    title: str
    version: str
    description: str | None = None


class ManifestV1(BaseModel):
    """Typed representation of a v1 manifest."""

    model_config = ConfigDict(extra="forbid")

    config_script_api_version: Literal["1"]
    info: ManifestInfo
    engine: EngineSection
    hooks: HookCollection = Field(default_factory=HookCollection)
    columns: ColumnSection
    env: dict[str, str] = Field(default_factory=dict)


@dataclass(slots=True)
class ManifestContext:
    """Single manifest representation for the engine."""

    raw: dict[str, object]
    version: str | None = None
    model: ManifestV1 | None = None

    @property
    def column_order(self) -> list[str]:
        if self.model is not None:
            return list(self.model.columns.order)
        columns = (self.raw.get("columns") or {})
        if isinstance(columns, Mapping):
            order = columns.get("order", [])
            if isinstance(order, Iterable):
                return [str(item) for item in order]
        return []

    @property
    def column_meta_models(self) -> dict[str, ColumnMeta]:
        if self.model is not None:
            return dict(self.model.columns.meta)

        columns = self.raw.get("columns") or {}
        result: dict[str, ColumnMeta] = {}
        if isinstance(columns, Mapping):
            meta = columns.get("meta", {})
            if isinstance(meta, Mapping):
                for field, value in meta.items():
                    if isinstance(value, Mapping):
                        try:
                            result[str(field)] = ColumnMeta.model_validate(value)
                        except Exception:  # pragma: no cover - validation fallback
                            continue
        return result

    @property
    def defaults(self) -> EngineDefaults:
        if self.model is not None:
            return self.model.engine.defaults
        engine = self.raw.get("engine") or {}
        if isinstance(engine, Mapping):
            defaults = engine.get("defaults", {})
            if isinstance(defaults, Mapping):
                try:
                    return EngineDefaults.model_validate(defaults)
                except Exception:  # pragma: no cover - validation fallback
                    pass
        return EngineDefaults()

    @property
    def writer(self) -> EngineWriter:
        if self.model is not None:
            return self.model.engine.writer
        engine = self.raw.get("engine") or {}
        if isinstance(engine, Mapping):
            writer = engine.get("writer", {})
            if isinstance(writer, Mapping):
                try:
                    return EngineWriter.model_validate(writer)
                except Exception:  # pragma: no cover - validation fallback
                    pass
        return EngineWriter()

    # Compatibility helpers to ease migration away from dict-based accessors.
    @property
    def column_meta(self) -> dict[str, dict[str, object]]:
        if self.model is not None:
            return {
                field: meta.model_dump()
                for field, meta in self.model.columns.meta.items()
            }
        columns = self.raw.get("columns") or {}
        if isinstance(columns, Mapping):
            meta = columns.get("meta", {})
            if isinstance(meta, Mapping):
                return {
                    str(field): dict(value) if isinstance(value, Mapping) else {}
                    for field, value in meta.items()
                }
        return {}

    @property
    def column_models(self) -> dict[str, ColumnMeta]:
        return self.column_meta_models


__all__ = [
    "ColumnMeta",
    "ColumnSection",
    "EngineDefaults",
    "EngineSection",
    "EngineWriter",
    "HookCollection",
    "ManifestContext",
    "ManifestInfo",
    "ManifestV1",
    "ScriptRef",
]
```

# apps/ade-engine/src/ade_engine/core/models.py
```python
"""Core engine data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .phases import JobStatus

if TYPE_CHECKING:
    from .manifest import ManifestContext, ManifestV1


@dataclass(frozen=True, slots=True)
class EngineMetadata:
    """Describes the installed ade_engine distribution."""

    name: str = "ade-engine"
    version: str = "0.0.0"
    description: str | None = None


@dataclass(frozen=True, slots=True)
class JobPaths:
    """Resolved paths for a job's working directory structure."""

    jobs_root: Path
    job_dir: Path
    input_dir: Path
    output_dir: Path
    logs_dir: Path
    artifact_path: Path
    events_path: Path


@dataclass(slots=True)
class JobContext:
    """Mutable context shared across the runtime."""

    job_id: str
    manifest: "ManifestContext | dict[str, Any]"
    paths: JobPaths
    started_at: datetime
    manifest_model: "ManifestV1 | None" = None
    safe_mode: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JobResult:
    """Outcome returned by the engine interface."""

    job_id: str
    status: JobStatus
    artifact_path: Path
    events_path: Path
    output_paths: tuple[Path, ...]
    processed_files: tuple[str, ...] = ()
    error: str | None = None


__all__ = ["EngineMetadata", "JobContext", "JobPaths", "JobResult"]
```

# apps/ade-engine/src/ade_engine/core/phases.py
```python
"""Shared pipeline/job phase markers."""

from __future__ import annotations

from enum import Enum
from typing import Literal

JobStatus = Literal["succeeded", "failed"]


class PipelinePhase(str, Enum):
    """Recognized pipeline phases."""

    INITIALIZED = "initialized"
    EXTRACTING = "extracting"
    BEFORE_SAVE = "before_save"
    WRITING_OUTPUT = "writing_output"
    COMPLETED = "completed"
    FAILED = "failed"


__all__ = ["JobStatus", "PipelinePhase"]
```

# apps/ade-engine/src/ade_engine/core/pipeline_types.py
```python
"""Dataclasses shared across pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Mapping, Sequence

from .manifest import ColumnMeta


@dataclass(slots=True)
class ScoreContribution:
    """Record how a detector influenced a field's final score."""

    field: str
    detector: str
    delta: float


@dataclass(slots=True)
class ColumnMapping:
    """Link a manifest field to a concrete input column."""

    field: str
    header: str
    index: int
    score: float
    contributions: tuple[ScoreContribution, ...]


@dataclass(slots=True)
class ExtraColumn:
    """Preserve unmapped columns in the normalized output."""

    header: str
    index: int
    output_header: str


@dataclass(slots=True)
class FileExtraction:
    """Normalized table data pulled from a single input file."""

    source_name: str
    sheet_name: str
    mapped_columns: list[ColumnMapping]
    extra_columns: list[ExtraColumn]
    rows: list[list[Any]]
    header_row: list[str]
    validation_issues: list[dict[str, Any]]


@dataclass(slots=True)
class ColumnModule:
    """Manifest-backed module that contributes detectors/transforms/validators."""

    field: str
    meta: Mapping[str, Any]
    definition: ColumnMeta
    module: ModuleType
    detectors: tuple[Callable[..., Mapping[str, Any]], ...]
    transformer: Callable[..., Mapping[str, Any] | None] | None
    validator: Callable[..., Sequence[Mapping[str, Any]]] | None


@dataclass(slots=True)
class TableProcessingResult:
    """Normalized view of a single table after mapping and validation."""

    mapping: list[ColumnMapping]
    extras: list[ExtraColumn]
    rows: list[list[Any]]
    issues: list[dict[str, Any]]


__all__ = [
    "ColumnMapping",
    "ColumnModule",
    "ExtraColumn",
    "FileExtraction",
    "ScoreContribution",
    "TableProcessingResult",
]
```

# apps/ade-engine/src/ade_engine/entrypoint.py
```python
"""Console entrypoint for ``python -m ade_engine``."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from ade_engine import (
    DEFAULT_METADATA,
    ManifestNotFoundError,
    TelemetryConfig,
    load_config_manifest,
    run_job,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ade_engine",
        description="ADE engine module entrypoint.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the ade_engine version and exit.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        help="Optional path to an ade_config manifest (defaults to the installed package resource).",
    )
    parser.add_argument(
        "--job-id",
        type=str,
        help="Run the worker pipeline for the specified job.",
    )
    parser.add_argument(
        "--jobs-dir",
        type=Path,
        help="Root directory containing per-job folders (defaults to ADE_JOBS_DIR/ADE_DATA_DIR).",
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Run without sandboxing (used by integration tests).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 when the module entrypoint completes successfully."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.version and not args.job_id:
        print(f"{DEFAULT_METADATA.name} {DEFAULT_METADATA.version}")
        return 0

    if args.job_id:
        telemetry = TelemetryConfig(
            correlation_id=os.environ.get("ADE_TELEMETRY_CORRELATION_ID")
        )
        result = run_job(
            args.job_id,
            jobs_dir=args.jobs_dir,
            manifest_path=args.manifest_path,
            safe_mode=args.safe_mode,
            telemetry=telemetry,
        )
        payload = {
            "engine_version": DEFAULT_METADATA.version,
            "job": {
                "job_id": result.job_id,
                "status": result.status,
                "outputs": [str(path) for path in result.output_paths],
                "artifact": str(result.artifact_path),
                "events": str(result.events_path),
            },
        }
        if result.error:
            payload["job"]["error"] = result.error
        print(json.dumps(payload, indent=2))
        return 0 if result.status == "succeeded" else 1

    try:
        manifest = load_config_manifest(manifest_path=args.manifest_path)
    except ManifestNotFoundError as exc:
        print(f"Manifest error: {exc}")
        return 1
    print(
        json.dumps(
            {
                "engine_version": DEFAULT_METADATA.version,
                "config_manifest": manifest,
            },
            indent=2,
        )
    )
    return 0


def console_entrypoint() -> NoReturn:
    """Console script helper for the module entrypoint."""

    raise SystemExit(main())
```

# apps/ade-engine/src/ade_engine/hooks/__init__.py
```python
"""Hook loading and execution helpers."""

from .registry import (
    HookContext,
    HookExecutionError,
    HookLoadError,
    HookRegistry,
    HookStage,
)

__all__ = [
    "HookContext",
    "HookExecutionError",
    "HookLoadError",
    "HookRegistry",
    "HookStage",
]
```

# apps/ade-engine/src/ade_engine/hooks/registry.py
```python
"""Typed hook registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from importlib import import_module
from typing import Any, Callable, Iterable, Mapping
import inspect

from ade_engine.core.manifest import HookCollection, ManifestContext, ScriptRef
from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import FileExtraction
from ade_engine.plugins.utils import _script_to_module
from ade_engine.sinks import ArtifactSink, EventSink


class HookLoadError(RuntimeError):
    """Raised when hooks cannot be imported from ``ade_config``."""


class HookExecutionError(RuntimeError):
    """Raised when a hook fails while the job is running."""


class HookStage(str, Enum):
    ON_ACTIVATE = "on_activate"
    ON_JOB_START = "on_job_start"
    ON_AFTER_EXTRACT = "on_after_extract"
    ON_BEFORE_SAVE = "on_before_save"
    ON_JOB_END = "on_job_end"


@dataclass(slots=True)
class HookContext:
    job: JobContext
    artifact: ArtifactSink
    events: EventSink | None = None
    tables: list[FileExtraction] | None = None
    result: Any | None = None


class HookRegistry:
    """Resolve and execute hooks declared in the manifest."""

    def __init__(self, manifest: ManifestContext, *, package: str) -> None:
        self._hooks: dict[HookStage, tuple[tuple[str, str], ...]] = {}
        entries = self._load_entries(manifest)
        for stage, refs in entries.items():
            funcs: list[tuple[str, str]] = []
            for ref in refs:
                script = ref.script if isinstance(ref, ScriptRef) else ref.get("script")
                enabled = ref.enabled if isinstance(ref, ScriptRef) else ref.get("enabled", True)
                if not enabled or not script:
                    continue
                module_name = _script_to_module(script, package=package)
                try:
                    module = import_module(module_name)
                except ModuleNotFoundError as exc:  # pragma: no cover - import guard
                    raise HookLoadError(
                        f"Hook module '{module_name}' could not be imported"
                    ) from exc

                func_name = "run" if hasattr(module, "run") else "main" if hasattr(module, "main") else None
                if func_name is None:
                    raise HookLoadError(
                        f"Hook module '{module_name}' must expose a 'run' or 'main' callable"
                    )
                funcs.append((module_name, func_name))
            if funcs:
                self._hooks[stage] = tuple(funcs)

    def _load_entries(
        self, manifest: ManifestContext
    ) -> Mapping[HookStage, Iterable[ScriptRef | Mapping[str, Any]]]:
        if manifest.model is not None and isinstance(manifest.model.hooks, HookCollection):
            hooks = manifest.model.hooks
            return {
                HookStage.ON_ACTIVATE: hooks.on_activate,
                HookStage.ON_JOB_START: hooks.on_job_start,
                HookStage.ON_AFTER_EXTRACT: hooks.on_after_extract,
                HookStage.ON_BEFORE_SAVE: hooks.on_before_save,
                HookStage.ON_JOB_END: hooks.on_job_end,
            }

        hooks_raw = (manifest.raw.get("hooks") if isinstance(manifest.raw, Mapping) else {}) or {}
        results: dict[HookStage, Iterable[Mapping[str, Any]]] = {}
        for stage in HookStage:
            entries = hooks_raw.get(stage.value)
            if isinstance(entries, list):
                results[stage] = entries
        return results

    def call(self, stage: HookStage, ctx: HookContext) -> None:
        functions = self._hooks.get(stage)
        if not functions:
            return
        for module_name, func_name in functions:
            try:
                module = import_module(module_name)
                func = getattr(module, func_name)
                self._invoke(func, ctx)
            except Exception as exc:  # pragma: no cover - hook failure path
                raise HookExecutionError(
                    f"Hook '{func.__module__}.{func.__name__}' failed during {stage.value}: {exc}"
                ) from exc

    def _invoke(self, func: Callable[..., Any], ctx: HookContext) -> None:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        if len(params) == 1 and params[0].kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            result = func(ctx)
        else:
            result = func(
            job=ctx.job,
            artifact=ctx.artifact,
            events=ctx.events,
            tables=ctx.tables,
            result=ctx.result,
        )
        if inspect.isgenerator(result):  # ensure generator-based hooks execute
            for _ in result:
                break


__all__ = ["HookContext", "HookExecutionError", "HookLoadError", "HookRegistry", "HookStage"]
```

# apps/ade-engine/src/ade_engine/job_service.py
```python
"""Service object that encapsulates ADE job preparation and finalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ade_engine.config.loader import load_manifest, resolve_input_sheets
from ade_engine.core.phases import PipelinePhase
from ade_engine.schemas import ManifestContext

from ade_engine.hooks import HookContext, HookRegistry, HookStage
from ade_engine.core.models import JobContext, JobPaths, JobResult
from ade_engine.telemetry.logging import PipelineLogger
from ade_engine.telemetry.sinks import SinkProvider, _now
from ade_engine.telemetry.types import TelemetryBindings, TelemetryConfig
from .pipeline.registry import ColumnRegistry
from .pipeline.runner import PipelineRunner
from .pipeline.stages import ExtractStage, WriteStage


@dataclass(slots=True)
class PreparedJob:
    """Runtime assets required to execute an ADE job."""

    job: JobContext
    manifest: ManifestContext
    hooks: HookRegistry
    logger: PipelineLogger
    pipeline: PipelineRunner
    telemetry: TelemetryBindings
    registry: ColumnRegistry


class JobService:
    """Coordinate job setup and teardown concerns for the worker."""

    def __init__(
        self,
        *,
        config_package: str = "ade_config",
        telemetry: TelemetryConfig | None = None,
    ) -> None:
        self._config_package = config_package
        self._telemetry_config = telemetry or TelemetryConfig()

    def prepare_job(
        self,
        job_id: str,
        *,
        jobs_root: Path,
        manifest_path: Path | None = None,
        safe_mode: bool = False,
        sink_provider: SinkProvider | None = None,
    ) -> PreparedJob:
        """Resolve runtime dependencies and return a prepared job bundle."""

        paths = _build_job_paths(jobs_root, job_id)
        manifest_ctx = load_manifest(
            package=self._config_package, manifest_path=manifest_path
        )
        metadata: dict[str, Any] = {}
        if self._telemetry_config.correlation_id:
            metadata["run_id"] = self._telemetry_config.correlation_id
        sheet_list = resolve_input_sheets()
        if sheet_list:
            metadata["input_sheet_names"] = sheet_list
            if len(sheet_list) == 1:
                metadata["input_sheet_name"] = sheet_list[0]
        job = JobContext(
            job_id=job_id,
            manifest=manifest_ctx.raw,
            manifest_model=manifest_ctx.model,
            paths=paths,
            started_at=_now(),
            safe_mode=safe_mode,
            metadata=metadata,
        )
        telemetry = self._telemetry_config.bind(
            job,
            paths,
            provider=sink_provider,
        )
        hooks = HookRegistry(manifest_ctx, package=self._config_package)
        logger = PipelineLogger(job, telemetry)
        pipeline = PipelineRunner(job, logger)
        telemetry.artifact.start(job=job, manifest=manifest_ctx.raw)
        logger.event("job_started", level="info")

        registry = ColumnRegistry(
            manifest_ctx.column_models,
            package=self._config_package,
        )

        return PreparedJob(
            job=job,
            manifest=manifest_ctx,
            hooks=hooks,
            logger=logger,
            pipeline=pipeline,
            telemetry=telemetry,
            registry=registry,
        )

    def run(self, prepared: PreparedJob) -> JobResult:
        """Execute a prepared job and return its result."""

        job = prepared.job
        artifact = prepared.telemetry.artifact
        events = prepared.telemetry.events
        hooks = prepared.hooks
        logger = prepared.logger
        pipeline = prepared.pipeline
        manifest_ctx = prepared.manifest

        try:
            hooks.call(
                HookStage.ON_JOB_START,
                HookContext(job=job, artifact=artifact, events=events),
            )

            registry = prepared.registry
            writer_cfg = manifest_ctx.writer
            defaults = manifest_ctx.defaults
            append_unmapped = bool(writer_cfg.append_unmapped_columns)
            prefix = str(writer_cfg.unmapped_prefix)
            sample_size = int(defaults.detector_sample_size or 64)
            threshold = float(defaults.mapping_score_threshold or 0.0)

            extract_stage = ExtractStage(
                manifest=manifest_ctx,
                modules=registry.modules(),
                threshold=threshold,
                sample_size=sample_size,
                append_unmapped=append_unmapped,
                unmapped_prefix=prefix,
            )
            write_stage = WriteStage(manifest=manifest_ctx)

            def _run_extract(job_ctx: Any, _: Any, log: PipelineLogger) -> list:
                tables = extract_stage.run(job_ctx, None, log)
                hooks.call(
                    HookStage.ON_AFTER_EXTRACT,
                    HookContext(job=job_ctx, artifact=artifact, events=events, tables=tables),
                )
                return tables

            def _run_write(job_ctx: Any, tables: Any, log: PipelineLogger) -> Path:
                hooks.call(
                    HookStage.ON_BEFORE_SAVE,
                    HookContext(job=job_ctx, artifact=artifact, events=events, tables=list(tables)),
                )
                return write_stage.run(job_ctx, list(tables), log)

            pipeline.run(extract_stage=_run_extract, write_stage=_run_write)
            result = self.finalize_success(prepared, None)
            hooks.call(
                HookStage.ON_JOB_END,
                HookContext(
                    job=job,
                    artifact=artifact,
                    events=events,
                    tables=pipeline.tables,
                    result=result,
                ),
            )
            artifact.flush()
            return result
        except Exception as exc:  # pragma: no cover - exercised via integration
            if pipeline.phase is not PipelinePhase.FAILED:
                pipeline.phase = PipelinePhase.FAILED
            result = self.finalize_failure(prepared, exc)
            try:
                hooks.call(
                    HookStage.ON_JOB_END,
                    HookContext(
                        job=job,
                        artifact=artifact,
                        events=events,
                        tables=pipeline.tables,
                        result=result,
                    ),
                )
            finally:
                artifact.flush()
            return result

    def finalize_success(
        self, prepared: PreparedJob, result: JobResult | None = None
    ) -> JobResult:
        """Mark job success, flush sinks, and build the job result."""

        completed_at = _now()
        prepared.telemetry.artifact.mark_success(
            completed_at=completed_at,
            outputs=prepared.pipeline.output_paths,
        )
        prepared.telemetry.artifact.flush()
        result = result or _build_result_from_pipeline(prepared.pipeline)
        prepared.logger.event("job_completed", status="succeeded")
        return result

    def finalize_failure(self, prepared: PreparedJob, error: Exception) -> JobResult:
        """Mark job failure, flush sinks, and return an error result."""

        completed_at = _now()
        if prepared.pipeline.phase is not PipelinePhase.FAILED:
            prepared.pipeline.phase = PipelinePhase.FAILED
            prepared.logger.transition(PipelinePhase.FAILED.value, error=str(error))
        prepared.telemetry.artifact.mark_failure(
            completed_at=completed_at,
            error=error,
        )
        prepared.logger.note(
            "Job failed",
            level="error",
            error=str(error),
        )
        prepared.telemetry.artifact.flush()
        prepared.logger.event("job_failed", level="error", error=str(error))
        return _build_result_from_pipeline(prepared.pipeline, error=str(error))


def _build_job_paths(jobs_root: Path, job_id: str) -> JobPaths:
    job_dir = jobs_root / job_id
    input_dir = job_dir / "input"
    output_dir = job_dir / "output"
    logs_dir = job_dir / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    return JobPaths(
        jobs_root=jobs_root,
        job_dir=job_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        logs_dir=logs_dir,
        artifact_path=logs_dir / "artifact.json",
        events_path=logs_dir / "events.ndjson",
    )


def _build_result_from_pipeline(pipeline: PipelineRunner, error: str | None = None) -> JobResult:
    status = "failed" if error or pipeline.phase is PipelinePhase.FAILED else "succeeded"
    processed = tuple(getattr(table, "source_name", "") for table in pipeline.tables)
    return JobResult(
        job_id=pipeline.job.job_id,
        status=status,
        artifact_path=pipeline.job.paths.artifact_path,
        events_path=pipeline.job.paths.events_path,
        output_paths=pipeline.output_paths,
        processed_files=processed,
        error=error,
    )


__all__ = ["JobService", "PreparedJob"]
```

# apps/ade-engine/src/ade_engine/logging.py
```python
"""Compatibility shim for legacy StructuredLogger imports."""

from ade_engine.telemetry.logging import PipelineLogger

StructuredLogger = PipelineLogger

__all__ = ["PipelineLogger", "StructuredLogger"]
```

# apps/ade-engine/src/ade_engine/pipeline/__init__.py
```python
"""Pipeline stage helpers for the ADE engine."""

from .extract import extract_inputs
from .io import list_input_files, read_table, sheet_name
from .mapping import (
    build_unmapped_header,
    column_sample,
    map_columns,
    match_header,
    normalize_header,
)
from .models import ColumnMapping, ColumnModule, ExtraColumn, FileExtraction, ScoreContribution
from .normalize import normalize_rows
from .processing import TableProcessingResult, process_table
from .output import output_headers, write_outputs
from .runner import PipelineRunner
from .registry import ColumnRegistry, ColumnRegistryError
from .stages import ExtractStage, WriteStage
from .util import unique_sheet_name

__all__ = [
    "ColumnMapping",
    "ColumnModule",
    "ColumnRegistry",
    "ColumnRegistryError",
    "ExtraColumn",
    "FileExtraction",
    "ScoreContribution",
    "TableProcessingResult",
    "build_unmapped_header",
    "column_sample",
    "extract_inputs",
    "list_input_files",
    "map_columns",
    "match_header",
    "normalize_header",
    "normalize_rows",
    "unique_sheet_name",
    "process_table",
    "PipelineRunner",
    "output_headers",
    "read_table",
    "ExtractStage",
    "WriteStage",
    "sheet_name",
    "write_outputs",
]
```

# apps/ade-engine/src/ade_engine/pipeline/extract.py
```python
"""Extract and normalize inputs into structured tables."""

from __future__ import annotations

from typing import Any, Mapping

from ade_engine.core.manifest import ManifestContext
from ade_engine.core.models import JobContext
from ade_engine.logging import StructuredLogger  # compatibility; prefer PipelineLogger
from ade_engine.telemetry.logging import PipelineLogger
from .io import iter_tables, list_input_files, sheet_name
from .models import ColumnModule, FileExtraction
from .processing import process_table
from .util import unique_sheet_name


def extract_inputs(
    job: JobContext,
    manifest: ManifestContext,
    modules: Mapping[str, ColumnModule],
    logger: StructuredLogger | PipelineLogger,
    *,
    threshold: float,
    sample_size: int,
    append_unmapped: bool,
    unmapped_prefix: str,
    state: dict[str, Any],
) -> list[FileExtraction]:
    """Process job input files and return normalized table extractions."""

    input_files = list_input_files(job.paths.input_dir)
    if not input_files:
        raise RuntimeError("No input files found for job")

    order = manifest.column_order
    meta = manifest.column_meta
    definitions = manifest.column_models

    runtime_logger = logger.runtime_logger
    results: list[FileExtraction] = []
    used_sheet_names: set[str] = set()
    raw_sheet_names = job.metadata.get("input_sheet_names") if job.metadata else None
    sheet_list: list[str] | None = None
    if isinstance(raw_sheet_names, list):
        cleaned = [str(value).strip() for value in raw_sheet_names if str(value).strip()]
        sheet_list = cleaned or None
    elif raw_sheet_names:
        sheet_list = [str(raw_sheet_names).strip()]
    elif job.metadata and job.metadata.get("input_sheet_name"):
        sheet_list = [str(job.metadata["input_sheet_name"]).strip()]

    for file_path in input_files:
        targets = sheet_list if file_path.suffix.lower() == ".xlsx" else None
        for source_sheet, header_row, data_rows in iter_tables(
            file_path, sheet_names=targets
        ):
            table_info = {
                "headers": header_row,
                "row_count": len(data_rows),
                "column_count": len(header_row),
                "source_name": file_path.name,
                "sheet_name": source_sheet,
            }
            state.setdefault("tables", []).append(table_info)

            table_result = process_table(
                job=job,
                header_row=header_row,
                data_rows=data_rows,
                order=order,
                meta=meta,
                definitions=definitions,
                modules=modules,
                threshold=threshold,
                sample_size=sample_size,
                append_unmapped=append_unmapped,
                unmapped_prefix=unmapped_prefix,
                table_info=table_info,
                state=state,
                logger=runtime_logger,
            )

            normalized_sheet = (
                sheet_name(f"{file_path.stem}-{source_sheet}")
                if source_sheet
                else sheet_name(file_path.stem)
            )
            normalized_sheet = unique_sheet_name(normalized_sheet, used_sheet_names)
            extraction = FileExtraction(
                source_name=file_path.name,
                sheet_name=normalized_sheet,
                mapped_columns=list(table_result.mapping),
                extra_columns=list(table_result.extras),
                rows=table_result.rows,
                header_row=header_row,
                validation_issues=table_result.issues,
            )

            logger.record_table(
                {
                    "input_file": file_path.name,
                    "sheet": normalized_sheet,
                    "header": {"row_index": 1, "source": header_row},
                    "mapping": [
                        {
                            "field": entry.field,
                            "header": entry.header,
                            "source_column_index": entry.index,
                            "score": entry.score,
                            "contributions": [
                                {
                                    "field": contrib.field,
                                    "detector": contrib.detector,
                                    "delta": contrib.delta,
                                }
                                for contrib in entry.contributions
                            ],
                        }
                        for entry in table_result.mapping
                    ],
                    "unmapped": [
                        {
                            "header": extra.header,
                            "source_column_index": extra.index,
                            "output_header": extra.output_header,
                        }
                        for extra in table_result.extras
                    ],
                    "validation": table_result.issues,
                }
            )
            logger.note(
                f"Processed input file {file_path.name}",
                mapped_fields=[entry.field for entry in table_result.mapping],
            )
            logger.flush()
            logger.event(
                "file_processed",
                file=file_path.name,
                mapped_fields=[entry.field for entry in table_result.mapping],
                validation_issue_count=len(table_result.issues),
            )
            for issue in table_result.issues:
                logger.event(
                    "validation_issue",
                    level="warning",
                    file=file_path.name,
                    row_index=issue.get("row_index"),
                    field=issue.get("field"),
                    code=issue.get("code"),
                )

            results.append(extraction)

    return results


__all__ = ["extract_inputs"]
```

# apps/ade-engine/src/ade_engine/pipeline/io.py
```python
"""Input discovery and ingestion helpers."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Iterable, Iterator

import openpyxl


def list_input_files(input_dir: Path) -> list[Path]:
    """Return sorted job input files limited to CSV/XLSX types."""

    if not input_dir.exists():
        return []
    candidates = [
        path
        for path in sorted(input_dir.iterdir())
        if path.suffix.lower() in {".csv", ".xlsx"}
    ]
    return [path for path in candidates if path.is_file()]


def read_table(
    path: Path,
    *,
    sheet_name: str | None = None,
) -> tuple[list[str], list[list[Any]]]:
    """Read a CSV or XLSX file returning the header row and data rows."""

    tables = list(iter_tables(path, sheet_names=[sheet_name] if sheet_name else None))
    if not tables:
        raise RuntimeError(f"Input file '{path.name}' is empty")
    _, header, rows = tables[0]
    return header, rows


def iter_tables(
    path: Path,
    *,
    sheet_names: Iterable[str] | None = None,
) -> Iterator[tuple[str | None, list[str], list[list[Any]]]]:
    """Yield (sheet name, header, rows) tuples for each worksheet in the input."""

    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration:
                return
            data_rows = [list(row) for row in reader]
        yield None, [str(value) if value is not None else "" for value in header], data_rows
        return

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        targets = list(sheet_names) if sheet_names else list(workbook.sheetnames)
        missing = [name for name in targets if name not in workbook.sheetnames]
        if missing:
            raise RuntimeError(
                f"Worksheet '{missing[0]}' not found in {path.name}"
            )

        for name in targets:
            sheet = workbook[name]
            iterator = sheet.iter_rows(values_only=True)
            try:
                header = next(iterator)
            except StopIteration:
                raise RuntimeError(f"Input sheet '{name}' in '{path.name}' is empty")
            header_row = [str(value) if value is not None else "" for value in header]
            data_rows = [
                [cell if cell is not None else "" for cell in row] for row in iterator
            ]
            yield name, header_row, data_rows
    finally:
        workbook.close()


def sheet_name(stem: str) -> str:
    """Normalize worksheet names to Excel-safe identifiers."""

    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", stem).strip()
    cleaned = cleaned or "Sheet"
    return cleaned[:31]


__all__ = ["iter_tables", "list_input_files", "read_table", "sheet_name"]
```

# apps/ade-engine/src/ade_engine/pipeline/mapping.py
```python
"""Column mapping utilities."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any, Mapping, Sequence

from ade_engine.core.manifest import ColumnMeta
from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import (
    ColumnMapping,
    ColumnModule,
    ExtraColumn,
    ScoreContribution,
)


def map_columns(
    job: JobContext,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    order: Sequence[str],
    meta: Mapping[str, Mapping[str, Any]],
    definitions: Mapping[str, ColumnMeta],
    modules: Mapping[str, ColumnModule],
    *,
    threshold: float,
    sample_size: int,
    append_unmapped: bool,
    prefix: str,
    table_info: Mapping[str, Any],
    state: Mapping[str, Any],
    logger: logging.Logger,
) -> tuple[list[ColumnMapping], list[ExtraColumn]]:
    """Score each input column and assign the best manifest field mapping."""

    mapping: list[ColumnMapping] = []
    extras: list[ExtraColumn] = []
    used_fields: set[str] = set()
    order_index = {field: idx for idx, field in enumerate(order)}

    normalized_headers = [normalize_header(value) for value in headers]
    column_values = [
        [row[idx] if idx < len(row) else None for row in rows]
        for idx in range(len(headers))
    ]

    table = dict(table_info)

    for idx, header in enumerate(headers):
        scores: dict[str, float] = defaultdict(float)
        contributions: list[ScoreContribution] = []
        normalized_header = normalized_headers[idx]
        values = column_values[idx]
        sample = column_sample(values, sample_size)
        column_tuple = tuple(values)

        for module in modules.values():
            for detector in module.detectors:
                try:
                    result = detector(
                        job=job,
                        state=state,
                        field_name=module.field,
                        field_meta=module.meta,
                        header=normalized_header,
                        column_values_sample=sample,
                        column_values=column_tuple,
                        table=table,
                        column_index=idx + 1,
                        logger=logger,
                    )
                except Exception as exc:  # pragma: no cover - detector failure
                    raise RuntimeError(
                        f"Detector '{detector.__module__}.{detector.__name__}' failed: {exc}"
                    ) from exc
                score_map = (result or {}).get("scores", {})
                for field, delta in score_map.items():
                    if field not in order_index:
                        continue
                    try:
                        delta_value = float(delta)
                    except (TypeError, ValueError):
                        continue
                    scores[field] = scores.get(field, 0.0) + delta_value
                    contributions.append(
                        ScoreContribution(
                            field=field,
                            detector=f"{detector.__module__}.{detector.__name__}",
                            delta=delta_value,
                        )
                    )

        chosen_field = None
        chosen_score = float("-inf")
        for field in order:
            if field in used_fields:
                continue
            score = scores.get(field)
            if score is None:
                continue
            if score < threshold:
                continue
            if score > chosen_score:
                chosen_field = field
                chosen_score = score
            elif score == chosen_score and chosen_field is not None:
                if order_index[field] < order_index[chosen_field]:
                    chosen_field = field
                    chosen_score = score

        if chosen_field is None and definitions:
            fallback = match_header(order, definitions, normalized_header, used_fields)
            if fallback is not None:
                chosen_field = fallback
                chosen_score = threshold

        if chosen_field:
            used_fields.add(chosen_field)
            selected = tuple(
                contrib for contrib in contributions if contrib.field == chosen_field
            )
            mapping.append(
                ColumnMapping(
                    field=chosen_field,
                    header=headers[idx],
                    index=idx,
                    score=chosen_score,
                    contributions=selected,
                )
            )
        elif append_unmapped:
            extras.append(
                ExtraColumn(
                    header=headers[idx],
                    index=idx,
                    output_header=build_unmapped_header(prefix, headers[idx], idx),
                )
            )

    return mapping, extras


def column_sample(values: Sequence[Any], size: int) -> list[Any]:
    """Return a spaced sample of ``values`` capped at ``size`` entries."""

    if size <= 0 or not values:
        return []
    if len(values) <= size:
        return list(values)
    count = max(1, size)
    step = len(values) / count
    sample: list[Any] = []
    index = 0.0
    while len(sample) < count:
        idx = int(index)
        if idx >= len(values):
            idx = len(values) - 1
        sample.append(values[idx])
        index += step
    if sample and sample[-1] != values[-1]:
        sample[-1] = values[-1]
    return sample


def build_unmapped_header(prefix: str, header: str, index: int) -> str:
    """Generate a sanitized header for unmapped columns."""

    cleaned = (
        re.sub(r"[^A-Za-z0-9]+", "_", header).strip("_").lower()
        or f"column_{index + 1}"
    )
    return f"{prefix}{cleaned}"[:31]


def normalize_header(value: str | None) -> str:
    """Normalize headers for comparison."""

    return (value or "").strip().lower()


def match_header(
    order: Sequence[str],
    meta: Mapping[str, ColumnMeta],
    normalized_header: str,
    used_fields: set[str],
) -> str | None:
    """Find a manifest field whose label/synonyms match the header."""

    candidate = normalized_header.strip()
    if not candidate:
        return None
    for field in order:
        if field in used_fields:
            continue
        info = meta.get(field)
        if info is None or not info.enabled:
            continue
        label = normalize_header(info.label or field)
        synonyms = [normalize_header(value) for value in info.synonyms]
        if candidate in {label, *synonyms}:
            return field
    return None


__all__ = [
    "build_unmapped_header",
    "column_sample",
    "map_columns",
    "match_header",
    "normalize_header",
]
```

# apps/ade-engine/src/ade_engine/pipeline/models.py
```python
"""Compatibility re-exports for pipeline dataclasses."""

from ade_engine.core.pipeline_types import (
    ColumnMapping,
    ColumnModule,
    ExtraColumn,
    FileExtraction,
    ScoreContribution,
)

__all__ = [
    "ColumnMapping",
    "ColumnModule",
    "ExtraColumn",
    "FileExtraction",
    "ScoreContribution",
]
```

# apps/ade-engine/src/ade_engine/pipeline/normalize.py
```python
"""Row normalization and validation."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import ColumnMapping, ColumnModule, ExtraColumn


def normalize_rows(
    job: JobContext,
    rows: Sequence[Sequence[Any]],
    order: Sequence[str],
    mapping: Sequence[ColumnMapping],
    extras: Sequence[ExtraColumn],
    modules: Mapping[str, ColumnModule],
    meta: Mapping[str, Mapping[str, Any]],
    *,
    state: Mapping[str, Any],
    logger: logging.Logger,
) -> tuple[list[list[Any]], list[dict[str, Any]]]:
    """Apply transforms and validators to produce normalized rows."""

    index_by_field = {entry.field: entry.index for entry in mapping}
    normalized: list[list[Any]] = []
    issues: list[dict[str, Any]] = []
    active_modules = {field: module for field, module in modules.items() if field in order}

    for zero_index, row in enumerate(rows):
        row_index = zero_index + 2  # header row is index 1
        canonical_row: dict[str, Any] = {}
        for field in order:
            idx = index_by_field.get(field)
            value = row[idx] if idx is not None and idx < len(row) else None
            canonical_row[field] = value

        for field in order:
            module = active_modules.get(field)
            if module is None or module.transformer is None:
                continue
            value = canonical_row.get(field)
            try:
                updates = module.transformer(
                    job=job,
                    state=state,
                    row_index=row_index,
                    field_name=field,
                    value=value,
                    row=canonical_row,
                    field_meta=meta.get(field),
                    logger=logger,
                )
            except Exception as exc:  # pragma: no cover - transform failure
                raise RuntimeError(
                    f"Transform for field '{field}' failed on row {row_index}: {exc}"
                ) from exc
            if updates:
                canonical_row.update(dict(updates))

        for field in order:
            module = active_modules.get(field)
            if module is None or module.validator is None:
                continue
            value = canonical_row.get(field)
            field_meta = meta.get(field)
            try:
                results = module.validator(
                    job=job,
                    state=state,
                    row_index=row_index,
                    field_name=field,
                    value=value,
                    row=canonical_row,
                    field_meta=field_meta,
                    logger=logger,
                )
            except Exception as exc:  # pragma: no cover - validation failure
                raise RuntimeError(
                    f"Validator for field '{field}' failed on row {row_index}: {exc}"
                ) from exc
            for issue in results or []:
                payload = dict(issue)
                payload.setdefault("row_index", row_index)
                payload.setdefault("field", field)
                issues.append(payload)

        normalized_row = [canonical_row.get(field) for field in order]
        for extra in extras:
            value = row[extra.index] if extra.index < len(row) else None
            normalized_row.append(value)
        normalized.append(normalized_row)

    return normalized, issues


__all__ = ["normalize_rows"]
```

# apps/ade-engine/src/ade_engine/pipeline/output.py
```python
"""Output composition helpers."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from ade_engine.core.manifest import ManifestContext
from ade_engine.core.models import JobContext
from .models import FileExtraction
from .util import unique_sheet_name


def _combined_headers(manifest: ManifestContext, extractions: list[FileExtraction]) -> list[str]:
    """Build a shared header row for combined outputs."""

    order = manifest.column_order
    meta = manifest.column_meta
    headers = [meta.get(field, {}).get("label", field) for field in order]
    extras: list[str] = []
    seen: set[str] = set()
    for extraction in extractions:
        for extra in extraction.extra_columns:
            if extra.output_header not in seen:
                seen.add(extra.output_header)
                extras.append(extra.output_header)
    headers.extend(extras)
    return headers


def _append_rows(sheet, headers: list[str], order_len: int, extraction: FileExtraction) -> None:
    """Append rows to a sheet using a unified header layout."""

    header_to_index = {name: idx for idx, name in enumerate(headers)}
    for row in extraction.rows:
        base = row[:order_len]
        extras_values = row[order_len:]
        extra_map = {
            extra.output_header: extras_values[idx]
            for idx, extra in enumerate(extraction.extra_columns)
            if idx < len(extras_values)
        }
        padded = list(base)
        extra_start = len(base)
        for name in headers[extra_start:]:
            padded.append(extra_map.get(name, ""))
        sheet.append(padded)


def write_outputs(
    job: JobContext,
    manifest: ManifestContext,
    extractions: list[FileExtraction],
) -> Path:
    """Persist normalized rows into an Excel workbook honoring writer settings."""

    writer_cfg = manifest.writer
    raw_writer = (
        manifest.raw.get("engine", {}).get("writer", {})
        if isinstance(manifest.raw, dict)
        else {}
    )
    output_sheet = writer_cfg.output_sheet if isinstance(writer_cfg.output_sheet, str) else None
    output_sheet_configured = isinstance(raw_writer, dict) and "output_sheet" in raw_writer
    in_memory = writer_cfg.mode == "in_memory"

    output_path = job.paths.output_dir / "normalized.xlsx"
    used_sheet_names: set[str] = set()

    tables_payload = []
    if in_memory:
        for extraction in extractions:
            tables_payload.append(
                {
                    "sheet": extraction.sheet_name,
                    "rows": [list(row) for row in extraction.rows],
                    "header": output_headers(manifest, extraction),
                }
            )
        job.metadata["output_tables"] = tables_payload

    workbook = Workbook(write_only=not in_memory)

    try:
        if output_sheet and output_sheet_configured and len(extractions) > 1:
            headers = _combined_headers(manifest, extractions)
            sheet = workbook.create_sheet(title=output_sheet[:31])
            sheet.append(headers)
            for extraction in extractions:
                _append_rows(sheet, headers, len(manifest.column_order), extraction)
        else:
            for extraction in extractions:
                sheet_title = output_sheet if output_sheet_configured and output_sheet else extraction.sheet_name
                sheet_title = unique_sheet_name(sheet_title, used_sheet_names)
                sheet = workbook.create_sheet(title=sheet_title)
                header_cells = output_headers(manifest, extraction)
                sheet.append(header_cells)
                for row in extraction.rows:
                    sheet.append(row)

        tmp_path = output_path.with_suffix(".xlsx.tmp")
        workbook.save(tmp_path)
        tmp_path.replace(output_path)
        return output_path
    finally:
        workbook.close()


def output_headers(manifest: ManifestContext, extraction: FileExtraction) -> list[str]:
    """Build output headers combining manifest labels and unmapped columns."""

    order = manifest.column_order
    meta = manifest.column_meta
    headers = [meta.get(field, {}).get("label", field) for field in order]
    headers.extend(extra.output_header for extra in extraction.extra_columns)
    return headers


__all__ = ["output_headers", "write_outputs"]
```

# apps/ade-engine/src/ade_engine/pipeline/processing.py
```python
"""Pure helpers for transforming raw tables into normalized structures."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from ade_engine.core.manifest import ColumnMeta
from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import (
    ColumnModule,
    ColumnMapping,
    ExtraColumn,
    TableProcessingResult,
)

from .mapping import map_columns
from .normalize import normalize_rows


def process_table(
    *,
    job: JobContext,
    header_row: Sequence[str],
    data_rows: Sequence[Sequence[Any]],
    order: Sequence[str],
    meta: Mapping[str, Mapping[str, Any]],
    definitions: Mapping[str, ColumnMeta],
    modules: Mapping[str, ColumnModule],
    threshold: float,
    sample_size: int,
    append_unmapped: bool,
    unmapped_prefix: str,
    table_info: Mapping[str, Any],
    state: Mapping[str, Any],
    logger: logging.Logger,
) -> TableProcessingResult:
    """Return normalized rows and metadata for an in-memory table."""

    mapping, extras = map_columns(
        job,
        header_row,
        data_rows,
        order,
        meta,
        definitions,
        modules,
        threshold=threshold,
        sample_size=sample_size,
        append_unmapped=append_unmapped,
        prefix=unmapped_prefix,
        table_info=table_info,
        state=state,
        logger=logger,
    )

    normalized_rows, issues = normalize_rows(
        job,
        data_rows,
        order,
        mapping,
        extras,
        modules,
        meta,
        state=state,
        logger=logger,
    )

    return TableProcessingResult(
        mapping=list(mapping),
        extras=list(extras),
        rows=normalized_rows,
        issues=issues,
    )


__all__ = ["TableProcessingResult", "process_table"]
```

# apps/ade-engine/src/ade_engine/pipeline/registry.py
```python
"""Load and validate manifest-declared column modules."""

from __future__ import annotations

import inspect
from importlib import import_module
from typing import Any, Iterable, Mapping

from ade_engine.schemas.manifest import ColumnMeta

from .models import ColumnModule


class ColumnRegistryError(RuntimeError):
    """Raised when column modules cannot be loaded or validated."""


class ColumnRegistry:
    """Load column modules defined in the manifest and validate signatures."""

    _DETECTOR_REQUIRED: tuple[str, ...] = ("field_name",)
    _DETECTOR_ALLOWED: tuple[str, ...] = (
        "job",
        "state",
        "field_name",
        "field_meta",
        "header",
        "column_values_sample",
        "column_values",
        "table",
        "column_index",
        "logger",
    )
    _TRANSFORM_REQUIRED: tuple[str, ...] = ("field_name", "value", "row")
    _TRANSFORM_ALLOWED: tuple[str, ...] = (
        "job",
        "state",
        "row_index",
        "field_name",
        "value",
        "row",
        "field_meta",
        "logger",
    )
    _VALIDATOR_REQUIRED: tuple[str, ...] = ("field_name", "value", "row_index")
    _VALIDATOR_ALLOWED: tuple[str, ...] = (
        "job",
        "state",
        "row_index",
        "field_name",
        "value",
        "row",
        "field_meta",
        "logger",
    )

    def __init__(self, meta: Mapping[str, ColumnMeta], *, package: str) -> None:
        self._modules: dict[str, ColumnModule] = {}
        for field, definition in meta.items():
            if not definition.enabled:
                continue
            script = definition.script
            if not script:
                continue
            module_name = _script_to_module(script, package=package)
            try:
                module = import_module(module_name)
            except ModuleNotFoundError as exc:  # pragma: no cover - import guard
                raise ColumnRegistryError(
                    f"Column module '{module_name}' could not be imported"
                ) from exc

            detectors = tuple(
                getattr(module, attr)
                for attr in dir(module)
                if attr.startswith("detect_") and callable(getattr(module, attr))
            )
            for detector in detectors:
                self._validate_callable(
                    detector,
                    required=self._DETECTOR_REQUIRED,
                    allowed=self._DETECTOR_ALLOWED,
                    kind="detector",
                    field=field,
                )

            transformer = getattr(module, "transform", None)
            if transformer is not None:
                if not callable(transformer):
                    raise ColumnRegistryError(
                        f"Transform callable for field '{field}' must be callable"
                    )
                self._validate_callable(
                    transformer,
                    required=self._TRANSFORM_REQUIRED,
                    allowed=self._TRANSFORM_ALLOWED,
                    kind="transformer",
                    field=field,
                )
            validator = getattr(module, "validate", None)
            if validator is not None:
                if not callable(validator):
                    raise ColumnRegistryError(
                        f"Validator callable for field '{field}' must be callable"
                    )
                self._validate_callable(
                    validator,
                    required=self._VALIDATOR_REQUIRED,
                    allowed=self._VALIDATOR_ALLOWED,
                    kind="validator",
                    field=field,
                )

            meta_payload: Mapping[str, Any] = definition.model_dump()
            self._modules[field] = ColumnModule(
                field=field,
                meta=meta_payload,
                definition=definition,
                module=module,
                detectors=detectors,
                transformer=transformer,
                validator=validator,
            )

    def modules(self) -> Mapping[str, ColumnModule]:
        """Return loaded modules keyed by field name."""

        return self._modules

    def get(self, field: str) -> ColumnModule | None:
        """Return the module for ``field`` if registered."""

        return self._modules.get(field)

    @classmethod
    def _validate_callable(
        cls,
        func,
        *,
        required: Iterable[str],
        allowed: Iterable[str],
        kind: str,
        field: str,
    ) -> None:
        signature = inspect.signature(func)
        parameters = signature.parameters
        has_kwargs = any(
            param.kind is inspect.Parameter.VAR_KEYWORD
            for param in parameters.values()
        )
        missing = [
            name
            for name in required
            if name not in parameters and not has_kwargs
        ]
        if missing:
            raise ColumnRegistryError(
                f"{kind.title()} for field '{field}' must accept parameters: {', '.join(required)}"
            )

        for name, param in parameters.items():
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.VAR_POSITIONAL,
            ):
                continue
            if name in allowed:
                continue
            if param.default is inspect._empty and not has_kwargs:
                raise ColumnRegistryError(
                    f"{kind.title()} for field '{field}' has unsupported parameter '{name}'"
                )


def _script_to_module(script: str, *, package: str) -> str:
    module = script[:-3] if script.endswith(".py") else script
    module = module.replace("/", ".").replace("-", "_")
    return f"{package}.{module}" if not module.startswith(package) else module


__all__ = ["ColumnRegistry", "ColumnRegistryError"]
```

# apps/ade-engine/src/ade_engine/pipeline/runner.py
```python
"""Composable pipeline runner for extract/write stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import FileExtraction
from ade_engine.core.phases import PipelinePhase
from ade_engine.telemetry.logging import PipelineLogger


@dataclass(slots=True)
class PipelineRunner:
    """Coordinate pipeline phases while recording transitions."""

    job: JobContext
    logger: PipelineLogger
    phase: PipelinePhase = PipelinePhase.INITIALIZED
    tables: list[FileExtraction] = field(default_factory=list)
    output_paths: tuple[Path, ...] = ()

    def run(
        self,
        *,
        extract_stage: Callable[[JobContext, Any, PipelineLogger], list[FileExtraction]],
        write_stage: Callable[[JobContext, list[FileExtraction], PipelineLogger], Path | Sequence[Path]],
    ) -> None:
        """Execute extract then write, advancing phases and emitting transitions."""

        try:
            self._transition(PipelinePhase.EXTRACTING)
            self.tables = list(extract_stage(self.job, None, self.logger))

            self._transition(
                PipelinePhase.WRITING_OUTPUT, table_count=len(self.tables)
            )
            output = write_stage(self.job, self.tables, self.logger)
            self.output_paths = self._normalize_output_paths(output)

            self._transition(
                PipelinePhase.COMPLETED,
                outputs=[str(path) for path in self.output_paths],
            )
        except Exception as exc:  # pragma: no cover - will be exercised in integration
            self.phase = PipelinePhase.FAILED
            self.logger.transition(PipelinePhase.FAILED.value, error=str(exc))
            raise

    def _transition(self, next_phase: PipelinePhase, **payload: Any) -> None:
        self.phase = next_phase
        self.logger.transition(next_phase.value, **payload)

    def _normalize_output_paths(self, value: Path | Sequence[Path]) -> tuple[Path, ...]:
        if isinstance(value, Path):
            return (value,)
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        raise TypeError("Writer must return a Path or iterable of Paths")


__all__ = ["PipelineRunner"]
```

# apps/ade-engine/src/ade_engine/pipeline/stages.py
```python
"""Extract and write pipeline stages used by :class:`PipelineRunner`."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from ade_engine.core.manifest import ManifestContext
from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import ColumnModule, FileExtraction
from ade_engine.telemetry.logging import PipelineLogger

from .io import iter_tables, list_input_files, sheet_name
from .processing import process_table
from .util import unique_sheet_name
from . import output as writer


class ExtractStage:
    """Extract inputs into normalized tables."""

    def __init__(
        self,
        *,
        manifest: ManifestContext,
        modules: Mapping[str, ColumnModule],
        threshold: float,
        sample_size: int,
        append_unmapped: bool,
        unmapped_prefix: str,
    ) -> None:
        self._manifest = manifest
        self._modules = modules
        self._threshold = threshold
        self._sample_size = sample_size
        self._append_unmapped = append_unmapped
        self._unmapped_prefix = unmapped_prefix

    def run(
        self, job: JobContext, data: None, logger: PipelineLogger
    ) -> list[FileExtraction]:
        input_files = list_input_files(job.paths.input_dir)
        if not input_files:
            raise RuntimeError("No input files found for job")

        order = self._manifest.column_order
        meta = self._manifest.column_meta
        definitions = self._manifest.column_meta_models

        runtime_logger = logger.runtime_logger
        results: list[FileExtraction] = []
        used_sheet_names: set[str] = set()
        raw_sheet_names = job.metadata.get("input_sheet_names") if job.metadata else None
        sheet_list: list[str] | None = None
        if isinstance(raw_sheet_names, list):
            cleaned = [str(value).strip() for value in raw_sheet_names if str(value).strip()]
            sheet_list = cleaned or None

        for file_path in input_files:
            targets = sheet_list if file_path.suffix.lower() == ".xlsx" else None
            for source_sheet, header_row, data_rows in iter_tables(
                file_path, sheet_names=targets
            ):
                table_info = {
                    "headers": header_row,
                    "row_count": len(data_rows),
                    "column_count": len(header_row),
                    "source_name": file_path.name,
                    "sheet_name": source_sheet,
                }

                table_result = process_table(
                    job=job,
                    header_row=header_row,
                    data_rows=data_rows,
                    order=order,
                    meta=meta,
                    definitions=definitions,
                    modules=self._modules,
                    threshold=self._threshold,
                    sample_size=self._sample_size,
                    append_unmapped=self._append_unmapped,
                    unmapped_prefix=self._unmapped_prefix,
                    table_info=table_info,
                    state={},
                    logger=runtime_logger,
                )

                normalized_sheet = (
                    sheet_name(f"{file_path.stem}-{source_sheet}")
                    if source_sheet
                    else sheet_name(file_path.stem)
                )
                normalized_sheet = unique_sheet_name(normalized_sheet, used_sheet_names)
                extraction = FileExtraction(
                    source_name=file_path.name,
                    sheet_name=normalized_sheet,
                    mapped_columns=list(table_result.mapping),
                    extra_columns=list(table_result.extras),
                    rows=table_result.rows,
                    header_row=header_row,
                    validation_issues=table_result.issues,
                )

                logger.record_table(
                    {
                        "input_file": file_path.name,
                        "sheet": normalized_sheet,
                        "header": {"row_index": 1, "source": header_row},
                        "mapping": [
                            {
                                "field": entry.field,
                                "header": entry.header,
                                "source_column_index": entry.index,
                                "score": entry.score,
                                "contributions": [
                                    {
                                        "field": contrib.field,
                                        "detector": contrib.detector,
                                        "delta": contrib.delta,
                                    }
                                    for contrib in entry.contributions
                                ],
                            }
                            for entry in table_result.mapping
                        ],
                        "unmapped": [
                            {
                                "header": extra.header,
                                "source_column_index": extra.index,
                                "output_header": extra.output_header,
                            }
                            for extra in table_result.extras
                        ],
                        "validation": table_result.issues,
                    }
                )
                logger.note(
                    f"Processed input file {file_path.name}",
                    mapped_fields=[entry.field for entry in table_result.mapping],
                )
                logger.flush()
                logger.event(
                    "file_processed",
                    file=file_path.name,
                    mapped_fields=[entry.field for entry in table_result.mapping],
                    validation_issue_count=len(table_result.issues),
                )
                for issue in table_result.issues:
                    logger.event(
                        "validation_issue",
                        level="warning",
                        file=file_path.name,
                        row_index=issue.get("row_index"),
                        field=issue.get("field"),
                        code=issue.get("code"),
                    )

                results.append(extraction)

        return results


class WriteStage:
    """Write normalized outputs."""

    def __init__(self, *, manifest: ManifestContext) -> None:
        self._manifest = manifest

    def run(
        self, job: JobContext, tables: list[FileExtraction], logger: PipelineLogger
    ) -> Path | Sequence[Path]:
        return writer.write_outputs(job, self._manifest, tables)


__all__ = ["ExtractStage", "WriteStage"]
```

# apps/ade-engine/src/ade_engine/pipeline/util.py
```python
"""Small pipeline utility helpers."""

from __future__ import annotations


def unique_sheet_name(name: str, used: set[str]) -> str:
    """Return an Excel-safe sheet name unique across the workbook."""

    if name not in used:
        used.add(name)
        return name

    counter = 2
    max_length = 31
    while True:
        suffix = f"-{counter}"
        base_limit = max_length - len(suffix)
        base = name[:base_limit] if base_limit > 0 else name[:max_length]
        candidate = f"{base}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        counter += 1


__all__ = ["unique_sheet_name"]
```

# apps/ade-engine/src/ade_engine/plugins/__init__.py
```python
"""Plugin utilities."""

from .utils import _script_to_module
from ade_engine.telemetry.types import _load_event_sink_factories, _load_event_sink_factory

load_event_sink_factories = _load_event_sink_factories
load_event_sink_factory = _load_event_sink_factory

__all__ = ["_script_to_module", "load_event_sink_factories", "load_event_sink_factory"]
```

# apps/ade-engine/src/ade_engine/plugins/utils.py
```python
"""Shared helpers for plugin/hook resolution."""

from __future__ import annotations


def _script_to_module(script: str, *, package: str) -> str:
    """Normalize a script path into an importable module name."""

    module = script[:-3] if script.endswith(".py") else script
    module = module.replace("/", ".").replace("-", "_")
    if not module.startswith(package):
        return f"{package}.{module}"
    return module


__all__ = ["_script_to_module"]
```

# apps/ade-engine/src/ade_engine/runtime.py
```python
"""Runtime helpers for :mod:`ade_engine`.

Kept as compatibility adapters; prefer :mod:`ade_engine.config.loader` helpers internally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ade_engine.config.loader import (
    ManifestNotFoundError,
    load_manifest as _load_manifest,
    resolve_input_sheets,
    resolve_jobs_root,
)
from ade_engine.core.manifest import ManifestContext


def load_config_manifest(
    *,
    package: str = "ade_config",
    resource: str = "manifest.json",
    manifest_path: Path | None = None,
    validate: bool = True,  # kept for compatibility; always validated
) -> dict[str, Any]:
    """Return the ade_config manifest as a dict (deprecated for internal use)."""

    ctx = _load_manifest(package=package, resource=resource, manifest_path=manifest_path)
    return ctx.raw


def load_manifest_context(
    *,
    package: str = "ade_config",
    resource: str = "manifest.json",
    manifest_path: Path | None = None,
) -> ManifestContext:
    """Return a :class:`ManifestContext` with schema-derived helpers."""

    return _load_manifest(
        package=package,
        resource=resource,
        manifest_path=manifest_path,
    )


__all__ = [
    "ManifestContext",
    "ManifestNotFoundError",
    "load_config_manifest",
    "load_manifest_context",
    "resolve_input_sheets",
    "resolve_jobs_root",
]
```

# apps/ade-engine/src/ade_engine/schemas/__init__.py
```python
"""Shared schema models and JSON definitions used by the ADE engine."""

from .manifest import (
    ColumnMeta,
    ColumnSection,
    EngineDefaults,
    EngineSection,
    EngineWriter,
    HookCollection,
    ManifestContext,
    ManifestInfo,
    ManifestV1,
    ScriptRef,
)
from .telemetry import ADE_TELEMETRY_EVENT_SCHEMA, TelemetryEnvelope, TelemetryEvent

__all__ = [
    "ADE_TELEMETRY_EVENT_SCHEMA",
    "ColumnMeta",
    "ColumnSection",
    "EngineDefaults",
    "EngineSection",
    "EngineWriter",
    "HookCollection",
    "ManifestContext",
    "ManifestInfo",
    "ManifestV1",
    "ScriptRef",
    "TelemetryEnvelope",
    "TelemetryEvent",
]
```

# apps/ade-engine/src/ade_engine/schemas/manifest.py
```python
"""Compatibility re-exports for manifest schema models."""

from ade_engine.core.manifest import (
    ColumnMeta,
    ColumnSection,
    EngineDefaults,
    EngineSection,
    EngineWriter,
    HookCollection,
    ManifestContext,
    ManifestInfo,
    ManifestV1,
    ScriptRef,
)

__all__ = [
    "ColumnMeta",
    "ColumnSection",
    "EngineDefaults",
    "EngineSection",
    "EngineWriter",
    "HookCollection",
    "ManifestContext",
    "ManifestInfo",
    "ManifestV1",
    "ScriptRef",
]
```

# apps/ade-engine/src/ade_engine/schemas/manifest.v1.schema.json
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:ade:manifest.v1.0",
  "title": "ADE Config Manifest v1.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["config_script_api_version", "info", "engine", "hooks", "columns"],
  "properties": {
    "config_script_api_version": { "type": "string", "const": "1" },
    "info": {
      "type": "object",
      "additionalProperties": false,
      "required": ["schema", "title", "version"],
      "properties": {
        "schema": { "type": "string", "const": "ade.manifest/v1.0" },
        "title": { "type": "string", "minLength": 1 },
        "version": {
          "type": "string",
          "pattern": "^\\d+\\.\\d+\\.\\d+(?:-[0-9A-Za-z.-]+)?(?:\\+[0-9A-Za-z.-]+)?$"
        },
        "description": { "type": "string" }
      }
    },
    "env": {
      "type": "object",
      "description": "Environment variables exposed to scripts",
      "additionalProperties": { "type": "string" }
    },
    "engine": {
      "type": "object",
      "additionalProperties": false,
      "required": ["defaults", "writer"],
      "properties": {
        "defaults": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "timeout_ms": { "type": "integer", "minimum": 1000 },
            "memory_mb": { "type": "integer", "minimum": 64 },
            "runtime_network_access": { "type": "boolean", "default": false },
            "mapping_score_threshold": { "type": "number", "minimum": 0.0 },
            "detector_sample_size": { "type": "integer", "minimum": 1 }
          }
        },
        "writer": {
          "type": "object",
          "additionalProperties": false,
          "required": ["mode", "append_unmapped_columns", "unmapped_prefix", "output_sheet"],
          "properties": {
            "mode": { "type": "string", "enum": ["row_streaming", "in_memory"], "default": "row_streaming" },
            "append_unmapped_columns": { "type": "boolean", "default": true },
            "unmapped_prefix": { "type": "string", "minLength": 1, "default": "raw_" },
            "output_sheet": { "type": "string", "minLength": 1, "maxLength": 31, "default": "Normalized" }
          }
        }
      }
    },
    "hooks": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "on_activate": { "$ref": "#/$defs/HookList" },
        "on_job_start": { "$ref": "#/$defs/HookList" },
        "on_after_extract": { "$ref": "#/$defs/HookList" },
        "on_before_save": { "$ref": "#/$defs/HookList" },
        "on_job_end": { "$ref": "#/$defs/HookList" }
      }
    },
    "columns": {
      "type": "object",
      "additionalProperties": false,
      "required": ["order", "meta"],
      "properties": {
        "order": {
          "type": "array",
          "items": { "$ref": "#/$defs/TargetFieldId" },
          "minItems": 1,
          "uniqueItems": true
        },
        "meta": {
          "type": "object",
          "additionalProperties": { "$ref": "#/$defs/ColumnMeta" }
        }
      }
    }
  },
  "$defs": {
    "ScriptRef": {
      "type": "object",
      "additionalProperties": false,
      "required": ["script"],
      "properties": {
        "script": {
          "type": "string",
          "pattern": "^(hooks/)?[A-Za-z0-9_.\\-/]+\\.py$"
        },
        "enabled": { "type": "boolean", "default": true }
      }
    },
    "HookList": {
      "type": "array",
      "items": { "$ref": "#/$defs/ScriptRef" }
    },
    "TargetFieldId": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" },
    "ColumnMeta": {
      "type": "object",
      "additionalProperties": false,
      "required": ["label", "script"],
      "properties": {
        "label": { "type": "string" },
        "required": { "type": "boolean", "default": false },
        "enabled": { "type": "boolean", "default": true },
        "script": {
          "type": "string",
          "pattern": "^columns/[A-Za-z0-9_.\\-/]+\\.py$"
        },
        "synonyms": {
          "type": "array",
          "items": { "type": "string" }
        },
        "type_hint": { "type": "string" }
      }
    }
  }
}
```

# apps/ade-engine/src/ade_engine/schemas/models.py
```python
"""Compatibility re-exports for manifest schemas bundled with :mod:`ade_engine`."""

from .manifest import (
    ColumnMeta,
    ColumnSection,
    EngineDefaults,
    EngineSection,
    EngineWriter,
    HookCollection,
    ManifestContext,
    ManifestInfo,
    ManifestV1,
    ScriptRef,
)

__all__ = [
    "ColumnMeta",
    "ColumnSection",
    "EngineDefaults",
    "EngineSection",
    "EngineWriter",
    "HookCollection",
    "ManifestContext",
    "ManifestInfo",
    "ManifestV1",
    "ScriptRef",
]
```

# apps/ade-engine/src/ade_engine/schemas/telemetry.event.v1.schema.json
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.ade.dev/telemetry/run-event.v1.json",
  "title": "ADE Telemetry Run Event",
  "type": "object",
  "required": ["schema", "version", "job_id", "timestamp", "event"],
  "additionalProperties": false,
  "properties": {
    "schema": {
      "const": "ade.telemetry/run-event.v1"
    },
    "version": {
      "type": "string"
    },
    "job_id": {
      "type": "string",
      "minLength": 1
    },
    "run_id": {
      "type": "string",
      "minLength": 1
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "event": {
      "type": "object",
      "required": ["event", "level"],
      "additionalProperties": true,
      "properties": {
        "event": {
          "type": "string",
          "minLength": 1
        },
        "level": {
          "type": "string",
          "enum": ["debug", "info", "warning", "error", "critical"]
        }
      }
    }
  }
}
```

# apps/ade-engine/src/ade_engine/schemas/telemetry.py
```python
"""Telemetry envelope schemas shared across ADE components."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ADE_TELEMETRY_EVENT_SCHEMA = "ade.telemetry/run-event.v1"

TelemetryLevel = Literal["debug", "info", "warning", "error", "critical"]


class TelemetryEvent(BaseModel):
    """Event payload emitted by the engine runtime."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str = Field(alias="event")
    level: TelemetryLevel = "info"

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)


class TelemetryEnvelope(BaseModel):
    """Versioned envelope for ADE telemetry events."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema: Literal[ADE_TELEMETRY_EVENT_SCHEMA] = ADE_TELEMETRY_EVENT_SCHEMA
    version: str = Field(default="1.0.0")
    job_id: str
    run_id: str | None = None
    emitted_at: datetime = Field(alias="timestamp")
    event: TelemetryEvent

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(*args, **kwargs)


__all__ = [
    "ADE_TELEMETRY_EVENT_SCHEMA",
    "TelemetryEnvelope",
    "TelemetryEvent",
    "TelemetryLevel",
]
```

# apps/ade-engine/src/ade_engine/sinks.py
```python
"""Compatibility shim; prefer :mod:`ade_engine.telemetry.sinks`."""

from ade_engine.telemetry.sinks import *  # noqa: F401,F403
```

# apps/ade-engine/src/ade_engine/telemetry.py
```python
"""Compatibility shim; prefer :mod:`ade_engine.telemetry.types`."""

from ade_engine.telemetry import *  # noqa: F401,F403
```

# apps/ade-engine/src/ade_engine/telemetry/__init__.py
```python
"""Telemetry types, sinks, and logging helpers."""

from .types import TelemetryBindings, TelemetryConfig, level_value
from .sinks import (
    ArtifactSink,
    DispatchEventSink,
    EventSink,
    EventSinkFactory,
    FileArtifactSink,
    FileEventSink,
    FileSinkProvider,
    SinkProvider,
    _now,
    _now_iso,
)
from .logging import PipelineLogger

__all__ = [
    "ArtifactSink",
    "DispatchEventSink",
    "EventSink",
    "EventSinkFactory",
    "FileArtifactSink",
    "FileEventSink",
    "FileSinkProvider",
    "PipelineLogger",
    "SinkProvider",
    "TelemetryBindings",
    "TelemetryConfig",
    "_now",
    "_now_iso",
    "level_value",
]
```

# apps/ade-engine/src/ade_engine/telemetry/logging.py
```python
"""Pipeline-facing logger abstraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ade_engine.core.models import JobContext

from .sinks import ArtifactSink, EventSink
from .types import TelemetryBindings, level_value


@dataclass(slots=True)
class PipelineLogger:
    """Bridge artifact and event sinks with a consistent API."""

    job: JobContext
    telemetry: TelemetryBindings
    runtime_logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("ade_engine.pipeline")
    )
    artifact: ArtifactSink = field(init=False)
    events: EventSink = field(init=False)

    def __post_init__(self) -> None:
        self.artifact = self.telemetry.artifact
        self.events = self.telemetry.events

    def note(self, message: str, *, level: str = "info", **details: Any) -> None:
        """Record a structured note in the artifact output."""

        record_level = level_value(level)
        if self.telemetry.enabled_for_note(level):
            enriched = self.telemetry.decorate_details(details)
            self.artifact.note(message, level=level, **enriched)
        self.runtime_logger.log(record_level, message, extra={"details": details})

    def event(self, name: str, *, level: str = "info", **payload: Any) -> None:
        """Emit a structured event for downstream consumers."""

        record_level = level_value(level)
        enriched = {"level": level, **payload}
        enriched = self.telemetry.decorate_payload(enriched)
        if self.telemetry.enabled_for_event(level):
            self.events.log(name, job=self.job, **enriched)
        self.runtime_logger.log(
            record_level,
            "event %s",
            name,
            extra={"payload": enriched},
        )

    def record_table(self, table: dict[str, Any]) -> None:
        """Persist table metadata to the artifact."""

        self.artifact.record_table(table)

    def flush(self) -> None:
        """Flush the artifact sink to disk."""

        self.artifact.flush()

    def transition(self, phase: str, **payload: Any) -> None:
        """Announce a pipeline phase transition."""

        event_payload = {"phase": phase, **payload}
        self.event("pipeline_transition", level="debug", **event_payload)
        self.note(
            f"Pipeline entered '{phase}' phase",
            level="debug",
            phase=phase,
            **payload,
        )


__all__ = ["PipelineLogger"]
```

# apps/ade-engine/src/ade_engine/telemetry/sinks.py
```python
"""Artifact and event sink abstractions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, runtime_checkable

from ade_engine.schemas import TelemetryEnvelope, TelemetryEvent

from ade_engine.core.models import JobContext, JobPaths


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso(moment: datetime | None = None) -> str:
    ts = moment or _now()
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


@runtime_checkable
class ArtifactSink(Protocol):
    """Destination for job artifact data."""

    def start(self, *, job: JobContext, manifest: dict[str, Any]) -> None: ...

    def note(self, message: str, *, level: str = "info", **extra: Any) -> None: ...

    def record_table(self, table: dict[str, Any]) -> None: ...

    def mark_success(self, *, completed_at: datetime, outputs: Iterable[Path]) -> None: ...

    def mark_failure(self, *, completed_at: datetime, error: Exception) -> None: ...

    def flush(self) -> None: ...


@runtime_checkable
class EventSink(Protocol):
    """Structured event consumer."""

    def log(self, event: str, *, job: JobContext, **payload: Any) -> None: ...


@runtime_checkable
class SinkProvider(Protocol):
    """Factory that produces artifact and event sinks for a job."""

    def artifact(self, job: JobContext) -> ArtifactSink: ...

    def events(self, job: JobContext) -> EventSink: ...


EventSinkFactory = Callable[[JobContext, JobPaths], EventSink]


class FileArtifactSink:
    """Persist job artifact JSON with atomic writes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {}

    def start(self, *, job: JobContext, manifest: dict[str, Any]) -> None:
        self.data = {
            "schema": "ade.artifact/v1alpha",
            "artifact_version": "0.1.0",
            "job": {
                "job_id": job.job_id,
                "status": "running",
                "started_at": _now_iso(job.started_at),
            },
            "config": {
                "schema": manifest.get("info", {}).get("schema"),
                "manifest_version": manifest.get("info", {}).get("version"),
            },
            "tables": [],
            "notes": [],
        }
        self.flush()

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(self.path)

    def note(self, message: str, *, level: str = "info", **extra: Any) -> None:
        entry = {"timestamp": _now_iso(), "level": level, "message": message}
        if extra:
            entry["details"] = extra
        self.data.setdefault("notes", []).append(entry)

    def record_table(self, table: dict[str, Any]) -> None:
        self.data.setdefault("tables", []).append(table)

    def mark_success(self, *, completed_at: datetime, outputs: Iterable[Path]) -> None:
        self.data["job"].update(
            {
                "status": "succeeded",
                "completed_at": _now_iso(completed_at),
                "outputs": [str(path) for path in outputs],
            }
        )

    def mark_failure(self, *, completed_at: datetime, error: Exception) -> None:
        self.data["job"].update(
            {
                "status": "failed",
                "completed_at": _now_iso(completed_at),
                "error": {
                    "type": error.__class__.__name__,
                    "message": str(error),
                },
            }
        )


class FileEventSink:
    """Append structured job lifecycle events to ``events.ndjson``."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
        payload_data = dict(payload)
        level = str(payload_data.pop("level", "info"))
        event_payload = TelemetryEvent(name=event, level=level, **payload_data)
        envelope = TelemetryEnvelope(
            job_id=job.job_id,
            run_id=str(job.metadata.get("run_id")) if job.metadata.get("run_id") else None,
            emitted_at=_now(),
            event=event_payload,
        )
        serialized = envelope.model_dump_json()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(serialized + "\n")


class DispatchEventSink:
    """Broadcast telemetry events to multiple sinks."""

    def __init__(self, sinks: Iterable[EventSink]) -> None:
        self._sinks = tuple(sinks)

    def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
        for sink in self._sinks:
            sink.log(event, job=job, **payload)


class FileSinkProvider:
    """Provide file-backed sinks for a job."""

    def __init__(self, paths: JobPaths) -> None:
        self._paths = paths

    def artifact(self, job: JobContext) -> ArtifactSink:
        return FileArtifactSink(self._paths.artifact_path)

    def events(self, job: JobContext) -> EventSink:
        return FileEventSink(self._paths.events_path)


__all__ = [
    "ArtifactSink",
    "DispatchEventSink",
    "EventSink",
    "EventSinkFactory",
    "FileArtifactSink",
    "FileEventSink",
    "FileSinkProvider",
    "SinkProvider",
    "_now",
    "_now_iso",
]
```

# apps/ade-engine/src/ade_engine/telemetry/types.py
```python
"""Telemetry configuration helpers for ADE runtime instrumentation."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Iterable

from importlib import import_module

from ade_engine.core.models import JobContext, JobPaths

from .sinks import (
    ArtifactSink,
    DispatchEventSink,
    EventSink,
    EventSinkFactory,
    FileSinkProvider,
    SinkProvider,
)

_LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def _normalize_level(level: str) -> str:
    return (level or "info").lower()


def level_value(level: str) -> int:
    """Return the logging level numeric value for ``level``."""

    return _LEVELS.get(_normalize_level(level), logging.INFO)


@dataclass(slots=True)
class TelemetryConfig:
    """Standardize runtime telemetry behavior across sinks."""

    correlation_id: str | None = None
    min_note_level: str = "debug"
    min_event_level: str = "debug"
    sink_provider: SinkProvider | None = None
    event_sink_factories: tuple[EventSinkFactory, ...] = field(default_factory=tuple)
    event_sink_specs: tuple[str, ...] = field(default_factory=tuple)
    sink_spec_env: str | None = "ADE_TELEMETRY_SINKS"

    def bind(
        self,
        job: JobContext,
        paths: JobPaths,
        *,
        provider: SinkProvider | None = None,
    ) -> "TelemetryBindings":
        """Create sink bindings for ``job`` using configured defaults."""

        selected = provider or self.sink_provider or FileSinkProvider(paths)
        artifact: ArtifactSink = selected.artifact(job)
        base_events: EventSink = selected.events(job)
        extra_sinks = [factory(job, paths) for factory in self._resolve_event_factories()]
        if extra_sinks:
            events: EventSink = DispatchEventSink((base_events, *extra_sinks))
        else:
            events = base_events
        return TelemetryBindings(
            job=job,
            config=self,
            provider=selected,
            artifact=artifact,
            events=events,
        )

    def _resolve_event_factories(self) -> tuple[EventSinkFactory, ...]:
        """Return configured event sink factories including env overrides."""

        factories = list(self.event_sink_factories)
        specs: list[str] = list(self.event_sink_specs)
        if self.sink_spec_env:
            raw_value = os.getenv(self.sink_spec_env, "")
            specs.extend(part.strip() for part in raw_value.split(",") if part.strip())
        if specs:
            factories.extend(_load_event_sink_factories(specs))
        return tuple(factories)


@dataclass(slots=True)
class TelemetryBindings:
    """Concrete sink bindings produced from a :class:`TelemetryConfig`."""

    job: JobContext
    config: TelemetryConfig
    provider: SinkProvider
    artifact: ArtifactSink
    events: EventSink

    def enabled_for_note(self, level: str) -> bool:
        """Return ``True`` when ``level`` meets the note severity threshold."""

        threshold = level_value(self.config.min_note_level)
        return level_value(level) >= threshold

    def enabled_for_event(self, level: str) -> bool:
        """Return ``True`` when ``level`` meets the event severity threshold."""

        threshold = level_value(self.config.min_event_level)
        return level_value(level) >= threshold

    def decorate_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """Attach correlation metadata to artifact note details."""

        if not self.config.correlation_id:
            return details
        enriched = dict(details)
        enriched.setdefault("correlation_id", self.config.correlation_id)
        return enriched

    def decorate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Attach correlation metadata to event payloads."""

        if not self.config.correlation_id:
            return payload
        enriched = dict(payload)
        enriched.setdefault("correlation_id", self.config.correlation_id)
        return enriched


def _split_spec(spec: str) -> tuple[str, str]:
    module_path, separator, attr = spec.partition(":")
    if not separator:
        module_path, dot, attr = spec.rpartition(".")
        if not dot:
            raise ValueError(f"Invalid sink specification: '{spec}'")
    if not module_path or not attr:
        raise ValueError(f"Invalid sink specification: '{spec}'")
    return module_path, attr


def _load_event_sink_factory(spec: str) -> EventSinkFactory:
    """Return the event sink factory referenced by ``spec``."""

    module_path, attr = _split_spec(spec)
    module = import_module(module_path)
    candidate = getattr(module, attr)
    if not callable(candidate):  # pragma: no cover - defensive guard
        raise TypeError(f"Telemetry sink factory '{spec}' is not callable")
    return candidate  # type: ignore[return-value]


def _load_event_sink_factories(specs: Iterable[str]) -> tuple[EventSinkFactory, ...]:
    """Load telemetry sink factories for ``specs``."""

    factories: list[EventSinkFactory] = []
    for spec in specs:
        spec = spec.strip()
        if not spec:
            continue
        factories.append(_load_event_sink_factory(spec))
    return tuple(factories)


__all__ = [
    "TelemetryBindings",
    "TelemetryConfig",
    "level_value",
]
```

# apps/ade-engine/src/ade_engine/worker.py
```python
"""Job orchestration for the ADE engine (legacy adapter)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ade_engine.config.loader import resolve_jobs_root
from ade_engine.core.manifest import EngineDefaults, EngineWriter
from ade_engine.core.models import JobResult
from ade_engine.core.phases import PipelinePhase
from ade_engine.hooks import (
    HookContext,
    HookExecutionError,
    HookLoadError,
    HookRegistry,
    HookStage,
)
from .job_service import JobService
from .pipeline.runner import PipelineRunner
from .pipeline.stages import ExtractStage, WriteStage
from .telemetry.sinks import SinkProvider
from .telemetry.types import TelemetryConfig


def run_job(
    job_id: str,
    *,
    jobs_dir: Path | None = None,
    manifest_path: Path | None = None,
    config_package: str = "ade_config",
    safe_mode: bool = False,
    sink_provider: SinkProvider | None = None,
    telemetry: TelemetryConfig | None = None,
) -> JobResult:
    """Execute the ADE job pipeline (legacy adapter)."""

    jobs_root = resolve_jobs_root(jobs_dir)
    service = JobService(config_package=config_package, telemetry=telemetry)
    prepared = service.prepare_job(
        job_id,
        jobs_root=jobs_root,
        manifest_path=manifest_path,
        safe_mode=safe_mode,
        sink_provider=sink_provider,
    )
    return service.run(prepared)


__all__ = [
    "HookExecutionError",
    "HookLoadError",
    "run_job",
]
```

# apps/ade-engine/tests/conftest.py
```python
import sys
from pathlib import Path


# Ensure source root is importable when running tests directly.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "ade-engine" / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
```

# apps/ade-engine/tests/pipeline/test_io.py
```python
from pathlib import Path

import openpyxl
import pytest

from ade_engine.pipeline.io import iter_tables, list_input_files, read_table, sheet_name


def test_list_input_files_filters_extensions(tmp_path: Path) -> None:
    files = [
        tmp_path / "data.csv",
        tmp_path / "notes.txt",
        tmp_path / "table.xlsx",
    ]
    (tmp_path / "dir").mkdir()
    for path in files:
        if path.suffix == ".xlsx":
            workbook = openpyxl.Workbook()
            workbook.save(path)
            workbook.close()
        else:
            path.write_text("header\nvalue\n", encoding="utf-8")
    results = list_input_files(tmp_path)
    assert [file.name for file in results] == ["data.csv", "table.xlsx"]


def test_read_table_handles_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "values.csv"
    csv_path.write_text("Name,Email\nAlice,alice@example.com\n", encoding="utf-8")
    header, rows = read_table(csv_path)
    assert header == ["Name", "Email"]
    assert rows[0][1] == "alice@example.com"


def test_read_table_uses_named_sheet_when_provided(tmp_path: Path) -> None:
    workbook = openpyxl.Workbook()
    workbook.active.title = "Summary"
    data = workbook.create_sheet("Data")
    data.append(["Name", "Role"])
    data.append(["Mina", "Analyst"])
    path = tmp_path / "people.xlsx"
    workbook.save(path)
    workbook.close()

    header, rows = read_table(path, sheet_name="Data")
    assert header == ["Name", "Role"]
    assert rows == [["Mina", "Analyst"]]


def test_read_table_errors_when_sheet_missing(tmp_path: Path) -> None:
    workbook = openpyxl.Workbook()
    path = tmp_path / "missing.xlsx"
    workbook.save(path)
    workbook.close()

    with pytest.raises(RuntimeError):
        read_table(path, sheet_name="Nope")


def test_sheet_name_sanitizes_input() -> None:
    assert sheet_name("Employee-List 2024") == "Employee List 2024"


def test_iter_tables_yields_all_worksheets_by_default(tmp_path: Path) -> None:
    workbook = openpyxl.Workbook()
    active = workbook.active
    active.title = "Summary"
    active.append(["Name", "Role"])
    active.append(["Mina", "Analyst"])

    detail = workbook.create_sheet("Detail")
    detail.append(["Name", "Score"])
    detail.append(["Mina", "90"])

    path = tmp_path / "people.xlsx"
    workbook.save(path)
    workbook.close()

    tables = list(iter_tables(path))
    assert [sheet for sheet, _, _ in tables] == ["Summary", "Detail"]


def test_iter_tables_can_limit_to_subset(tmp_path: Path) -> None:
    workbook = openpyxl.Workbook()
    workbook.active.title = "Primary"
    workbook.active.append(["Name"])
    workbook.active.append(["Keep"])

    other = workbook.create_sheet("Secondary")
    other.append(["Name"])
    other.append(["Skip"])

    path = tmp_path / "subset.xlsx"
    workbook.save(path)
    workbook.close()

    tables = list(iter_tables(path, sheet_names=["Secondary"]))
    assert [sheet for sheet, _, _ in tables] == ["Secondary"]
```

# apps/ade-engine/tests/pipeline/test_mapping.py
```python
from datetime import datetime, timezone
from types import SimpleNamespace

from ade_engine.schemas.manifest import ColumnMeta

from ade_engine.pipeline.mapping import (
    build_unmapped_header,
    column_sample,
    map_columns,
    match_header,
)
from ade_engine.pipeline.models import ColumnModule
from ade_engine.core.models import JobContext, JobPaths


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

    definition = ColumnMeta(label="Email", script="tests.email")
    modules = {
        "email": ColumnModule(
            field="email",
            meta=definition.model_dump(),
            definition=definition,
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
        {"email": definition},
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
    definition = ColumnMeta(label="Member", script="tests.member", synonyms=("ID",))
    result = match_header(
        ["member_id"],
        {"member_id": definition},
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
```

# apps/ade-engine/tests/pipeline/test_normalize.py
```python
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
```

# apps/ade-engine/tests/pipeline/test_output.py
```python
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

from ade_engine.core.models import JobContext, JobPaths
from ade_engine.pipeline.models import ColumnMapping, ExtraColumn, FileExtraction
from ade_engine.pipeline.output import output_headers, write_outputs
from ade_engine.schemas.models import ManifestContext


def _job(tmp_path: Path) -> JobContext:
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True)
    paths = JobPaths(
        jobs_root=tmp_path,
        job_dir=tmp_path,
        input_dir=tmp_path / "input",
        output_dir=output_dir,
        logs_dir=tmp_path / "logs",
        artifact_path=tmp_path / "logs" / "artifact.json",
        events_path=tmp_path / "logs" / "events.ndjson",
    )
    return JobContext(job_id="job", manifest={}, paths=paths, started_at=datetime.now(timezone.utc))


def test_output_headers_combines_manifest_and_extras() -> None:
    extraction = FileExtraction(
        source_name="file.csv",
        sheet_name="Sheet",
        mapped_columns=[
            ColumnMapping(field="member_id", header="ID", index=0, score=1.0, contributions=tuple())
        ],
        extra_columns=[ExtraColumn(header="Original", index=1, output_header="raw_original")],
        rows=[["123", "foo"]],
        header_row=["ID", "Original"],
        validation_issues=[],
    )
    manifest = ManifestContext(
        raw={"columns": {"order": ["member_id"], "meta": {"member_id": {"label": "Member"}}}},
        version=None,
        model=None,
    )
    headers = output_headers(manifest, extraction)
    assert headers == ["Member", "raw_original"]


def test_write_outputs_creates_workbook(tmp_path: Path) -> None:
    job = _job(tmp_path)
    extraction = FileExtraction(
        source_name="file.csv",
        sheet_name="Employees",
        mapped_columns=[
            ColumnMapping(field="member_id", header="ID", index=0, score=1.0, contributions=tuple())
        ],
        extra_columns=[],
        rows=[["123"]],
        header_row=["ID"],
        validation_issues=[],
    )
    manifest = ManifestContext(
        raw={"columns": {"order": ["member_id"], "meta": {"member_id": {"label": "Member"}}}},
        version=None,
        model=None,
    )

    output_path = write_outputs(job, manifest, [extraction])
    workbook = openpyxl.load_workbook(output_path, read_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    first_row = next(sheet.iter_rows(values_only=True))
    assert first_row == ("Member",)
    workbook.close()


def test_write_outputs_dedupes_sheet_names(tmp_path: Path) -> None:
    job = _job(tmp_path)
    manifest = ManifestContext(
        raw={"columns": {"order": ["member_id"], "meta": {"member_id": {"label": "Member"}}}},
        version=None,
        model=None,
    )
    base_extraction = FileExtraction(
        source_name="file.csv",
        sheet_name="Employees",
        mapped_columns=[
            ColumnMapping(field="member_id", header="ID", index=0, score=1.0, contributions=tuple())
        ],
        extra_columns=[],
        rows=[["123"]],
        header_row=["ID"],
        validation_issues=[],
    )
    second = FileExtraction(
        source_name="file2.csv",
        sheet_name="Employees",
        mapped_columns=list(base_extraction.mapped_columns),
        extra_columns=list(base_extraction.extra_columns),
        rows=[["456"]],
        header_row=["ID"],
        validation_issues=[],
    )

    output_path = write_outputs(job, manifest, [base_extraction, second])
    workbook = openpyxl.load_workbook(output_path, read_only=True)
    assert workbook.sheetnames == ["Employees", "Employees-2"]
    workbook.close()
```

# apps/ade-engine/tests/pipeline/test_registry.py
```python
import sys
import textwrap
import textwrap
from pathlib import Path

import pytest

from ade_engine.schemas.manifest import ColumnMeta

from ade_engine.pipeline.registry import ColumnRegistry, ColumnRegistryError


def _write_module(root: Path, path: str, content: str) -> None:
    file_path = root / path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(textwrap.dedent(content), encoding="utf-8")


def _reset_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(sys.modules):
        if name == "ade_config" or name.startswith("ade_config."):
            monkeypatch.delitem(sys.modules, name, raising=False)


def test_column_registry_loads_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_root = tmp_path / "cfg"
    module_root = pkg_root / "ade_config"
    module_root.mkdir(parents=True)
    (module_root / "__init__.py").write_text("", encoding="utf-8")
    _write_module(
        module_root,
        "column_detectors/member.py",
        """
        def detect_from_header(**kwargs):
            return {"scores": {kwargs["field_name"]: 1.0}}

        def transform(*, value, row, field_name, **_):
            row[field_name] = value
            return {field_name: value}

        def validate(*, value, field_name, row_index, **_):
            if not value:
                return [{"code": "missing", "row_index": row_index, "field": field_name}]
            return []
        """,
    )

    monkeypatch.syspath_prepend(str(pkg_root))
    _reset_modules(monkeypatch)
    registry = ColumnRegistry(
        {"member": ColumnMeta(label="Member", script="column_detectors/member.py")},
        package="ade_config",
    )

    module = registry.get("member")
    assert module is not None
    assert module.detectors
    assert callable(module.transformer)
    assert callable(module.validator)


def test_column_registry_validates_signatures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_root = tmp_path / "cfg"
    module_root = pkg_root / "ade_config"
    module_root.mkdir(parents=True)
    (module_root / "__init__.py").write_text("", encoding="utf-8")
    _write_module(
        module_root,
        "column_detectors/member.py",
        """
        def detect_from_header(header):
            return {"scores": {}}

        def transform(value):
            return value
        """,
    )

    monkeypatch.syspath_prepend(str(pkg_root))
    _reset_modules(monkeypatch)

    with pytest.raises(ColumnRegistryError) as excinfo:
        ColumnRegistry(
            {"member": ColumnMeta(label="Member", script="column_detectors/member.py")},
            package="ade_config",
        )

    assert "must accept parameters" in str(excinfo.value)
```

# apps/ade-engine/tests/test_hooks_registry.py
```python
from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ade_engine.core.manifest import ManifestContext
from ade_engine.core.models import JobContext, JobPaths
from ade_engine.hooks import HookContext, HookExecutionError, HookRegistry, HookStage
from ade_engine.telemetry.sinks import ArtifactSink


@dataclass
class DummyArtifact(ArtifactSink):
    notes: list[dict[str, Any]] | None = None

    def start(self, *, job: JobContext, manifest: dict[str, Any]) -> None: ...

    def note(self, message: str, *, level: str = "info", **extra: Any) -> None:
        self.notes = self.notes or []
        self.notes.append({"message": message, "level": level, "extra": extra})

    def record_table(self, table: dict[str, Any]) -> None: ...

    def mark_success(self, *, completed_at, outputs) -> None: ...

    def mark_failure(self, *, completed_at, error) -> None: ...

    def flush(self) -> None: ...


def _job() -> JobContext:
    paths = JobPaths(
        jobs_root=Path("/tmp"),
        job_dir=Path("/tmp"),
        input_dir=Path("/tmp"),
        output_dir=Path("/tmp"),
        logs_dir=Path("/tmp"),
        artifact_path=Path("/tmp/artifact.json"),
        events_path=Path("/tmp/events.ndjson"),
    )
    return JobContext(
        job_id="job",
        manifest={},
        paths=paths,
        started_at=datetime.utcnow(),
    )


def _install_temp_hook(tmp_path: Path) -> str:
    pkg = tmp_path / "test_hooks_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    hooks_dir = pkg / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "__init__.py").write_text("", encoding="utf-8")
    (hooks_dir / "on_job_start.py").write_text(
        "def run(job=None, artifact=None, **_: object):\n"
        "    artifact.note('hello', level='info')\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    return "test_hooks_pkg"


def test_hook_registry_executes_and_passes_context(tmp_path: Path):
    package = _install_temp_hook(tmp_path)
    manifest = ManifestContext(
        raw={
            "hooks": {
                "on_job_start": [{"script": "hooks/on_job_start.py"}],
            }
        },
        model=None,
    )
    registry = HookRegistry(manifest, package=package)

    artifact = DummyArtifact()
    ctx = HookContext(job=_job(), artifact=artifact)

    registry.call(HookStage.ON_JOB_START, ctx)

    assert artifact.notes and artifact.notes[0]["message"] == "hello"


def test_hook_registry_raises_on_failure(tmp_path: Path):
    package = _install_temp_hook(tmp_path)
    manifest = ManifestContext(
        raw={
            "hooks": {
                "on_job_start": [{"script": "hooks/on_job_start.py"}],
            }
        },
        model=None,
    )
    registry = HookRegistry(manifest, package=package)
    artifact = DummyArtifact()
    ctx = HookContext(job=_job(), artifact=artifact)

    # Monkeypatch the module to throw
    mod = importlib.import_module(f"{package}.hooks.on_job_start")
    mod.run = lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))

    try:
        registry.call(HookStage.ON_JOB_START, ctx)
    except HookExecutionError as exc:
        assert "boom" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("HookExecutionError not raised")
```

# apps/ade-engine/tests/test_main.py
```python
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from ade_engine.__main__ import main


def test_main_version_flag(capsys) -> None:
    code = main(["--version"])
    captured = capsys.readouterr()

    assert code == 0
    assert "ade-engine" in captured.out


def test_main_prints_manifest(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "config_script_api_version": "1",
                "info": {
                    "schema": "ade.manifest/v1.0",
                    "title": "Test",
                    "version": "1.0.0",
                },
                "engine": {
                    "defaults": {"mapping_score_threshold": 0.0},
                    "writer": {
                        "mode": "row_streaming",
                        "append_unmapped_columns": True,
                        "unmapped_prefix": "raw_",
                        "output_sheet": "Normalized",
                    },
                },
                "hooks": {},
                "columns": {
                    "order": ["member_id"],
                    "meta": {
                        "member_id": {
                            "label": "Member ID",
                            "script": "columns/member_id.py",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(["--manifest-path", str(manifest_path)])
    captured = capsys.readouterr()

    assert code == 0
    assert '"config_manifest"' in captured.out


def _build_config_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pkg_root = tmp_path / "cfg"
    config_pkg = pkg_root / "ade_config"
    columns_dir = config_pkg / "columns"
    columns_dir.mkdir(parents=True)
    (config_pkg / "__init__.py").write_text("", encoding="utf-8")
    (columns_dir / "__init__.py").write_text("", encoding="utf-8")

    member_module = textwrap.dedent(
        """
        def detect_from_header(**kwargs):
            header = kwargs.get("header") or ""
            if header.lower() == "member id":
                return {"scores": {kwargs["field_name"]: 1.0}}
            return {"scores": {}}
        """
    )
    (columns_dir / "member_id.py").write_text(member_module, encoding="utf-8")

    manifest = {
        "config_script_api_version": "1",
        "info": {
            "schema": "ade.manifest/v1.0",
            "title": "Test Config",
            "version": "1.0.0",
        },
        "engine": {
            "defaults": {"mapping_score_threshold": 0.0, "detector_sample_size": 4},
            "writer": {
                "mode": "row_streaming",
                "append_unmapped_columns": False,
                "unmapped_prefix": "raw_",
                "output_sheet": "Normalized",
            },
        },
        "hooks": {},
        "columns": {
            "order": ["member_id"],
            "meta": {
                "member_id": {
                    "label": "Member ID",
                    "script": "columns/member_id.py",
                }
            },
        },
        "env": {},
    }

    manifest_path = config_pkg / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.syspath_prepend(str(pkg_root))
    for name in list(sys.modules):
        if name == "ade_config" or name.startswith("ade_config."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    return manifest_path


def test_main_runs_job(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    jobs_dir = tmp_path / "jobs"
    job_dir = jobs_dir / "job-cli"
    input_dir = job_dir / "input"
    logs_dir = job_dir / "logs"
    input_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    (input_dir / "data.csv").write_text("Member ID\n1\n", encoding="utf-8")

    manifest_path = _build_config_package(tmp_path, monkeypatch)

    code = main(
        [
            "--job-id",
            "job-cli",
            "--jobs-dir",
            str(jobs_dir),
            "--manifest-path",
            str(manifest_path),
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert '"status": "succeeded"' in captured.out
```

# apps/ade-engine/tests/test_pipeline_runner_unit.py
```python
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
```

# apps/ade-engine/tests/test_placeholder.py
```python
def test_placeholder() -> None:
    """Temporary smoke test so pytest collections succeed."""

    assert True
```

# apps/ade-engine/tests/test_runtime.py
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ade_engine.runtime import load_config_manifest, load_manifest_context


def test_load_config_manifest_from_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "config_script_api_version": "1",
                "info": {
                    "schema": "ade.manifest/v1.0",
                    "title": "Test Config",
                    "version": "1.0.0",
                },
                "engine": {
                    "defaults": {"mapping_score_threshold": 0.0},
                    "writer": {
                        "mode": "row_streaming",
                        "append_unmapped_columns": True,
                        "unmapped_prefix": "raw_",
                        "output_sheet": "Normalized",
                    },
                },
                "hooks": {},
                "columns": {
                    "order": ["member_id"],
                    "meta": {
                        "member_id": {
                            "label": "Member ID",
                            "script": "columns/member_id.py",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = load_config_manifest(manifest_path=manifest_path)

    assert manifest["info"]["schema"] == "ade.manifest/v1.0"


def test_load_config_manifest_from_package(monkeypatch: Any, tmp_path: Path) -> None:
    package_dir = tmp_path / "fake_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")

    manifest_data = {
        "config_script_api_version": "1",
        "info": {
            "schema": "ade.manifest/v1.0",
            "title": "Test Config",
            "version": "1.0.0",
        },
        "engine": {
            "defaults": {"mapping_score_threshold": 0.0},
            "writer": {
                "mode": "row_streaming",
                "append_unmapped_columns": True,
                "unmapped_prefix": "raw_",
                "output_sheet": "Normalized",
            },
        },
        "hooks": {},
        "columns": {
            "order": ["member_id"],
            "meta": {
                "member_id": {
                    "label": "Member ID",
                    "script": "columns/member_id.py",
                }
            },
        },
    }

    (package_dir / "manifest.json").write_text(
        json.dumps(manifest_data), encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    manifest = load_config_manifest(package="fake_pkg", resource="manifest.json")

    assert manifest["info"]["schema"] == "ade.manifest/v1.0"


def test_load_manifest_context_returns_models(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "config_script_api_version": "1",
                "info": {
                    "schema": "ade.manifest/v1.0",
                    "title": "Test",
                    "version": "1.0.0",
                },
                "engine": {
                    "defaults": {
                        "mapping_score_threshold": 0.6,
                        "detector_sample_size": 10,
                    },
                    "writer": {
                        "mode": "row_streaming",
                        "append_unmapped_columns": True,
                        "unmapped_prefix": "raw_",
                        "output_sheet": "Normalized",
                    },
                },
                "hooks": {},
                "columns": {
                    "order": ["member_id"],
                    "meta": {
                        "member_id": {
                            "label": "Member ID",
                            "script": "columns/member_id.py",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_manifest_context(manifest_path=manifest_path)

    assert context.model is not None
    assert context.column_order == ["member_id"]
    assert context.writer.mode == "row_streaming"


def test_manifest_with_before_save_hooks_validates(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest_with_hooks.json"
    manifest_path.write_text(
        json.dumps(
            {
                "config_script_api_version": "1",
                "info": {
                    "schema": "ade.manifest/v1.0",
                    "title": "Test",
                    "version": "1.0.0",
                },
                "engine": {
                    "defaults": {},
                    "writer": {
                        "mode": "row_streaming",
                        "append_unmapped_columns": True,
                        "unmapped_prefix": "raw_",
                        "output_sheet": "Normalized",
                    },
                },
                "hooks": {
                    "on_before_save": [{"script": "hooks/on_before_save.py"}],
                },
                "columns": {
                    "order": ["member_id"],
                    "meta": {
                        "member_id": {
                            "label": "Member ID",
                            "script": "columns/member_id.py",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_manifest_context(manifest_path=manifest_path)

    assert context.version == "ade.manifest/v1.0"
    assert context.model is not None
```

# apps/ade-engine/tests/test_telemetry.py
```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ade_engine.logging import StructuredLogger
from ade_engine.core.models import JobContext, JobPaths
from ade_engine.telemetry import TelemetryConfig

_PLUGIN_EVENTS: list[tuple[str, dict[str, Any]]] = []


def telemetry_test_sink(job: JobContext, paths: JobPaths):  # pragma: no cover - imported via env
    class _Sink:
        def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
            _PLUGIN_EVENTS.append((event, {"job_id": job.job_id, **payload}))

    return _Sink()


class MemoryArtifact:
    def __init__(self) -> None:
        self.notes: list[tuple[str, dict[str, Any]]] = []

    def start(self, *, job: JobContext, manifest: dict[str, Any]) -> None:  # noqa: D401 - noop
        """Test helper does not persist start payloads."""

    def note(self, message: str, *, level: str = "info", **details: Any) -> None:
        self.notes.append((message, {"level": level, **details}))

    def record_table(self, table: dict[str, Any]) -> None:  # noqa: D401 - noop
        """Test helper does not persist table records."""

    def mark_success(self, *, completed_at, outputs) -> None:  # noqa: D401 - noop
        """Test helper does not persist success payloads."""

    def mark_failure(self, *, completed_at, error) -> None:  # noqa: D401 - noop
        """Test helper does not persist failure payloads."""

    def flush(self) -> None:  # noqa: D401 - noop
        """Test helper does not flush to disk."""


class MemoryEvents:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
        self.events.append((event, {"job_id": job.job_id, **payload}))


class StaticProvider:
    def __init__(self, artifact: MemoryArtifact, events: MemoryEvents) -> None:
        self._artifact = artifact
        self._events = events

    def artifact(self, job: JobContext) -> MemoryArtifact:
        return self._artifact

    def events(self, job: JobContext) -> MemoryEvents:
        return self._events


def _job(tmp_path: Path) -> JobContext:
    paths = JobPaths(
        jobs_root=tmp_path,
        job_dir=tmp_path,
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        artifact_path=tmp_path / "logs" / "artifact.json",
        events_path=tmp_path / "logs" / "events.ndjson",
    )
    return JobContext(
        job_id="job",
        manifest={},
        paths=paths,
        started_at=datetime.now(timezone.utc),
    )


def test_telemetry_config_controls_levels(tmp_path: Path) -> None:
    job = _job(tmp_path)
    artifact = MemoryArtifact()
    events = MemoryEvents()
    config = TelemetryConfig(
        correlation_id="corr-123",
        min_note_level="info",
        min_event_level="warning",
    )
    telemetry = config.bind(job, job.paths, provider=StaticProvider(artifact, events))
    logger = StructuredLogger(job, telemetry)

    logger.note("debug note", level="debug", detail="suppressed")
    logger.note("info note", level="info", detail="kept")
    logger.event("debug_event", level="debug", flag=True)
    logger.event("warn_event", level="warning", flag=True)

    assert all(message != "debug note" for message, _ in artifact.notes)
    note_details = dict(artifact.notes[0][1])
    assert note_details["level"] == "info"
    assert note_details["correlation_id"] == "corr-123"

    assert all(event != "debug_event" for event, _ in events.events)
    event_name, payload = events.events[0]
    assert event_name == "warn_event"
    assert payload["level"] == "warning"
    assert payload["correlation_id"] == "corr-123"


def test_telemetry_config_broadcasts_to_extra_sinks(tmp_path: Path) -> None:
    job = _job(tmp_path)
    artifact = MemoryArtifact()
    events = MemoryEvents()
    captured: list[tuple[str, dict[str, Any]]] = []

    def extra_factory(job: JobContext, paths: JobPaths):
        class _Sink:
            def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
                captured.append((event, {"job_id": job.job_id, **payload}))

        return _Sink()

    config = TelemetryConfig(event_sink_factories=(extra_factory,))
    telemetry = config.bind(job, job.paths, provider=StaticProvider(artifact, events))
    logger = StructuredLogger(job, telemetry)

    logger.event("broadcast", level="info", flag=True)

    assert captured and captured[0][0] == "broadcast"
    assert captured[0][1]["flag"] is True


def test_telemetry_config_loads_env_sinks(tmp_path: Path, monkeypatch) -> None:
    global _PLUGIN_EVENTS
    _PLUGIN_EVENTS = []
    job = _job(tmp_path)
    artifact = MemoryArtifact()
    events = MemoryEvents()

    tests_dir = Path(__file__).parent
    monkeypatch.syspath_prepend(str(tests_dir))
    monkeypatch.setenv(
        "ADE_TELEMETRY_SINKS",
        "test_telemetry:telemetry_test_sink",
    )

    config = TelemetryConfig()
    telemetry = config.bind(job, job.paths, provider=StaticProvider(artifact, events))
    logger = StructuredLogger(job, telemetry)

    logger.event("env_sink", level="info", extra="value")

    assert _PLUGIN_EVENTS and _PLUGIN_EVENTS[0][0] == "env_sink"
    assert _PLUGIN_EVENTS[0][1]["extra"] == "value"
```

# apps/ade-engine/tests/test_worker.py
```python
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import openpyxl
import pytest

from ade_engine.schemas import ADE_TELEMETRY_EVENT_SCHEMA, TelemetryEnvelope

from ade_engine.worker import run_job


def _setup_config_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_hooks: bool = False,
    raising_hook: bool = False,
) -> Path:
    pkg_root = tmp_path / ("config_pkg_hooks" if include_hooks else "config_pkg")
    config_pkg = pkg_root / "ade_config"
    detectors_dir = config_pkg / "columns"
    detectors_dir.mkdir(parents=True)
    (config_pkg / "__init__.py").write_text("", encoding="utf-8")
    (detectors_dir / "__init__.py").write_text("", encoding="utf-8")

    member_module = textwrap.dedent(
        """
        def detect_from_header(**kwargs):
            header = kwargs.get("header") or ""
            if header == "id":
                return {"scores": {kwargs["field_name"]: 1.0}}
            return {"scores": {}}

        def transform(*, value, row, field_name, **_):
            if value is None:
                return None
            normalized = str(value).strip()
            row[field_name] = normalized
            return {field_name: normalized}
        """
    )
    (detectors_dir / "member_id.py").write_text(member_module, encoding="utf-8")

    email_module = textwrap.dedent(
        """
        def detect_from_header(**kwargs):
            header = kwargs.get("header") or ""
            if header == "email":
                return {"scores": {kwargs["field_name"]: 1.0}}
            sample = kwargs.get("column_values_sample", [])
            if any("@" in str(value) for value in sample if value):
                return {"scores": {kwargs["field_name"]: 0.5}}
            return {"scores": {}}

        def transform(*, value, row, field_name, **_):
            if value is None:
                return None
            normalized = str(value).strip().lower()
            row[field_name] = normalized
            return {field_name: normalized}

        def validate(*, value, field_meta=None, row_index, field_name, **_):
            issues = []
            if field_meta and field_meta.get("required") and not value:
                issues.append({"code": "required_missing"})
            if value and "@" not in value:
                issues.append({"code": "invalid_email"})
            for issue in issues:
                issue.setdefault("field", field_name)
                issue.setdefault("row_index", row_index)
            return issues
        """
    )
    (detectors_dir / "email.py").write_text(email_module, encoding="utf-8")

    manifest: dict[str, object] = {
        "config_script_api_version": "1",
        "info": {
            "schema": "ade.manifest/v1.0",
            "title": "Test Config",
            "version": "1.0.0",
        },
        "engine": {
            "defaults": {
                "mapping_score_threshold": 0.25,
                "detector_sample_size": 8,
            },
            "writer": {
                "mode": "row_streaming",
                "append_unmapped_columns": True,
                "unmapped_prefix": "raw_",
                "output_sheet": "Normalized",
            },
        },
        "hooks": {},
        "columns": {
            "order": ["member_id", "email"],
            "meta": {
                "member_id": {
                    "label": "Member ID",
                    "synonyms": ["ID"],
                    "script": "columns/member_id.py",
                },
                "email": {
                    "label": "Email",
                    "required": True,
                    "script": "columns/email.py",
                },
            },
        },
        "env": {},
    }

    if include_hooks:
        hooks_dir = config_pkg / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "__init__.py").write_text("", encoding="utf-8")
        start_hook = "def run(*, artifact, **_):\n    artifact.note('start hook')\n"
        if raising_hook:
            start_hook += "    raise RuntimeError('boom')\n"
        (hooks_dir / "on_job_start.py").write_text(start_hook, encoding="utf-8")
        (hooks_dir / "on_job_end.py").write_text(
            "def run(*, artifact, result, **_):\n    artifact.note('end hook', status=result.status)\n",
            encoding="utf-8",
        )
        manifest["hooks"] = {
            "on_job_start": [{"script": "hooks/on_job_start.py"}],
            "on_job_end": [{"script": "hooks/on_job_end.py"}],
        }

    manifest_path = config_pkg / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.syspath_prepend(str(pkg_root))
    for name in list(sys.modules):
        if name == "ade_config" or name.startswith("ade_config."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    return manifest_path


def test_run_job_normalizes_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = _setup_config_package(tmp_path, monkeypatch)

    jobs_dir = tmp_path / "jobs"
    job_dir = jobs_dir / "job-1"
    input_dir = job_dir / "input"
    logs_dir = job_dir / "logs"
    input_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    csv_path = input_dir / "employees.csv"
    csv_path.write_text(
        "ID,Email,Name\n123,USER@EXAMPLE.COM,Alice\n456,invalid,Bob\n",
        encoding="utf-8",
    )

    result = run_job(
        "job-1",
        jobs_dir=jobs_dir,
        manifest_path=manifest_path,
        config_package="ade_config",
    )

    assert result.status == "succeeded"
    assert result.processed_files == ("employees.csv",)
    workbook = openpyxl.load_workbook(result.output_paths[0], read_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0] == ("Member ID", "Email", "raw_name")
    assert rows[1][:2] == ("123", "user@example.com")
    assert rows[2][1] == "invalid"
    workbook.close()

    artifact = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert artifact["job"]["status"] == "succeeded"
    table = artifact["tables"][0]
    assert table["mapping"][0]["field"] == "member_id"
    assert any(entry["code"] == "invalid_email" for entry in table["validation"])

    envelopes = [
        TelemetryEnvelope.model_validate_json(line)
        for line in result.events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all(envelope.schema == ADE_TELEMETRY_EVENT_SCHEMA for envelope in envelopes)
    assert any(env.event.name == "job_started" for env in envelopes)
    assert any(env.event.name == "job_completed" for env in envelopes)
    assert any(env.event.name == "validation_issue" for env in envelopes)


def test_hooks_are_executed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = _setup_config_package(tmp_path, monkeypatch, include_hooks=True)

    jobs_dir = tmp_path / "jobs"
    job_dir = jobs_dir / "job-2"
    input_dir = job_dir / "input"
    logs_dir = job_dir / "logs"
    input_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    (input_dir / "data.csv").write_text("ID\n42\n", encoding="utf-8")

    result = run_job(
        "job-2",
        jobs_dir=jobs_dir,
        manifest_path=manifest_path,
        config_package="ade_config",
    )

    assert result.status == "succeeded"
    artifact = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    notes = [entry["message"] for entry in artifact["notes"]]
    assert "start hook" in notes
    assert any(
        entry["message"] == "end hook" and entry.get("details", {}).get("status") == "succeeded"
        for entry in artifact["notes"]
    )


def test_run_job_reports_failure_when_hook_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = _setup_config_package(tmp_path, monkeypatch, include_hooks=True, raising_hook=True)

    jobs_dir = tmp_path / "jobs"
    job_dir = jobs_dir / "job-3"
    input_dir = job_dir / "input"
    logs_dir = job_dir / "logs"
    input_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    (input_dir / "data.csv").write_text("ID\n42\n", encoding="utf-8")

    result = run_job(
        "job-3",
        jobs_dir=jobs_dir,
        manifest_path=manifest_path,
        config_package="ade_config",
    )

    assert result.status == "failed"
    assert result.output_paths == ()
    assert result.error
    artifact = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert artifact["job"]["status"] == "failed"
```
