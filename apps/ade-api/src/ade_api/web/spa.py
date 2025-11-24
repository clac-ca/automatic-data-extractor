"""SPA mounting helpers for the ADE FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

SPA_CACHE_HEADERS = {"Cache-Control": "no-cache"}


def mount_spa(app: FastAPI, *, api_prefix: str, static_dir: Path) -> None:
    """Mount the compiled SPA and register client-side routing fallbacks."""

    spa_index = static_dir / "index.html"

    if static_dir.exists():
        _mount_static_assets(app=app, static_dir=static_dir)

    _register_spa_routes(app=app, spa_index=spa_index, api_prefix=api_prefix)


def _mount_static_assets(*, app: FastAPI, static_dir: Path) -> None:
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    favicon = static_dir / "favicon.ico"
    if favicon.exists():

        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon_ico() -> FileResponse:
            return FileResponse(favicon)


def _register_spa_routes(
    *,
    app: FastAPI,
    spa_index: Path,
    api_prefix: str,
) -> None:
    missing_build_msg = "SPA build not found; run `ade build` from the repo root."

    @app.get("/", include_in_schema=False)
    async def read_spa_root() -> Response:
        if not spa_index.exists():
            raise HTTPException(status_code=404, detail=missing_build_msg)
        return FileResponse(spa_index, headers=SPA_CACHE_HEADERS)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def read_spa_fallback(full_path: str, request: Request) -> Response:
        path = request.url.path
        if path == "/" or path.startswith(f"{api_prefix}/") or path == api_prefix:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        reserved = {app.docs_url, app.redoc_url, app.openapi_url}
        if any(path == candidate for candidate in reserved if candidate):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        if not _wants_html(request):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        filename = full_path.rsplit("/", 1)[-1]
        if "." in filename:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        if not spa_index.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=missing_build_msg)

        return FileResponse(spa_index, headers=SPA_CACHE_HEADERS)


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept.lower()


__all__ = ["mount_spa"]
