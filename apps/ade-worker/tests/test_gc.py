from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.orm import sessionmaker

from ade_worker.gc import gc_environments
from ade_worker.paths import PathManager
from ade_worker.schema import environments, metadata, runs


def _create_config_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE configurations ("
                "id TEXT PRIMARY KEY, "
                "status TEXT NOT NULL"
                ")"
            )
        )


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
                claimed_by=None,
                claim_expires_at=None,
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
    with engine.begin() as conn:
        conn.execute(
            insert(runs).values(
                id=run_id,
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                input_document_id="doc-1",
                input_sheet_names=None,
                run_options=None,
                output_path=None,
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


def _make_env_dir(paths: PathManager, *, workspace_id: str, configuration_id: str, deps_digest: str, env_id: str) -> Path:
    env_path = paths.environment_root(workspace_id, configuration_id, deps_digest, env_id)
    env_path.mkdir(parents=True, exist_ok=True)
    (env_path / "marker.txt").write_text("env")
    return env_path


def _engine() -> object:
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    _create_config_table(engine)
    return engine


def test_gc_env_skips_when_run_active(tmp_path: Path) -> None:
    engine = _engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    paths = PathManager(tmp_path / "data", tmp_path / "data" / "venvs")

    _insert_configuration(engine, config_id="cfg-1", status="draft")
    _insert_environment(
        engine,
        env_id="env-1",
        workspace_id="ws-1",
        configuration_id="cfg-1",
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:abc",
        status="ready",
        now=now,
        last_used_at=now - timedelta(days=10),
    )
    _insert_run(
        engine,
        run_id="run-1",
        workspace_id="ws-1",
        configuration_id="cfg-1",
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:abc",
        status="running",
        now=now,
    )
    env_path = _make_env_dir(
        paths,
        workspace_id="ws-1",
        configuration_id="cfg-1",
        deps_digest="sha256:abc",
        env_id="env-1",
    )

    result = gc_environments(SessionLocal=SessionLocal, paths=paths, now=now, env_ttl_days=1)

    assert result.deleted == 0
    assert env_path.exists()
    with engine.begin() as conn:
        row = conn.execute(select(environments.c.id).where(environments.c.id == "env-1")).first()
    assert row is not None


def test_gc_env_deletes_cold_non_active(tmp_path: Path) -> None:
    engine = _engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    paths = PathManager(tmp_path / "data", tmp_path / "data" / "venvs")

    _insert_configuration(engine, config_id="cfg-2", status="archived")
    _insert_environment(
        engine,
        env_id="env-2",
        workspace_id="ws-2",
        configuration_id="cfg-2",
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:def",
        status="ready",
        now=now,
        last_used_at=now - timedelta(days=45),
    )
    env_path = _make_env_dir(
        paths,
        workspace_id="ws-2",
        configuration_id="cfg-2",
        deps_digest="sha256:def",
        env_id="env-2",
    )

    result = gc_environments(SessionLocal=SessionLocal, paths=paths, now=now, env_ttl_days=30)

    assert result.deleted == 1
    assert not env_path.exists()
    with engine.begin() as conn:
        row = conn.execute(select(environments.c.id).where(environments.c.id == "env-2")).first()
    assert row is None


def test_gc_env_idempotent(tmp_path: Path) -> None:
    engine = _engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    paths = PathManager(tmp_path / "data", tmp_path / "data" / "venvs")

    _insert_configuration(engine, config_id="cfg-3", status="draft")
    _insert_environment(
        engine,
        env_id="env-3",
        workspace_id="ws-3",
        configuration_id="cfg-3",
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:ghi",
        status="failed",
        now=now,
        last_used_at=None,
    )
    _make_env_dir(
        paths,
        workspace_id="ws-3",
        configuration_id="cfg-3",
        deps_digest="sha256:ghi",
        env_id="env-3",
    )

    first = gc_environments(SessionLocal=SessionLocal, paths=paths, now=now, env_ttl_days=1)
    second = gc_environments(SessionLocal=SessionLocal, paths=paths, now=now, env_ttl_days=1)

    assert first.deleted == 1
    assert second.deleted == 0
