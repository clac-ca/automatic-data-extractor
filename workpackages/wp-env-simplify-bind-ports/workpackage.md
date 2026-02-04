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

**Legacy env aliases are removed; deployments must update to the canonical env model.**

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
3. Bind to `8000`

**Web servers receive exactly one API input:**
`ADE_INTERNAL_API_URL`

**Rule:** `ADE_INTERNAL_API_URL` must be an origin only (no `/api` path).

---

### Minimal web-related env model

```env
ADE_INTERNAL_API_URL=http://localhost:8001  # origin only (no /api)
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
    nginx.conf        # minimal nginx config
    default.conf.tmpl # site template (envsubst)
```

---

## Reference Configs

### nginx (`frontend/ade-web/nginx/default.conf.tmpl`)

```nginx
map $http_upgrade $connection_upgrade {
  default upgrade;
  '' close;
}

server {
  listen 8000;

  root /usr/share/nginx/html;
  index index.html;

  location / {
    try_files $uri /index.html;
  }

  location /api/ {
    proxy_pass ${ADE_INTERNAL_API_URL};
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
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
    port: 8000,
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

### Bind ports (fixed)

* API always binds to `8001`
* Web server always binds to `8000`

### URLs (what proxies and users use)

* `ADE_PUBLIC_WEB_URL` – public-facing web URL
* `ADE_INTERNAL_API_URL` – internal API upstream (origin only, used by nginx and Vite)

---

## CLI Behavior

`ade start` and `ade dev` always use the fixed bind ports (web `8000`, API `8001`).

---

## Runtime Behavior

### `ade start` (production-style)

* Runs API, worker, and web (nginx)
* Serves built frontend assets
* Proxies `/api` → `ADE_INTERNAL_API_URL`
* Binds: API `8001`, web `8000`

---

### `ade dev` (development-style)

* Runs API, worker, and web (Vite dev server)
* Uses HMR
* Proxies `/api` → `ADE_INTERNAL_API_URL`
* Binds: API `8001`, web `8000`

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

## URL Change Rules

* If the API host changes, update `ADE_INTERNAL_API_URL`.
* If the public web host or scheme changes, update `ADE_PUBLIC_WEB_URL`.

---

## Scope

### In scope

* Canonical env names for URLs; bind ports fixed to `8000`/`8001`
* Remove legacy env aliases (single canonical model)
* Unified proxy config via `ADE_INTERNAL_API_URL`
* Docs (env reference, quickstart, deployment)
* Simplified Dockerfile and standardized nginx layout

### Out of scope

* Auth, session, or routing behavior changes

---

## Work Breakdown Structure (WBS)

## Stages

### Stage 1: Env + CLI wiring

- Canonical env names + precedence rules
- API/web settings (canonical only)
- Root CLI + web CLI fixed port behavior

### Stage 2: Web proxy + Docker layout

- nginx + Vite proxy configs
- Dockerfile + nginx template layout
- Docker Compose env wiring

### Stage 3: Docs + validation

- Env reference + quickstart/deployment docs
- Local smoke checks

### 1.0 Env model and defaults

* [x] Finalize canonical env names
* [x] Define precedence rules
* [x] Confirm API default port (`8001`)
* [x] Enforce `ADE_INTERNAL_API_URL` origin-only input
* [x] Remove legacy frontend URL alias (`ADE_FRONTEND_URL`)

### 2.0 Settings and validation

#### 2.1 API

* [x] Add canonical settings
* [x] Remove legacy parsing
* [x] Validate ports and URLs

#### 2.2 Worker / shared

* [x] Audit worker usage of URLs
* [x] Keep behavior consistent

---

### 3.0 CLI wiring

#### 3.1 Root CLI

* [x] Remove bind-port flags
* [x] Standardize fixed ports (web `8000`, API `8001`)
* [x] Remove ad-hoc port logic

#### 3.2 Web commands

* [x] Ensure `ade web start` uses canonical envs

---

### 4.0 Web proxy config

#### 4.1 nginx

* [x] Use `ADE_INTERNAL_API_URL`
* [x] Validate template rendering
* [x] Simplify nginx.conf (minimal, standard) and render via envsubst

#### 4.2 Vite

* [x] Use `ADE_INTERNAL_API_URL`
* [x] Remove legacy aliases

#### 4.3 Docker / layout

* [x] Simplify Dockerfile
* [x] Standardize nginx directory
* [x] Replace init container with root-then-drop entrypoint (gosu) for /app/backend/data permissions
* [x] Remove ade-init services from compose
* [x] Bind-mount ./backend/data for local dev troubleshooting
* [x] Rename runtime user to `adeuser`
* [x] Move default data dir to `backend/data` (settings + compose + docs + gitignore)

---

### 5.0 Documentation

* [x] Update env reference
* [x] Update quickstart and deployment docs

---

### 6.0 Validation

* [x] Local smoke tests
* [ ] Verify overrides for `ade start` and `ade dev`
* [ ] Verify root-then-drop permissions with local compose (no ade-init)

---

## Open Questions

* Should the API always bind to `8001` if web is disabled?
  * Decision: yes, always `8001`.
* Do we need `ADE_PUBLIC_API_URL` if the UI always proxies `/api`?
  * Decision: no (out of scope).
* Should legacy env usage emit deprecation warnings?
  * Decision: no (legacy envs are removed).

---

## Acceptance Criteria

* Canonical env vars are supported and documented
* Fixed bind ports are enforced (web `8000`, API `8001`)
* nginx and Vite proxy via `ADE_INTERNAL_API_URL`
* `ADE_INTERNAL_API_URL` is origin-only (no `/api` path)
* Legacy env aliases removed

---

## Definition of Done

* Implementation complete and locally verified
* Docs updated with canonical examples
* WBS checklist reflects completed work
