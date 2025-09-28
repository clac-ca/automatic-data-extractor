# Environment Variable Rewrite Plan

## Goal
Reorganise ADE's environment configuration so backend and frontend code use clear, conventional variables that work for both localhost development and hosted deployments (HTTP or HTTPS, custom domains, reverse proxies).

## Guiding Principles
1. **12-factor style** – All deploy-time options come from environment variables. Defaults should cover localhost but every setting must be overrideable without code edits.
2. **Single responsibility** – Backend code should only expose backend configuration. Frontend defaults stay in the Vite layer. Shared values (such as public API origin) live in a neutral location (templates/docs) and are injected into each process explicitly.
3. **Explicit origins** – Prefer complete origin URLs (scheme + host + optional port) over recombining host/port in multiple places.
4. **Secure by default** – Never assume HTTP in production; allow HTTPS and custom domains without extra code changes.
5. **Explain the "why"** – When variables differ from each other, document the scenarios that make the distinction necessary so future contributors understand the standard pattern.

## Current Pain Points
- `backend/api/settings.py` defines `server_host`, `backend_port`, and `frontend_port`, so backend configuration leaks frontend assumptions.
- Backend helpers (`backend_origin` / `frontend_origin`) hard-code `http://` and use the same host for both services, making HTTPS or split hosts awkward.
- `cli/commands/start.py` has to infer `VITE_API_BASE_URL` from backend host/port, coupling dev ergonomics to backend internals.
- `.env` / docs do not document a single source of truth for the public API origin, so CORS, cookies, and frontend config have to guess.

## Proposed Restructure
### 1. Backend Settings Model
- Replace `server_host`, `backend_port`, and derived `backend_origin` with:
  - `ADE_BACKEND_BIND_HOST` / `ADE_BACKEND_BIND_PORT` (for uvicorn bind interface only — typically `0.0.0.0:8000` in containers).
  - `ADE_BACKEND_PUBLIC_URL` (default `http://localhost:8000`) used for CORS, cookies, and third-party callbacks.
- Document why the bind values and the public URL can differ (e.g., container listens on `0.0.0.0:8000` but users reach it via `https://api.example.com`).
- Remove `frontend_port` and any frontend-specific helpers from backend settings.
- Update validators so `ADE_BACKEND_PUBLIC_URL` accepts HTTP or HTTPS URLs (use `AnyHttpUrl` or manual parsing) and defaults to localhost.
- Ensure CORS configuration consumes `ADE_CORS_ALLOW_ORIGINS` plus `ADE_BACKEND_PUBLIC_URL` when appropriate.

> **Standard pattern:** Frameworks such as FastAPI, Django, and Rails all separate the bind address from the public origin in production deployments. Containers or PaaS platforms often expose services on `0.0.0.0` internally while routing public traffic through a load balancer on a DNS name with TLS. Mirroring that split keeps ADE compatible with reverse proxies and cloud ingress controllers without special-case logic.

- Record the mapping from backend variables to their usages in the developer docs so people know which component reads each variable.

### 2. Frontend Environment Handling
- Standardise on `VITE_API_BASE_URL` (already in use). Provide dev defaults via `frontend/.env.example`, mirroring `ADE_BACKEND_PUBLIC_URL`.
- Remove assumptions that the CLI or backend will inject frontend ports; instead, the CLI should read backend bind host/port flags and set `VITE_API_BASE_URL` only for the dev server convenience case.

### 3. CLI Alignment (`ade start`)
- Source backend bind host/port from CLI flags (default localhost). Keep convenience logic to populate `VITE_API_BASE_URL` **only** when the user has not set it.
- Honour `.env` overrides so running `ADE_BACKEND_PUBLIC_URL=https://api.example.com ade start` works without extra flags.

- Clarify in docs that the bind host/port addresses listen-only concerns (e.g., Docker, Kubernetes Service) while the public URL aligns with DNS/certificates. Include common production setups where they differ.

### 4. Documentation & Templates
- Update `.env.example`, `frontend/.env.example`, and relevant docs to explain the three key variables:
  - `ADE_BACKEND_BIND_HOST` / `ADE_BACKEND_BIND_PORT` – local bind interface for uvicorn.
  - `ADE_BACKEND_PUBLIC_URL` – public URL that clients should use (can differ from bind host).
  - `VITE_API_BASE_URL` – frontend API endpoint (should match `ADE_BACKEND_PUBLIC_URL`).
- Provide guidance for HTTPS / reverse proxy deployments (e.g., set `ADE_BACKEND_PUBLIC_URL=https://api.example.com`).

### 5. Testing & Validation
- Extend backend settings tests to cover `ADE_BACKEND_PUBLIC_URL` validation and ensure HTTPS origins work.
- Add CLI tests (or integration docs) ensuring `--env VITE_API_BASE_URL=...` overrides the auto-generated value.

## Execution Steps
1. Refactor `backend/api/settings.py` and associated tests/middleware to the new variable names and behaviours.
2. Adjust `cli/commands/start.py` to read the renamed bind variables and stop depending on frontend settings.
3. Add/update `.env.example` files and documentation to describe the new configuration workflow.
4. Verify local dev flow (`ade start`) still works with defaults and with custom overrides.
