# ADE Web Assets

The API can serve the built SPA bundle when `ADE_FRONTEND_DIST_DIR` is set.

Example (repo root):

```bash
ade build
ADE_FRONTEND_DIST_DIR=apps/ade-web/dist uvicorn ade_api.main:app
```

`ADE_FRONTEND_DIST_DIR` is required when serving the SPA. The CLI does not infer
a default path; set it explicitly (the production image sets it to `/app/web/dist`).
If you prefer a dedicated web server or reverse proxy, serve the `dist/`
directory separately and run `ade api --no-web` (or `ade start --no-web`).
