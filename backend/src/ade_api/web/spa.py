"""Serve a built SPA bundle from FastAPI."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

logger = logging.getLogger(__name__)


class SpaStaticFiles(StaticFiles):
    """StaticFiles variant that falls back to index.html for SPA routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        if scope.get("method") not in {"GET", "HEAD"}:
            return await super().get_response(path, scope)

        missing_exc: StarletteHTTPException | None = None
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            missing_exc = exc
            response = None

        if response is not None and response.status_code != 404:
            return response
        directory = self.directory
        if directory is None:
            raise RuntimeError("SPA static directory is not configured.")
        index_path = Path(directory) / "index.html"
        if not index_path.exists():
            if missing_exc is not None:
                raise missing_exc
            raise RuntimeError("Static response missing without a 404 exception.")
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
