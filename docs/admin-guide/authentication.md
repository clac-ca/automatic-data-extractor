# Authentication Architecture

This document explains how requests are authenticated in Automatic Data Extractor (ADE), how FastAPI dependencies enforce
permissions, and what operators should consider when extending the system.

## Identity sources

ADE normalises three credential types into an `AuthenticatedPrincipal` before any route code runs:

1. **Session cookies** — primary browser flow. `POST /api/v1/auth/cookie/login` sets the HttpOnly `ade_session` cookie
   (with SameSite/Lax and Secure on HTTPS). Sessions are stored in `access_tokens` and use a double-submit CSRF cookie (`ade_csrf`)
   for unsafe methods.
2. **Bearer access tokens** — optional non-browser flow. `POST /api/v1/auth/jwt/login` returns a JWT; send via
   `Authorization: Bearer <token>`.
3. **API keys** — issued via the API/UI; send via `X-API-Key` or `Authorization: Api-Key <token>`. API keys map to the same
   principal model so RBAC applies uniformly.

The dependency `get_current_principal` tries API key → session cookie → bearer and guarantees the backing `User` exists.

## Session lifecycle

- `POST /api/v1/auth/cookie/login` (email/password) sets the `ade_session` cookie and stores an `access_tokens` row; the response
  is `204 No Content` for browser callers.
- `POST /api/v1/auth/jwt/login` returns a bearer token for non-browser clients.
- `POST /api/v1/auth/setup` creates the inaugural administrator, sets cookies, and returns `204`.
- `POST /api/v1/auth/cookie/logout` clears cookies and removes the access token row.
- CSRF enforcement uses a double-submit cookie: `ade_csrf` must match `X-CSRF-Token` for unsafe methods authenticated by cookie.

## Account deactivation

- The `users.is_active` flag now hard-blocks authentication across password, cookie sessions, and API keys; existing sessions
  fail with 401 once a user is deactivated.
- Deactivating a user also revokes all of their API keys and places a long-lived lock on the account; audit foreign keys remain
  intact. Reactivated users must be issued fresh API keys.

## Single sign-on

When `ADE_OIDC_ENABLED=true`, the API exposes:

- `GET /api/v1/auth/oidc/{provider}/authorize` — 302 redirect to the IdP (sets state + return_to cookies).
- `GET /api/v1/auth/oidc/{provider}/callback` — validates the response, provisions or links users, and sets a session cookie.
  - Browser mode redirects to `ADE_FRONTEND_URL/auth/callback?return_to=...`.
  - JSON mode returns `{ "ok": true }` when `response_mode=json` or `Accept: application/json` is used.

## Security dependencies

Routers share dependencies from `ade_api.core.http.dependencies` so OpenAPI documents auth requirements consistently:

- `require_authenticated` ensures a `User` is attached to the request.
- `require_global(<permission>)` / `require_workspace(<permission>)` enforce RBAC via the principal-aware authoriser and surface
  structured 403 responses with permission and scope context.
- `require_csrf` enforces double-submit CSRF for cookie-authenticated unsafe methods.
- OpenAPI marks only `/health`, `/auth/providers`, `/auth/setup` (GET/POST), `/auth/cookie/login`, `/auth/jwt/login`,
  `/auth/register`, and OIDC authorize/callback as public; everything else inherits the default security schemes.

## Extending the system

When adding endpoints:

1) Mount routers with `dependencies=[Security(require_authenticated)]` unless the route is intentionally public.  
2) Add `Security(require_global(...))` or `Security(require_workspace(...))` with the exact permission key.  
3) Keep `Security(require_csrf)` on mutating routes to remain future-ready.  
4) If the workspace identifier uses a non-default name, set `workspace_param` when calling `require_workspace`.  
5) Update tests to cover both permitted and denied cases.

## Troubleshooting

- **401** — no credentials resolved; check token expiry, cookie domain/path, or API key validity.  
- **403** — missing permission; verify role assignments at the correct scope.  
- **422 invalid_scope** — workspace identifier missing/mismatched; confirm the guard sees the correct parameter.  
- **Missing session context after login** — bootstrap call failed while building the envelope; verify DB connectivity and JWT
  signing settings.
