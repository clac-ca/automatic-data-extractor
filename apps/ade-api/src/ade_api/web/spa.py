"""Serve a built SPA bundle from FastAPI."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


class SpaStaticFiles(StaticFiles):
    """StaticFiles variant that falls back to index.html for SPA routes."""

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code != 404:
            return response
        if scope.get("method") not in {"GET", "HEAD"}:
            return response
        index_path = Path(self.directory) / "index.html"
        if not index_path.exists():
            return response
        return FileResponse(index_path)


def mount_spa(app: FastAPI, dist_dir: Path | None) -> None:
    """Mount the SPA bundle if a build output directory exists."""

    if not dist_dir:
        return
    if not dist_dir.exists():
        logger.warning(
            "ade_api.frontend.missing_dist",
            extra={"dist_dir": str(dist_dir)},
        )
        return
    if not dist_dir.is_dir():
        logger.warning(
            "ade_api.frontend.invalid_dist_dir",
            extra={"dist_dir": str(dist_dir)},
        )
        return
    if not (dist_dir / "index.html").exists():
        logger.warning(
            "ade_api.frontend.missing_index",
            extra={"dist_dir": str(dist_dir)},
        )
        return

    app.mount("/", SpaStaticFiles(directory=str(dist_dir), html=True), name="spa")


__all__ = ["mount_spa", "SpaStaticFiles"]
