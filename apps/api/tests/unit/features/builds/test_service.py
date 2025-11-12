from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.app.features.builds.builder import BuildArtifacts
from apps.api.app.features.builds.exceptions import BuildAlreadyInProgressError
from apps.api.app.features.builds.models import BuildStatus, ConfigurationBuild
from apps.api.app.features.builds.service import BuildEnsureMode, BuildsService
from apps.api.app.features.configs.models import Configuration, ConfigurationStatus
from apps.api.app.features.configs.storage import ConfigStorage
from apps.api.app.features.workspaces.models import Workspace
from apps.api.app.settings import Settings
from apps.api.app.shared.core.time import utc_now
from apps.api.app.shared.db import Base
from apps.api.app.shared.db.mixins import generate_ulid


@dataclass
class BuilderCall:
    build_id: str
    workspace_id: str
    config_id: str
    target_path: Path


class FakeBuilder:
    """Test double for ``VirtualEnvironmentBuilder`` that avoids pip installs."""

    def __init__(self, *, engine_version: str = "0.1.0", python_version: str = "3.12.1") -> None:
        self.engine_version = engine_version
        self.python_version = python_version
        self.calls: list[BuilderCall] = []

    async def build(
        self,
        *,
        build_id: str,
        workspace_id: str,
        config_id: str,
        target_path: Path,
        config_path: Path,
        engine_spec: str,
        pip_cache_dir: Path | None,
        python_bin: str | None,
        timeout: float,
    ) -> BuildArtifacts:
        target_path.mkdir(parents=True, exist_ok=True)
        self.calls.append(
            BuilderCall(
                build_id=build_id,
                workspace_id=workspace_id,
                config_id=config_id,
                target_path=target_path,
            )
        )
        return BuildArtifacts(
            python_version=self.python_version,
            engine_version=self.engine_version,
        )


class TimeStub:
    """Mutable callable returning deterministic timestamps for the service."""

    def __init__(self, initial: datetime | None = None) -> None:
        self.current = initial or datetime.now(tz=UTC)

    def advance(self, delta: timedelta) -> None:
        self.current += delta

    def __call__(self) -> datetime:
        return self.current


@pytest.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture()
def service_factory(tmp_path: Path) -> Callable[[AsyncSession, dict[str, Any], FakeBuilder, Callable[[], datetime]], BuildsService]:
    def _factory(
        session: AsyncSession,
        overrides: dict[str, Any] | None = None,
        builder: FakeBuilder | None = None,
        now: Callable[[], datetime] = utc_now,
    ) -> BuildsService:
        base_settings = Settings()
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(parents=True, exist_ok=True)
        (engine_dir / "pyproject.toml").write_text(
            """
[project]
name = "ade-engine"
version = "0.1.0"
""".strip(),
            encoding="utf-8",
        )
        configs_dir = tmp_path / "configs"
        venvs_dir = tmp_path / "venvs"
        pip_cache_dir = tmp_path / "pip-cache"
        overrides = overrides or {}
        settings = base_settings.model_copy(
            update={
                "configs_dir": configs_dir,
                "venvs_dir": venvs_dir,
                "pip_cache_dir": pip_cache_dir,
                "engine_spec": str(engine_dir),
                **overrides,
            }
        )
        (tmp_path / "templates").mkdir(parents=True, exist_ok=True)
        storage = ConfigStorage(
            templates_root=tmp_path / "templates",
            configs_root=settings.configs_dir,
        )
        builder = builder or FakeBuilder()
        return BuildsService(
            session=session,
            settings=settings,
            storage=storage,
            builder=builder,
            now=now,
        )

    return _factory


async def _prepare_configuration(
    session: AsyncSession,
    *,
    workspace_id: str | None = None,
    config_id: str | None = None,
    status: ConfigurationStatus = ConfigurationStatus.ACTIVE,
    config_version: int = 1,
    content_digest: str | None = "digest",
) -> tuple[str, str, str]:
    workspace = Workspace(name="Acme", slug=f"acme-{generate_ulid().lower()}")
    session.add(workspace)
    await session.flush()
    workspace_id = workspace.id if workspace_id is None else workspace_id
    config = Configuration(
        workspace_id=workspace_id,
        config_id=config_id or generate_ulid(),
        display_name="Config",
        status=status,
        config_version=config_version,
        content_digest=content_digest,
    )
    session.add(config)
    await session.flush()
    return workspace_id, config.config_id, config.id


async def _ensure_config_path(root: Path, workspace_id: str, config_id: str) -> Path:
    config_path = root / workspace_id / "config_packages" / config_id
    config_path.mkdir(parents=True, exist_ok=True)
    return config_path


@pytest.mark.asyncio()
async def test_ensure_build_creates_new_build(session: AsyncSession, tmp_path: Path, service_factory) -> None:
    workspace_id, config_id, configuration_db_id = await _prepare_configuration(session)
    await _ensure_config_path(tmp_path / "configs", workspace_id, config_id)

    builder = FakeBuilder(engine_version="1.0.0", python_version="3.12.0")
    service = service_factory(
        session,
        builder=builder,
        now=utc_now,
    )

    result = await service.ensure_build(
        workspace_id=workspace_id,
        config_id=config_id,
    )

    assert result.status is BuildStatus.ACTIVE
    assert result.just_built is True
    assert result.build is not None
    assert result.build.engine_version == "1.0.0"
    assert result.build.python_version == "3.12.0"
    assert builder.calls and builder.calls[0].build_id == result.build.build_id


