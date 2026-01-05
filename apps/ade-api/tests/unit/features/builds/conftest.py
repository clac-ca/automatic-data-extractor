from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ade_api.db import Base
from ade_api.features.builds.service import BuildsService
from ade_api.features.configs.storage import ConfigStorage
from ade_api.settings import Settings


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    base_settings = Settings()
    workspaces_dir = tmp_path / "workspaces"
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir(parents=True, exist_ok=True)
    (engine_dir / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                "name = \"ade-engine\"",
                "version = \"1.6.1\"",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pip_cache_dir = tmp_path / "pip-cache"
    return base_settings.model_copy(
        update={
            "workspaces_dir": workspaces_dir,
            "configs_dir": workspaces_dir,
            "venvs_dir": tmp_path / "venvs",
            "pip_cache_dir": pip_cache_dir,
            "engine_spec": str(engine_dir),
        }
    )


@pytest.fixture()
def storage(settings: Settings) -> ConfigStorage:
    return ConfigStorage(settings=settings)


@pytest.fixture()
def service(session: AsyncSession, settings: Settings, storage: ConfigStorage) -> BuildsService:
    return BuildsService(session=session, settings=settings, storage=storage)
