# Work Package: Simplify Env Names and Bind Ports

> **Agent instructions**
>
> * This document is the single source of truth
> * Keep the WBS checklist up to date (`[ ]` → `[x]`)
> * If the plan changes, update this document first, then the code

---

## The Golden Rule

If **nginx** and **Vite** need different documentation, the design is wrong.

They may differ only in:

* how frontend assets are produced
* whether HMR exists

Everything else must be identical.

---

## Goal

Standardize how ADE defines:

* **bind ports** (where processes listen)
* **API and web URLs** (what proxies point to and users access)

…and make overrides explicit and consistent across `ade start` and `ade dev`.

This removes ambiguity between:

* public URLs vs internal upstreams
* dev (Vite) vs prod (nginx)
* legacy env names vs canonical ones

**All existing deployments must continue to work.**

---

## Design Contract

### Clear responsibilities

| Component                  | Responsibility                         |
| -------------------------- | -------------------------------------- |
| API                        | Serve `/api/*`                         |
| Web server (Vite or nginx) | Serve frontend assets and proxy `/api` |
| CLI                        | Decide which web server runs           |

---

### Single web contract

Both **Vite** and **nginx** must:

1. Serve frontend assets
2. Proxy `/api` → `ADE_INTERNAL_API_URL`
3. Bind to `ADE_WEB_BIND_PORT`

**Web servers receive exactly one API input:**
`ADE_INTERNAL_API_URL`

---

### Minimal web-related env model

```env
ADE_WEB_BIND_PORT=8000
ADE_INTERNAL_API_URL=http://localhost:8001
ADE_PUBLIC_WEB_URL=http://localhost:8000
```

---

## Frontend Layout (Standard and Obvious)

```
frontend/ade-web/
  dist/               # Vite build output
  src/
  vite.config.ts
  nginx/
    default.conf.tmpl # single nginx template
```

---

## Reference Configs

### nginx (`frontend/ade-web/nginx/default.conf.tmpl`)

```nginx
server {
  listen ${ADE_WEB_BIND_PORT};

  root /usr/share/nginx/html;
  index index.html;

  location / {
    try_files $uri /index.html;
  }

  location /api/ {
    proxy_pass ${ADE_INTERNAL_API_URL};
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
}
```

---

### Vite (`frontend/ade-web/vite.config.ts`)

```ts
export default defineConfig({
  server: {
    port: Number(process.env.ADE_WEB_BIND_PORT ?? 8000),
    proxy: {
      "/api": {
        target: process.env.ADE_INTERNAL_API_URL,
        changeOrigin: true,
      },
    },
  },
});
```

---

## Canonical Environment Model

### Bind ports (where processes listen)

* `ADE_API_BIND_PORT` (default: `8001`)
* `ADE_WEB_BIND_PORT` (default: `8000`)

### URLs (what proxies and users use)

* `ADE_PUBLIC_WEB_URL` – public-facing web URL
* `ADE_INTERNAL_API_URL` – internal API upstream (used by nginx and Vite)

---

## CLI Overrides

Both commands accept explicit bind-port overrides:

```bash
ade start --api-bind-port 9001 --web-bind-port 9000
ade dev   --api-bind-port 9001 --web-bind-port 9000
```

**Precedence rules**

1. CLI flags
2. Canonical env vars
3. Legacy env vars
4. Defaults

`ade start` and `ade dev` behave identically.

---

## Runtime Behavior

### `ade start` (production-style)

* Runs API, worker, and web (nginx)
* Serves built frontend assets
* Proxies `/api` → `ADE_INTERNAL_API_URL`
* Uses:

  * `ADE_API_BIND_PORT` for API
  * `ADE_WEB_BIND_PORT` for nginx

---

### `ade dev` (development-style)

* Runs API, worker, and web (Vite dev server)
* Uses HMR
* Proxies `/api` → `ADE_INTERNAL_API_URL`
* Uses:

  * `ADE_API_BIND_PORT` for API
  * `ADE_WEB_BIND_PORT` for Vite

**Key point:**
Only the web server implementation changes.
Env vars and flags do not.

---

## Web Serving Rules

**Development**

* Vite dev server
* HMR enabled
* Vite proxies `/api`
* No nginx

**Production**

* Static build (`npm run build`)
* Served by nginx (or CDN/object storage)
* nginx proxies `/api`

**Rule of thumb**

* Vite = dev
* nginx = prod

---

## Port Change Rules

* Changing `ADE_WEB_BIND_PORT` → update `ADE_PUBLIC_WEB_URL`
* Changing `ADE_API_BIND_PORT` → update `ADE_INTERNAL_API_URL`

No hidden coupling.

---

## Scope

### In scope

* Canonical env names for bind ports and URLs
* `--api-bind-port` / `--web-bind-port` flags
* Backward-compatible aliases:

  * `ADE_API_PORT`
  * `ADE_WEB_DEV_PORT`
  * `ADE_WEB_PROXY_TARGET`
* Unified proxy config via `ADE_INTERNAL_API_URL`
* Docs (env reference, quickstart, deployment)
* Simplified Dockerfile and standardized nginx layout

### Out of scope

* Removing legacy env vars
* Breaking existing deployments
* Auth, session, or routing behavior changes

---

## Work Breakdown Structure (WBS)

### 1.0 Env model and defaults

* [ ] Finalize canonical env names
* [ ] Define precedence rules
* [ ] Confirm API default port (`8001`)

### 2.0 Settings and aliases

#### 2.1 API

* [ ] Add canonical settings
* [ ] Preserve legacy parsing
* [ ] Validate ports and URLs

#### 2.2 Worker / shared

* [ ] Audit worker usage of URLs
* [ ] Keep behavior consistent

---

### 3.0 CLI wiring

#### 3.1 Root CLI

* [ ] Add bind-port flags
* [ ] Enforce override precedence
* [ ] Remove ad-hoc port logic

#### 3.2 Web commands

* [ ] Ensure `ade web start` uses canonical envs

---

### 4.0 Web proxy config

#### 4.1 nginx

* [ ] Use `ADE_INTERNAL_API_URL`
* [ ] Validate template rendering

#### 4.2 Vite

* [ ] Use `ADE_INTERNAL_API_URL`
* [ ] Support legacy aliases

#### 4.3 Docker / layout

* [ ] Simplify Dockerfile
* [ ] Standardize nginx directory

---

### 5.0 Documentation

* [ ] Update env reference
* [ ] Update quickstart and deployment docs
* [ ] Add migration notes

---

### 6.0 Validation

* [ ] Local smoke tests
* [ ] Verify overrides for `ade start` and `ade dev`

---

## Open Questions

* Should the API always bind to `8001` if web is disabled?
* Do we need `ADE_PUBLIC_API_URL` if the UI always proxies `/api`?
* Should legacy env usage emit deprecation warnings?

---

## Acceptance Criteria

* Canonical env vars are supported and documented
* Bind-port overrides work consistently
* nginx and Vite proxy via `ADE_INTERNAL_API_URL`
* Legacy envs continue to work unchanged

---

## Definition of Done

* Implementation complete and locally verified
* Docs updated with examples and migration notes
* WBS checklist reflects completed work
