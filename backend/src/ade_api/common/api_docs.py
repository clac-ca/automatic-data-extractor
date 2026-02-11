"""Custom API docs routes for ADE."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Security
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse, Response

from ade_api.core.http import require_authenticated
from ade_api.settings import Settings

DOCS_RESPONSE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
}
SWAGGER_UI_PARAMETERS: dict[str, Any] = {
    "tryItOutEnabled": True,
    "displayRequestDuration": True,
    "filter": True,
    "persistAuthorization": True,
    "deepLinking": True,
    "displayOperationId": True,
    "defaultModelsExpandDepth": -1,
    "operationsSorter": "alpha",
    "tagsSorter": "alpha",
}
SWAGGER_REQUEST_INTERCEPTOR_MARKER = "adeSwaggerCsrfRequestInterceptor"


def _docs_dependencies(access_mode: str) -> Sequence[Any]:
    if access_mode == "authenticated":
        return [Security(require_authenticated)]
    return []


def _apply_docs_headers(response: Response) -> Response:
    for name, value in DOCS_RESPONSE_HEADERS.items():
        response.headers[name] = value
    return response


def _build_swagger_request_interceptor_script(csrf_cookie_name: str) -> str:
    safe_methods = ("GET", "HEAD", "OPTIONS", "TRACE")
    safe_methods_js = ", ".join(json.dumps(method) for method in safe_methods)
    cookie_name_js = json.dumps(csrf_cookie_name)
    return f"""
<script>
(() => {{
  const marker = "{SWAGGER_REQUEST_INTERCEPTOR_MARKER}";
  if (window[marker]) {{
    return;
  }}
  window[marker] = true;

  const SAFE_METHODS = new Set([{safe_methods_js}]);

  function readCookie(name) {{
    const encodedName = encodeURIComponent(name) + "=";
    const parts = document.cookie.split(";");
    for (const rawPart of parts) {{
      const part = rawPart.trim();
      if (part.startsWith(encodedName)) {{
        return decodeURIComponent(part.slice(encodedName.length));
      }}
    }}
    return "";
  }}

  const ui = window.ui;
  if (!ui || typeof ui.getConfigs !== "function") {{
    return;
  }}

  const configs = ui.getConfigs();
  const previousInterceptor =
    typeof configs.requestInterceptor === "function"
      ? configs.requestInterceptor
      : (req) => req;

  configs.requestInterceptor = (req) => {{
    const request = req ?? {{}};
    const method = String(request.method ?? "GET").toUpperCase();
    if (!SAFE_METHODS.has(method)) {{
      const csrfToken = readCookie({cookie_name_js});
      if (csrfToken) {{
        request.headers = request.headers ?? {{}};
        const existingToken = request.headers["X-CSRF-Token"] || request.headers["x-csrf-token"];
        if (!existingToken) {{
          request.headers["X-CSRF-Token"] = csrfToken;
        }}
      }}
    }}
    return previousInterceptor(request);
  }};
}})();
</script>
"""


def _inject_swagger_request_interceptor(
    html: str,
    *,
    csrf_cookie_name: str,
) -> str:
    script = _build_swagger_request_interceptor_script(csrf_cookie_name)
    if "</body>" in html:
        return html.replace("</body>", f"{script}\n</body>", 1)
    return f"{html}\n{script}"


def register_api_docs_routes(app: FastAPI, *, settings: Settings) -> None:
    dependencies = list(_docs_dependencies(settings.api_docs_access_mode))

    @app.get(settings.redoc_url, include_in_schema=False, dependencies=dependencies)
    async def redoc_html() -> Response:
        response = get_redoc_html(
            openapi_url=settings.openapi_url,
            title=f"{settings.app_name} - ReDoc",
        )
        return _apply_docs_headers(response)

    @app.get(settings.docs_url, include_in_schema=False, dependencies=dependencies)
    async def swagger_ui_html() -> Response:
        response = get_swagger_ui_html(
            openapi_url=settings.openapi_url,
            title=f"{settings.app_name} - Swagger UI",
            swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
        )
        raw_html = bytes(response.body).decode("utf-8")
        enriched_html = _inject_swagger_request_interceptor(
            raw_html,
            csrf_cookie_name=settings.session_csrf_cookie_name,
        )
        response.body = enriched_html.encode("utf-8")
        response.init_headers()
        return _apply_docs_headers(response)

    @app.get(settings.openapi_url, include_in_schema=False, dependencies=dependencies)
    async def openapi_json() -> Response:
        return JSONResponse(
            content=app.openapi(),
            headers=dict(DOCS_RESPONSE_HEADERS),
        )

    redirect_targets = {
        "/api/docs": settings.docs_url,
        "/docs": settings.docs_url,
        "/redoc": settings.redoc_url,
        "/openapi.json": settings.openapi_url,
    }

    for source_path, target_path in redirect_targets.items():
        if source_path == target_path:
            continue

        async def _redirect(target: str = target_path) -> Response:
            return RedirectResponse(
                url=target,
                status_code=307,
                headers=dict(DOCS_RESPONSE_HEADERS),
            )

        app.add_api_route(
            source_path,
            _redirect,
            methods=["GET"],
            include_in_schema=False,
            dependencies=dependencies,
        )


__all__ = [
    "DOCS_RESPONSE_HEADERS",
    "SWAGGER_UI_PARAMETERS",
    "register_api_docs_routes",
]
