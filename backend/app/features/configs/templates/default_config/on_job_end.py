from __future__ import annotations

from typing import Any


def run(
    *,
    workspace_id: str,
    config_id: str,
    job_id: str,
    env: dict[str, str],
    paths: dict[str, str],
    success: bool,
    error: str | None,
) -> dict[str, Any] | None:
    """
    Example on_job_end hook. Emits a summary that could be logged by the engine.
    """

    return {
        "jobContext": {
            "workspace_id": workspace_id,
            "config_id": config_id,
            "job_id": job_id,
            "success": success,
            "error": error,
        }
    }
