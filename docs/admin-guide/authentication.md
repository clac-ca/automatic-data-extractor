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

ADE now manages OIDC providers in the database and exposes a dedicated SSO surface:

- `GET /api/v1/auth/sso/providers` — public provider list for the login screen.
- `GET /api/v1/auth/sso/{providerId}/authorize` — 302 redirect to the IdP (server-stored state, PKCE, nonce).
- `GET /api/v1/auth/sso/{providerId}/callback` — validates the response, links/provisions users, and sets a session cookie.
  - Browser mode redirects to the sanitized `returnTo` path.
  - JSON mode returns `{ "ok": true, "returnTo": "/path", "error": null }` when `Accept: application/json` is used.

Provider configuration is managed via admin APIs:

- `GET/POST /api/v1/admin/sso/providers`
- `GET/PATCH/DELETE /api/v1/admin/sso/providers/{id}`
- `GET/PUT /api/v1/admin/sso/settings` (global enable/disable)

Operational settings:

- `ADE_AUTH_FORCE_SSO=true` disables password login in favor of SSO.
- `ADE_AUTH_SSO_AUTO_PROVISION` enables auto-provisioning for new SSO users (default: false).
- `ADE_AUTH_SSO_PROVIDERS_JSON` syncs env-managed providers into the database at startup.
- `ADE_SSO_ENCRYPTION_KEY` encrypts provider client secrets at rest (falls back to `ADE_SECRET_KEY` if unset).

### Provider management

Providers are created and managed via `/api/v1/admin/sso/providers`. Required fields:

- `id` (slug): lower-case, URL-safe (`^[a-z0-9][a-z0-9-_]{2,63}$`).
- `label`: human-readable name shown on the login screen.
- `issuer`: https URL for the IdP issuer.
- `clientId`: OIDC client ID.
- `clientSecret`: write-only secret; read responses never return it.
- `status`: `active`, `disabled`, or `deleted`.
- `domains`: optional list of email domains for routing (and auto-provision allow-list).

Disable providers by setting `status=disabled`; delete is a soft delete that preserves identities.

### Env-managed providers (startup sync)

To declare providers in configuration-as-code, set `ADE_AUTH_SSO_PROVIDERS_JSON` to a JSON array at process startup. When set
(including `[]`), the API performs a startup sync:

- Upserts every provider from the env list into the database.
- Marks env-managed providers as `managedBy="env"` and `locked=true`.
- Releases env-managed providers missing from the env list by flipping them to `managedBy="db"` and `locked=false`.

Example:

```json
[
  {
    "id": "okta-primary",
    "type": "oidc",
    "label": "Okta",
    "issuer": "https://issuer.example.com",
    "clientId": "abc123",
    "clientSecret": "secret",
    "domains": ["example.com"],
    "status": "active"
  }
]
```

Notes:

- ENV changes require a restart; there is no hot reload.
- `managedBy` and `locked` appear only on admin provider responses.
- To move an env-managed provider back to DB-managed, remove it from the env list and restart.

### Domain routing

Domain routing selects a provider based on the user's email domain. Configure domains via the provider `domains` list:

- Domains are stored lower-case (IDNA/punycode for internationalized domains).
- Each domain can map to only one provider.
- If no domain matches, the UI can still show all active providers.

### Auto-provision allow-list

Auto-provisioning is allowed only when `ADE_AUTH_SSO_AUTO_PROVISION=true` and the provider has `domains` configured that match
the user's email domain. If auto-provisioning is disabled (or a provider has no domains configured), users must already exist
in ADE or be linked by an admin.

### Error codes

SSO failures return stable codes in `ssoError`:

- `PROVIDER_NOT_FOUND` - provider ID is missing or deleted.
- `PROVIDER_DISABLED` - provider is disabled or globally disabled.
- `PROVIDER_MISCONFIGURED` - missing credentials, discovery failure, or JWKS failure.
- `UPSTREAM_ERROR` - IdP returned an error response.
- `STATE_INVALID` - state missing/unknown or provider mismatch.
- `STATE_EXPIRED` - state expired before callback.
- `STATE_REUSED` - state already consumed.
- `TOKEN_EXCHANGE_FAILED` - code exchange failed at the token endpoint.
- `ID_TOKEN_INVALID` - ID token failed validation (signature/issuer/audience/nonce).
- `EMAIL_MISSING` - IdP did not return an email claim.
- `EMAIL_NOT_VERIFIED` - email is not verified by the IdP.
- `AUTO_PROVISION_DISABLED` - auto-provisioning is disabled for new SSO users.
- `DOMAIN_NOT_ALLOWED` - email domain not allow-listed for auto-provisioning.
- `USER_NOT_ALLOWED` - user is inactive or a service account.
- `IDENTITY_CONFLICT` - provider subject linked to another user.
- `RATE_LIMITED` - too many attempts from the same client.
- `INTERNAL_ERROR` - unexpected server error during the SSO flow.

### Troubleshooting

- `PROVIDER_MISCONFIGURED`: verify issuer URL, client ID/secret, and that discovery and JWKS endpoints are reachable.
- `ID_TOKEN_INVALID`: confirm the IdP `iss` matches the configured issuer and that `aud` includes the client ID.
- `TOKEN_EXCHANGE_FAILED`: check the token endpoint URL, client authentication method, and PKCE verifier length.
- `EMAIL_MISSING`: ensure the IdP returns an email claim and that `scope` includes `email`.
- `EMAIL_NOT_VERIFIED` or `DOMAIN_NOT_ALLOWED`: verify IdP email verification settings and provider domain allow-lists.
- `AUTO_PROVISION_DISABLED`: enable `ADE_AUTH_SSO_AUTO_PROVISION` if you want new SSO users to be created automatically.

## Security dependencies

Routers share dependencies from `ade_api.core.http.dependencies` so OpenAPI documents auth requirements consistently:

- `require_authenticated` ensures a `User` is attached to the request.
- `require_global(<permission>)` / `require_workspace(<permission>)` enforce RBAC via the principal-aware authoriser and surface
  structured 403 responses with permission and scope context.
- `require_csrf` enforces double-submit CSRF for cookie-authenticated unsafe methods.
- OpenAPI marks only `/health`, `/auth/providers`, `/auth/sso/providers`, `/auth/setup` (GET/POST), `/auth/cookie/login`,
  `/auth/jwt/login`, `/auth/register`, and SSO authorize/callback as public; everything else inherits the default security schemes.

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
