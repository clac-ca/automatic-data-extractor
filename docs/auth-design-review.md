# Authentication Endpoint Redesign

## Overview
ADE’s authentication module now targets the browser-first workflow the product requires. Password and SSO logins establish HttpOnly session cookies, refresh tokens rotate transparently, and every unsafe request must present a CSRF token issued alongside the session. Machine clients can continue to rely on API keys or explicit bearer tokens, but the default path is now safe for a standard frontend.

## Session lifecycle

### Credential login
`POST /auth/login` accepts a JSON body with `email` and `password`, authenticates the user, and issues:

* `ade_session` – an HttpOnly, SameSite=Lax JWT that expires after the configured session timeout.
* `ade_refresh` – an HttpOnly refresh token scoped to `/auth/refresh` with a longer TTL for silent rotation.
* `ade_csrf` – a non-HttpOnly token surfaced both as a cookie and within the access/refresh token claims so the frontend can perform the double-submit check.

The response body contains only metadata (`user`, `expires_at`, `refresh_expires_at`) so the browser never touches secret material. 【F:app/auth/router.py†L28-L104】【F:app/auth/schemas.py†L1-L54】 The frontend now sends JSON credentials and relies entirely on the cookies for subsequent requests. 【F:frontend/src/api/auth.ts†L1-L63】

### Refresh and logout
`POST /auth/refresh` validates the refresh cookie, enforces the CSRF header, rotates the session, and re-issues all cookies atomically. Logout (`POST /auth/logout`) requires the same CSRF header and deletes the three cookies, immediately invalidating the browser session. 【F:app/auth/router.py†L106-L177】

### SSO
The SSO callback mirrors the password flow: after verifying the state token, the handler clears the temporary cookie and applies the new session cookies before returning the same lightweight metadata envelope. 【F:app/auth/router.py†L147-L214】

## Request authentication

### Cookie-backed requests
`bind_current_principal` now inspects the `ade_session` cookie, verifies the embedded CSRF hash, and enforces that unsafe HTTP methods include `X-CSRF-Token` matching the non-HttpOnly cookie. 【F:app/auth/dependencies.py†L20-L74】【F:app/auth/service.py†L132-L241】 The FastAPI client wrapper automatically attaches this header when running in the browser, keeping API calls deterministic for the frontend. 【F:frontend/src/api/client.ts†L1-L159】

### Bearer tokens and API keys
For automation or CLI clients we retain support for `Authorization: Bearer <jwt>`. Bearer requests bypass CSRF checks, while API keys continue to use the dedicated header. 【F:app/auth/dependencies.py†L20-L74】 The tests still exercise bearer flows, so existing automation remains compatible even as browser flows prefer cookies. 【F:tests/modules/workspaces/test_workspaces.py†L16-L39】

## Supporting infrastructure

* **Settings** – Session configuration now includes cookie names, refresh lifetimes, and common cookie attributes so deployments can tailor domains and paths if required. 【F:app/settings.py†L41-L66】
* **Schemas** – The old OAuth2 form schema has been replaced with `LoginRequest`/`SessionEnvelope`, reflecting the cookie-first contract. 【F:app/auth/schemas.py†L1-L61】
* **Frontend state** – The session provider stores only user metadata and expiry timestamps; tokens never touch application state. Logout calls the new backend endpoint to clear cookies. 【F:frontend/src/app/providers/SessionProvider.tsx†L1-L66】【F:frontend/src/api/auth.ts†L1-L72】

## Migration notes

* Clients that previously called `/auth/token` must migrate to `/auth/login` and rely on cookies rather than storing JWTs.
* State-changing requests must include `X-CSRF-Token` when cookies are present. ADE’s `ApiClient` handles this automatically for browser consumers.
* Machine-to-machine integrations should continue to use API keys; bearer tokens remain available for explicit automation scenarios.

This redesign brings ADE’s authentication in line with mainstream SPA/server security expectations while preserving the flexibility required for scripting and API-driven workloads.

