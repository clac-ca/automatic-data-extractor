"""Garbage collection for environments and run artifacts."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, text

from .paths import PathManager
from .schema import environments, runs

logger = logging.getLogger("ade_worker.gc")


@dataclass(slots=True)
class GcResult:
    scanned: int = 0
    deleted: int = 0
    skipped: int = 0
    failed: int = 0


def gc_environments(*, engine, paths: PathManager, now: datetime, env_ttl_days: int) -> GcResult:
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
          AND (e.claim_expires_at IS NULL OR e.claim_expires_at <= :now)
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

    with engine.begin() as conn:
        rows = conn.execute(query, {"cutoff": cutoff, "now": now}).mappings().all()

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

        with engine.begin() as conn:
            deleted = conn.execute(
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


def gc_run_artifacts(*, engine, paths: PathManager, now: datetime, run_ttl_days: int) -> GcResult:
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

    with engine.begin() as conn:
        rows = conn.execute(query, {"cutoff": cutoff}).mappings().all()

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


__all__ = ["gc_environments", "gc_run_artifacts", "GcResult"]
