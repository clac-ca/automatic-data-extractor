# Authentication Architecture

This document explains how requests are authenticated in Automatic Data Extractor (ADE), how FastAPI dependencies enforce
permissions, and what operators should consider when extending the system.

## Identity sources

ADE normalises three credential types into an `AuthenticatedPrincipal` before any route code runs:

1. **Session cookies** — primary browser flow. `POST /api/v1/auth/session` and `/session/refresh` set `httponly` access and
   refresh cookies (`SameSite=Lax`; `Secure` when `ADE_SERVER_PUBLIC_URL` is https) scoped to the configured cookie domain/path.
   Requests fall back to the access-token cookie when no `Authorization` header is present.
2. **Bearer access tokens** — the same JWTs returned in the session envelope; send via `Authorization: Bearer <token>`.
3. **API keys** — issued via the API/UI; send via `X-API-Key`. API keys map to the same principal model so RBAC applies uniformly.

The dependency `get_current_principal` tries bearer → session cookie → API key and guarantees the backing `User` exists.

## Session lifecycle

- `POST /api/v1/auth/session` (email/password) and `POST /api/v1/auth/session/refresh` return a `SessionEnvelope` containing
  tokens **and** the `/me/bootstrap` context (user, roles, permissions, workspaces, expiry hints). Responses set cookies for
  browser callers while keeping the JSON payload for API clients.
- `POST /api/v1/auth/setup` creates the inaugural administrator and returns the same envelope/cookies.
- `DELETE /api/v1/auth/session` clears cookies; no server-side revocation store exists yet.
- CSRF enforcement is **not implemented**. The `require_csrf` dependency is wired into routers as a placeholder to ease future
  activation but currently no-ops.

## Single sign-on

SSO endpoints exist but the OIDC service is not implemented. With `ADE_OIDC_ENABLED=true`, the API exposes:

- `GET /api/v1/auth/sso/{provider}/authorize` — planned 302 to the IdP.
- `GET /api/v1/auth/sso/{provider}/callback` — currently returns 404 “not implemented”. It already supports two response modes:
  - Redirect to `ADE_FRONTEND_URL/sso-complete?state=...` (default for browser Accept headers).
  - JSON `SessionEnvelope` when `response_mode=json` or `Accept: application/json` is used.

Until OIDC logic lands, keep `ADE_OIDC_ENABLED=false` to avoid advertising an unusable flow.

## Security dependencies

Routers share dependencies from `ade_api.core.http.dependencies` so OpenAPI documents auth requirements consistently:

- `require_authenticated` ensures a `User` is attached to the request.
- `require_global(<permission>)` / `require_workspace(<permission>)` enforce RBAC via the principal-aware authoriser and surface
  structured 403 responses with permission and scope context.
- `require_csrf` is present on mutating routes but currently a no-op.
- OpenAPI marks only `/health`, `/auth/providers`, `/auth/setup` (GET/POST), `/auth/session` (POST), and SSO authorize/callback
  as public; everything else inherits the default security schemes.

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
