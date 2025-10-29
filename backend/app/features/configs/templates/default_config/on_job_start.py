from __future__ import annotations

from pathlib import Path
from typing import Any


def run(
    *,
    workspace_id: str,
    config_id: str,
    job_id: str,
    env: dict[str, str],
    paths: dict[str, str],
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Example on_job_start hook. Builds a small job context payload that column
    modules can reference when scoring/transforming values.
    """

    cache_dir = Path(paths["cache"])
    cache_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "workspace_id": workspace_id,
        "config_id": config_id,
        "job_id": job_id,
        "locale": env.get("LOCALE", "en-CA"),
        "inputs": inputs or {},
    }
    return {"jobContext": summary}
