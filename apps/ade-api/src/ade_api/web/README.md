# ADE Web Assets

The API can serve the built SPA bundle when `ADE_FRONTEND_DIST_DIR` is set.

Example (repo root):

```bash
ade build
ADE_FRONTEND_DIST_DIR=apps/ade-web/dist uvicorn ade_api.main:app
```

When running via `ade api` (or `ade start`), the CLI sets `ADE_FRONTEND_DIST_DIR` for you (expects a built `dist/`).
If you prefer a dedicated web server or reverse proxy, serve the `dist/`
directory separately and run `ade api --no-web` (or `ade start --no-web`).
