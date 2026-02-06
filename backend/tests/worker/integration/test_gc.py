from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import insert, select, text
from sqlalchemy.orm import sessionmaker

from ade_db.schema import environments, runs
from ade_worker.gc import gc_environments
from ade_worker.paths import PathManager
from .helpers import seed_file_with_version


class _Layout:
    def __init__(self, root: Path, runs_root: Path | None = None) -> None:
        self.workspaces_dir = root / "workspaces"
        self.configs_dir = self.workspaces_dir
        self.documents_dir = self.workspaces_dir
        self.runs_dir = runs_root or (root / "runs")
        self.venvs_dir = root / "venvs"
        self.pip_cache_dir = root / "cache" / "pip"


def _uuid() -> str:
    return str(uuid4())


def _create_config_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS configurations ("
                "id UUID PRIMARY KEY, "
                "status TEXT NOT NULL"
                ")"
            )
        )
        conn.execute(text("DELETE FROM configurations"))


def _insert_configuration(engine, *, config_id: str, status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO configurations (id, status) VALUES (:id, :status)"),
            {"id": config_id, "status": status},
        )


def _insert_environment(
    engine,
    *,
    env_id: str,
    workspace_id: str,
    configuration_id: str,
    engine_spec: str,
    deps_digest: str,
    status: str,
    now: datetime,
    last_used_at: datetime | None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(environments).values(
                id=env_id,
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                engine_spec=engine_spec,
                deps_digest=deps_digest,
                status=status,
                error_message=None,
                created_at=now - timedelta(days=40),
                updated_at=now - timedelta(days=40),
                last_used_at=last_used_at,
                python_version=None,
                python_interpreter=None,
                engine_version=None,
            )
        )


def _insert_run(
    engine,
    *,
    run_id: str,
    workspace_id: str,
    configuration_id: str,
    engine_spec: str,
    deps_digest: str,
    status: str,
    now: datetime,
) -> None:
    _, input_file_version_id = seed_file_with_version(
        engine,
        workspace_id=workspace_id,
        now=now,
    )
    with engine.begin() as conn:
        conn.execute(
            insert(runs).values(
                id=run_id,
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                input_file_version_id=input_file_version_id,
                output_file_version_id=None,
                input_sheet_names=None,
                run_options=None,
                engine_spec=engine_spec,
                deps_digest=deps_digest,
                status=status,
                available_at=now - timedelta(minutes=1),
                attempt_count=0,
                max_attempts=3,
                claimed_by=None,
                claim_expires_at=None,
                exit_code=None,
                error_message=None,
                created_at=now - timedelta(minutes=5),
                started_at=None,
                completed_at=None,
            )
        )


def _make_env_dir(
    paths: PathManager,
    *,
    workspace_id: str,
    configuration_id: str,
    deps_digest: str,
    env_id: str,
) -> Path:
    env_path = paths.environment_root(workspace_id, configuration_id, deps_digest, env_id)
    env_path.mkdir(parents=True, exist_ok=True)
    (env_path / "marker.txt").write_text("env")
    return env_path


def test_gc_env_skips_when_run_active(engine, tmp_path: Path) -> None:
    _create_config_table(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    data_root = tmp_path / "data"
    layout = _Layout(data_root, tmp_path / "runs")
    paths = PathManager(layout, layout.pip_cache_dir)

    workspace_id = _uuid()
    configuration_id = _uuid()
    env_id = _uuid()
    run_id = _uuid()

    _insert_configuration(engine, config_id=configuration_id, status="draft")
    _insert_environment(
        engine,
        env_id=env_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@v1.7.9",
        deps_digest="sha256:abc",
        status="ready",
        now=now,
        last_used_at=now - timedelta(days=10),
    )
    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@v1.7.9",
        deps_digest="sha256:abc",
        status="running",
        now=now,
    )
    env_path = _make_env_dir(
        paths,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:abc",
        env_id=env_id,
    )

    result = gc_environments(session_factory=session_factory, paths=paths, now=now, env_ttl_days=1)

    assert result.deleted == 0
    assert env_path.exists()
    with engine.begin() as conn:
        row = conn.execute(select(environments.c.id).where(environments.c.id == env_id)).first()
    assert row is not None


def test_gc_env_deletes_cold_non_active(engine, tmp_path: Path) -> None:
    _create_config_table(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    data_root = tmp_path / "data"
    layout = _Layout(data_root, tmp_path / "runs")
    paths = PathManager(layout, layout.pip_cache_dir)

    workspace_id = _uuid()
    configuration_id = _uuid()
    env_id = _uuid()

    _insert_configuration(engine, config_id=configuration_id, status="archived")
    _insert_environment(
        engine,
        env_id=env_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@v1.7.9",
        deps_digest="sha256:def",
        status="ready",
        now=now,
        last_used_at=now - timedelta(days=45),
    )
    env_path = _make_env_dir(
        paths,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:def",
        env_id=env_id,
    )

    result = gc_environments(session_factory=session_factory, paths=paths, now=now, env_ttl_days=30)

    assert result.deleted == 1
    assert not env_path.exists()
    with engine.begin() as conn:
        row = conn.execute(select(environments.c.id).where(environments.c.id == env_id)).first()
    assert row is None


def test_gc_env_idempotent(engine, tmp_path: Path) -> None:
    _create_config_table(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    data_root = tmp_path / "data"
    layout = _Layout(data_root, tmp_path / "runs")
    paths = PathManager(layout, layout.pip_cache_dir)

    workspace_id = _uuid()
    configuration_id = _uuid()
    env_id = _uuid()

    _insert_configuration(engine, config_id=configuration_id, status="draft")
    _insert_environment(
        engine,
        env_id=env_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@v1.7.9",
        deps_digest="sha256:ghi",
        status="failed",
        now=now,
        last_used_at=None,
    )
    _make_env_dir(
        paths,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:ghi",
        env_id=env_id,
    )

    first = gc_environments(session_factory=session_factory, paths=paths, now=now, env_ttl_days=1)
    second = gc_environments(session_factory=session_factory, paths=paths, now=now, env_ttl_days=1)

    assert first.deleted == 1
    assert second.deleted == 0
