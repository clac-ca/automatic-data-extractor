# ADE Web Assets

The API no longer serves the SPA bundle. Host the built web assets via nginx
(or a CDN/object storage). The ADE image includes the built assets under
`/usr/share/nginx/html` and ships an nginx template at
`/etc/nginx/templates/default.conf.template`.

Local development:

```bash
cd apps/ade-web
npm run dev
```

Container runtime (image):

- Use `/usr/local/bin/ade-web-entrypoint`, which renders the nginx template with
  `ADE_WEB_PROXY_TARGET` and starts nginx.
