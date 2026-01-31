"""Garbage collection for environments and run artifacts."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, text
from sqlalchemy.orm import Session, sessionmaker

from . import db
from .paths import PathManager
from .schema import environments, runs
from .settings import Settings, get_settings

logger = logging.getLogger("ade_worker.gc")


@dataclass(slots=True)
class GcResult:
    scanned: int = 0
    deleted: int = 0
    skipped: int = 0
    failed: int = 0


def gc_environments(
    *,
    SessionLocal: sessionmaker[Session],
    paths: PathManager,
    now: datetime,
    env_ttl_days: int,
) -> GcResult:
    result = GcResult()
    ttl_days = int(env_ttl_days)
    if ttl_days <= 0:
        return result

    cutoff = now - timedelta(days=ttl_days)
    query = text(
        """
        SELECT
            e.id,
            e.workspace_id,
            e.configuration_id,
            e.engine_spec,
            e.deps_digest,
            e.status,
            e.last_used_at,
            e.updated_at
        FROM environments AS e
        JOIN configurations AS c ON c.id = e.configuration_id
        WHERE c.status != 'active'
          AND e.status IN ('ready', 'failed')
          AND (
            (e.last_used_at IS NOT NULL AND e.last_used_at < :cutoff)
            OR (e.last_used_at IS NULL AND e.updated_at < :cutoff)
          )
          AND NOT EXISTS (
            SELECT 1
            FROM runs AS r
            WHERE r.workspace_id = e.workspace_id
              AND r.configuration_id = e.configuration_id
              AND r.engine_spec = e.engine_spec
              AND r.deps_digest = e.deps_digest
              AND r.status IN ('queued', 'running')
          )
        ORDER BY COALESCE(e.last_used_at, e.updated_at) ASC
        """
    )

    with SessionLocal() as session:
        rows = session.execute(query, {"cutoff": cutoff}).mappings().all()

    result.scanned = len(rows)
    for row in rows:
        env_id = row["id"]
        env_path = paths.environment_root(
            row["workspace_id"],
            row["configuration_id"],
            row["deps_digest"],
            env_id,
        )
        if not _delete_tree(env_path):
            logger.warning(
                "gc: environment delete failed env_id=%s path=%s",
                env_id,
                env_path,
            )
            result.failed += 1
            continue

        with SessionLocal.begin() as session:
            deleted = session.execute(
                delete(environments).where(environments.c.id == env_id)
            ).rowcount or 0
        if deleted:
            result.deleted += 1
            logger.info(
                "gc: environment deleted env_id=%s status=%s cutoff=%s",
                env_id,
                row["status"],
                cutoff.isoformat(),
            )
        else:
            result.skipped += 1
            logger.info(
                "gc: environment already removed env_id=%s",
                env_id,
            )

    return result


def gc_run_artifacts(
    *,
    SessionLocal: sessionmaker[Session],
    paths: PathManager,
    now: datetime,
    run_ttl_days: int,
) -> GcResult:
    result = GcResult()
    ttl_days = int(run_ttl_days)
    if ttl_days <= 0:
        return result

    cutoff = now - timedelta(days=ttl_days)
    query = text(
        """
        SELECT id, workspace_id, completed_at
        FROM runs
        WHERE status IN ('succeeded', 'failed')
          AND completed_at IS NOT NULL
          AND completed_at < :cutoff
        """
    )

    with SessionLocal() as session:
        rows = session.execute(query, {"cutoff": cutoff}).mappings().all()

    result.scanned = len(rows)
    for row in rows:
        run_id = row["id"]
        run_path = paths.run_dir(row["workspace_id"], run_id)
        if not _delete_tree(run_path):
            logger.warning("gc: run artifact delete failed run_id=%s path=%s", run_id, run_path)
            result.failed += 1
            continue
        result.deleted += 1
        logger.info(
            "gc: run artifacts deleted run_id=%s completed_at=%s",
            run_id,
            row["completed_at"],
        )

    return result


def _delete_tree(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        shutil.rmtree(path)
        return True
    except FileNotFoundError:
        return True
    except Exception:
        logger.exception("gc: failed to delete path %s", path)
    return False


def run_gc(settings: Settings | None = None) -> tuple[GcResult, GcResult | None]:
    settings = settings or get_settings()
    engine = db.build_engine(settings)
    SessionLocal = db.build_sessionmaker(engine)
    paths = PathManager(settings.data_dir, settings.venvs_dir, settings.worker_runs_dir)
    now = datetime.utcnow().replace(tzinfo=None)

    env_result = gc_environments(
        SessionLocal=SessionLocal,
        paths=paths,
        now=now,
        env_ttl_days=settings.worker_env_ttl_days,
    )

    run_result: GcResult | None = None
    if settings.worker_run_artifact_ttl_days is not None:
        run_result = gc_run_artifacts(
            SessionLocal=SessionLocal,
            paths=paths,
            now=now,
            run_ttl_days=settings.worker_run_artifact_ttl_days,
        )

    engine.dispose()
    return env_result, run_result


__all__ = ["gc_environments", "gc_run_artifacts", "GcResult", "run_gc"]
