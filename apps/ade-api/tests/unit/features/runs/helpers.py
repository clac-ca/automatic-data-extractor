from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from ade_api.common.events import EventRecord
from ade_api.common.time import utc_now
from ade_api.db.mixins import generate_uuid7
from ade_api.features.builds.service import BuildDecision, BuildExecutionContext
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.runs.service import RunsService
from ade_api.features.system_settings.service import SafeModeService
from ade_api.infra.storage import workspace_config_root, workspace_documents_root
from ade_api.models import (
    Build,
    BuildStatus,
    Configuration,
    ConfigurationStatus,
    Document,
    DocumentSource,
    DocumentStatus,
    Workspace,
)
from ade_api.settings import Settings


class FakeBuildsService:
    """Minimal build service stub used to avoid real env creation."""

    def __init__(
        self,
        *,
        session,
        build: Build,
        context: BuildExecutionContext | None,
        events: list[EventRecord] | None,
        venv_path: Path,
    ) -> None:
        self._session = session
        self.build = build
        self.context = context
        self.events = events or []
        self.venv_path = venv_path
        self.force_calls: list[bool] = []

    async def ensure_build_for_run(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        force_rebuild: bool,
        run_id,
        reason: str = "on_demand",
    ) -> tuple[Build, BuildExecutionContext | None]:
        self.force_calls.append(bool(force_rebuild))
        return self.build, self.context

    async def stream_build(self, *, context, options) -> AsyncIterator[EventRecord]:
        for event in self.events:
            yield event
        self.build.status = BuildStatus.READY
        self.build.exit_code = 0
        await self._session.commit()

    async def stream_build_events(
        self,
        *,
        build: Build,
        start_sequence: int | None = None,  # noqa: ARG002
        timeout_seconds: float | None = None,  # noqa: ARG002
    ) -> AsyncIterator[EventRecord]:
        for event in self.events:
            yield event
        build.status = BuildStatus.READY
        build.exit_code = 0
        await self._session.commit()

    async def launch_build_if_needed(
        self,
        *,
        build: Build,  # noqa: ARG002
        reason: str | None = None,  # noqa: ARG002
        run_id=None,  # noqa: ANN001,ARG002
    ) -> None:
        return None

    async def get_build_or_raise(self, build_id: str, workspace_id: str | None = None) -> Build:
        return self.build

    async def ensure_local_env(self, *, build: Build) -> Path:
        from ade_api.infra.venv import venv_python_path

        self.venv_path.parent.mkdir(parents=True, exist_ok=True)
        self.venv_path.mkdir(parents=True, exist_ok=True)
        python_path = venv_python_path(self.venv_path, must_exist=False)
        python_path.parent.mkdir(parents=True, exist_ok=True)
        python_path.write_text("", encoding="utf-8")
        return self.venv_path

    def event_log_reader(self, *_, **__):
        class _Reader:
            def iter(self, after_sequence: int = 0):
                return []

        return _Reader()

    @asynccontextmanager
    async def subscribe_to_events(self, *_args, **_kwargs):
        yield iter(())


async def build_runs_service(
    session,
    tmp_path: Path,
    *,
    safe_mode: bool = False,
    build_status: BuildStatus = BuildStatus.READY,
    build_decision: BuildDecision = BuildDecision.START_NEW,
    build_events: list[EventRecord] | None = None,
) -> tuple[RunsService, Configuration, Document, FakeBuildsService, Settings]:
    data_root = tmp_path / "data"
    settings = Settings(
        workspaces_dir=data_root / "workspaces",
        documents_dir=data_root / "workspaces",
        runs_dir=data_root / "workspaces",
        venvs_dir=data_root / "venvs",
        pip_cache_dir=data_root / "cache" / "pip",
        safe_mode=safe_mode,
    )

    workspace = Workspace(name="Test Workspace", slug=f"ws-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    await session.flush()

    configuration = Configuration(
        workspace_id=workspace.id,
        display_name="Demo Config",
        status=ConfigurationStatus.ACTIVE,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=build_status,
        created_at=utc_now(),
        fingerprint="fingerprint",
    )
    session.add(build)
    configuration.active_build_id = build.id
    await session.flush()

    config_root = workspace_config_root(settings, workspace.id, configuration.id)
    config_root.mkdir(parents=True, exist_ok=True)
    venv_root = Path(settings.venvs_dir) / "demo-venv"
    build_ctx = BuildExecutionContext(
        build_id=build.id,
        configuration_id=configuration.id,
        workspace_id=workspace.id,
        config_path=str(config_root),
        venv_root=str(venv_root),
        python_bin=None,
        engine_spec="engine-spec",
        engine_version_hint=None,
        pip_cache_dir=None,
        timeout_seconds=30.0,
        decision=build_decision,
        fingerprint="fp",
        run_id=None,
        reuse_summary=None,
        reason=None,
    )
    if build_status is BuildStatus.READY:
        build_ctx = None

    doc_storage = DocumentStorage(workspace_documents_root(settings, workspace.id))
    document_id = generate_uuid7()
    stored_uri = doc_storage.make_stored_uri(str(document_id))
    document_path = doc_storage.path_for(stored_uri)
    document_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.write_text("name\nAlice\n", encoding="utf-8")

    document = Document(
        id=document_id,
        workspace_id=workspace.id,
        original_filename="input.csv",
        content_type="text/csv",
        byte_size=document_path.stat().st_size,
        sha256="deadbeef",
        stored_uri=stored_uri,
        attributes={},
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add(document)
    await session.commit()

    safe_mode_service = SafeModeService(session=session, settings=settings)
    service = RunsService(
        session=session,
        settings=settings,
        safe_mode_service=safe_mode_service,
    )
    fake_builds = FakeBuildsService(
        session=session,
        build=build,
        context=build_ctx,
        events=build_events,
        venv_path=venv_root / ".venv",
    )
    service._builds_service = fake_builds  # type: ignore[attr-defined]

    return service, configuration, document, fake_builds, settings