@pytest.mark.asyncio()
async def test_ensure_build_reuses_active(session: AsyncSession, tmp_path: Path, service_factory) -> None:
    workspace_id, config_id, _ = await _prepare_configuration(session)
    await _ensure_config_path(tmp_path / "configs", workspace_id, config_id)

    builder = FakeBuilder()
    service = service_factory(session, builder=builder)

    first = await service.ensure_build(workspace_id=workspace_id, config_id=config_id)
    assert first.just_built is True
    assert len(builder.calls) == 1

    second = await service.ensure_build(workspace_id=workspace_id, config_id=config_id)
    assert second.just_built is False
    assert second.build is not None
    assert second.build.build_id == first.build.build_id
    assert len(builder.calls) == 1


@pytest.mark.asyncio()
async def test_ensure_build_honours_ttl(session: AsyncSession, tmp_path: Path, service_factory) -> None:
    workspace_id, config_id, configuration_db_id = await _prepare_configuration(session)
    await _ensure_config_path(tmp_path / "configs", workspace_id, config_id)

    clock = TimeStub(datetime(2024, 1, 1, tzinfo=UTC))
    builder = FakeBuilder()
    service = service_factory(
        session,
        overrides={"build_ttl": timedelta(seconds=30)},
        builder=builder,
        now=clock,
    )

    first = await service.ensure_build(workspace_id=workspace_id, config_id=config_id)
    assert first.just_built is True
    clock.advance(timedelta(seconds=31))

    second = await service.ensure_build(workspace_id=workspace_id, config_id=config_id)
    assert second.just_built is True
    assert len(builder.calls) == 2


@pytest.mark.asyncio()
async def test_ensure_build_returns_building_when_in_progress(
    session: AsyncSession, tmp_path: Path, service_factory
) -> None:
    workspace_id, config_id, configuration_db_id = await _prepare_configuration(session)
    await _ensure_config_path(tmp_path / "configs", workspace_id, config_id)

    building = ConfigurationBuild(
        workspace_id=workspace_id,
        config_id=config_id,
        configuration_id=configuration_db_id,
        build_id=generate_ulid(),
        status=BuildStatus.BUILDING,
        venv_path=str(tmp_path / "venvs" / workspace_id / config_id / "build"),
        config_version=1,
        content_digest="digest",
        engine_spec="spec",
        engine_version="0.1.0",
        python_interpreter=str(Path(sys.executable).resolve()),
        started_at=datetime.now(tz=UTC),
    )
    session.add(building)
    await session.commit()

    service = service_factory(session)
    result = await service.ensure_build(
        workspace_id=workspace_id,
        config_id=config_id,
        mode=BuildEnsureMode.INTERACTIVE,
    )
    assert result.status is BuildStatus.BUILDING
    assert result.build is None


@pytest.mark.asyncio()
async def test_ensure_build_blocks_and_times_out(session: AsyncSession, tmp_path: Path, service_factory) -> None:
    workspace_id, config_id, _ = await _prepare_configuration(session)
    await _ensure_config_path(tmp_path / "configs", workspace_id, config_id)

    building = ConfigurationBuild(
        workspace_id=workspace_id,
        config_id=config_id,
        configuration_id=configuration_db_id,
        build_id=generate_ulid(),
        status=BuildStatus.BUILDING,
        venv_path=str(tmp_path / "venvs" / workspace_id / config_id / "build"),
        config_version=1,
        content_digest="digest",
        engine_spec="spec",
        engine_version="0.1.0",
        python_interpreter=str(Path(sys.executable).resolve()),
        started_at=datetime.now(tz=UTC),
    )
    session.add(building)
    await session.commit()

    service = service_factory(
        session,
        overrides={"build_ensure_wait": timedelta(seconds=0)},
    )

    with pytest.raises(BuildAlreadyInProgressError):
        await service.ensure_build(
            workspace_id=workspace_id,
            config_id=config_id,
            mode=BuildEnsureMode.BLOCKING,
        )


@pytest.mark.asyncio()
async def test_delete_active_build_removes_row_and_directory(
    session: AsyncSession, tmp_path: Path, service_factory
) -> None:
    workspace_id, config_id, _ = await _prepare_configuration(session)
    config_root = tmp_path / "configs"
    await _ensure_config_path(config_root, workspace_id, config_id)

    builder = FakeBuilder()
    service = service_factory(session, builder=builder)

    result = await service.ensure_build(workspace_id=workspace_id, config_id=config_id)
    assert result.build is not None
    venv_path = Path(result.build.venv_path)
    assert venv_path.exists()

    await service.delete_active_build(workspace_id=workspace_id, config_id=config_id)
    lookup = await session.get(
        ConfigurationBuild,
        (workspace_id, config_id, result.build.build_id),
    )
    assert lookup is None
    assert not venv_path.exists()
