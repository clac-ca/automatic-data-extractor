"""Garbage collection for worker-local cache and run artifacts."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from ade_db.engine import build_engine
from .paths import PathManager
from .settings import Settings, get_settings

logger = logging.getLogger("ade_worker.gc")


@dataclass(slots=True)
class GcResult:
    scanned: int = 0
    deleted: int = 0
    skipped: int = 0
    failed: int = 0


def gc_local_venv_cache(
    *,
    paths: PathManager,
    now: datetime,
    cache_ttl_days: int,
) -> GcResult:
    result = GcResult()
    ttl_days = int(cache_ttl_days)
    if ttl_days <= 0:
        return result

    cutoff = now - timedelta(days=ttl_days)
    venvs_root = paths.worker_venvs_root
    if not venvs_root.exists():
        return result

    candidates = [path for path in venvs_root.glob("*/*/deps-*") if path.is_dir()]
    result.scanned = len(candidates)
    for env_root in candidates:
        marker = env_root / ".ready"
        probe = marker if marker.exists() else env_root
        try:
            last_used = datetime.fromtimestamp(probe.stat().st_mtime)
        except FileNotFoundError:
            result.skipped += 1
            continue

        if last_used >= cutoff:
            result.skipped += 1
            continue

        if _delete_tree(env_root):
            result.deleted += 1
            logger.info(
                "gc: local environment deleted path=%s last_used=%s cutoff=%s",
                env_root,
                last_used.isoformat(),
                cutoff.isoformat(),
            )
        else:
            result.failed += 1
            logger.warning("gc: local environment delete failed path=%s", env_root)

    return result


def gc_run_artifacts(
    *,
    session_factory: sessionmaker[Session],
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
        WHERE status IN ('succeeded', 'failed', 'cancelled')
          AND completed_at IS NOT NULL
          AND completed_at < :cutoff
        """
    )

    with session_factory() as session:
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
    engine = build_engine(settings)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    paths = PathManager(
        layout=settings,
        worker_runs_root=settings.worker_runs_dir,
        worker_venvs_root=settings.worker_venvs_dir,
        worker_pip_cache_root=settings.worker_uv_cache_dir,
    )
    now = datetime.now(timezone.utc)

    cache_result = gc_local_venv_cache(
        paths=paths,
        now=now,
        cache_ttl_days=settings.worker_cache_ttl_days,
    )

    run_result: GcResult | None = None
    if settings.worker_run_artifact_ttl_days is not None:
        run_result = gc_run_artifacts(
            session_factory=session_factory,
            paths=paths,
            now=now,
            run_ttl_days=settings.worker_run_artifact_ttl_days,
        )

    engine.dispose()
    return cache_result, run_result


__all__ = ["gc_local_venv_cache", "gc_run_artifacts", "GcResult", "run_gc"]
