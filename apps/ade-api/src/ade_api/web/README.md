# ADE Web Assets

The API no longer serves the SPA bundle. Use `ade web serve` (nginx) or another
static web server (CDN, object storage, etc.) to host `apps/ade-web/dist`.
The ADE image includes the built assets under `/app/web/dist`.

Example (repo root):

```bash
ade web build
ade web serve --dist-dir apps/ade-web/dist --proxy-target http://localhost:8000
```
