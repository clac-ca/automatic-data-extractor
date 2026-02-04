# ADE Web Assets

The API no longer serves the SPA bundle. Host the built web assets via nginx
(or a CDN/object storage). The ADE image includes the built assets under
`/usr/share/nginx/html` and ships a minimal nginx config at
`/etc/nginx/nginx.conf` plus a template at `/etc/nginx/templates/default.conf.tmpl`.

Local development:

```bash
cd frontend/ade-web
npm run dev
```

Container runtime (image):

- Use `ade web start` (or `ade start`), which renders the nginx template via
  `envsubst` with `ADE_INTERNAL_API_URL` and starts nginx.
