# Authentication Architecture

This document explains how requests are authenticated in Automatic Data Extractor (ADE), how the FastAPI dependencies enforce
permissions, and what operators should consider when extending the system. It complements the RBAC documentation by focusing on
identity, session, and credential handling.

## Identity Sources

ADE recognises three credential types and normalises them into an `AuthenticatedIdentity` object before any route code runs:

1. **Session cookies** – the primary browser flow. The access token lives in the session cookie and the refresh token is issued in
a sibling cookie with the same session identifier. CSRF tokens are minted alongside the JWT pair and must accompany mutating
requests.【F:app/features/auth/service.py†L305-L370】
2. **Bearer access tokens** – typically produced by the `/auth/session` endpoints. They are decoded with the same signing secret as
sessions and skip CSRF enforcement because they are intended for non-browser clients.【F:app/features/auth/dependencies.py†L33-L68】
3. **API keys** – created through the admin UI or CLI. The raw token is shown once and clients must provide it via the
`X-API-Key` header. API keys reuse the principal model so they participate in the same RBAC assignments.【F:app/features/auth/dependencies.py†L69-L90】【F:app/features/auth/service.py†L52-L103】

`get_current_identity` prefers bearer tokens, then session cookies, then API keys. Regardless of the path, the dependency
ensures the backing `User` has a corresponding `Principal` record so downstream permission checks operate on principals
exclusively.【F:app/features/auth/dependencies.py†L33-L90】

## Session Lifecycle

* `AuthService.start_session` issues a new session identifier, access token, refresh token, and CSRF token. The tokens embed the
session identifier and hashed CSRF token so a refresh can rotate everything while keeping the same session id when desired.
* `AuthService.apply_session_cookies` writes the access and refresh cookies with `httponly`, `lax` SameSite, and a refresh path
tied to `/api/v1/auth/session/refresh`. Secure cookies are used whenever the request is served over HTTPS.【F:app/features/auth/service.py†L305-L370】【F:app/features/auth/service.py†L420-L468】
* `require_csrf` runs on every mutating endpoint. It only enforces CSRF for session-cookie identities and delegates to
`AuthService.enforce_csrf`, which compares the hashed token in the JWT with the submitted value.【F:app/api/security.py†L19-L40】

## Security Dependencies

All feature routers include the shared dependencies from `app/api/security.py` so that OpenAPI documents the requirements and
the responses are consistent.【F:app/api/security.py†L1-L121】

* `require_authenticated` guarantees a `User` is attached to the request. All routers mount this dependency once so individual
handlers can assume an authenticated context.【F:app/api/security.py†L15-L29】
* `require_global(<permission>)` and `require_workspace(<permission>)` call the principal-aware `authorize` helper to enforce
RBAC assignments. Workspace guards derive the scope identifier from path or query parameters and emit structured 403 payloads
when access is denied.【F:app/api/security.py†L42-L111】
* `require_permissions_catalog_access` protects the permissions catalogue endpoints and handles both global and workspace
scopes. It reuses the same forbidden payload shape and performs scope validation for workspace requests.【F:app/api/security.py†L113-L168】
* `require_csrf` must wrap every mutating route. A regression test walks the FastAPI routing table to ensure that any POST,
PUT, PATCH, or DELETE endpoint is guarded, excluding a small allowlist for session bootstrap flows.【F:app/api/tests/test_csrf_guards.py†L1-L85】

## RBAC Integration

After authentication, route-level guards always authorise using the principal identifier attached to the identity. Global and
workspace permissions are evaluated through the `authorize` facade, which resolves assignments, roles, and permissions using the
unified RBAC tables. Any failure produces a consistent 403 payload with the permission key and scope metadata to aid debugging
and client UX.【F:app/api/security.py†L42-L168】【F:app/features/roles/authorization.py†L1-L123】

## Extending the System

When introducing a new endpoint:

1. Mount the router with `dependencies=[Security(require_authenticated)]` so every request resolves an identity.
2. Add `Security(require_global(...))` or `Security(require_workspace(...))` to the endpoint signature with the exact permission
key that should gate access.
3. Include `dependencies=[Security(require_csrf)]` (or add it to the decorator) for any mutating route that should honour CSRF.
4. If the endpoint accepts a workspace id outside the default `workspace_id` parameter name, pass `scopes=["{<param>}"]` to the
workspace guard so `_resolve_workspace_param` picks it up.
5. Update tests to cover success and denial cases, and extend the RBAC work package if the permission model changes.

When adjusting authentication behaviour, update:

* `docs/authentication.md` (this document) with the new flow or credential type.
* `AGENTS.md` with a short note summarising the change for future automation runs.
* The security dependencies so OpenAPI stays accurate, and the CSRF regression test if new bootstrap routes are added.

## Troubleshooting Checklist

* **401 responses** usually mean `get_current_identity` could not resolve any credentials. Check token expiry, cookie domain, and
API key status.
* **403 responses** surface the required permission and scope. Confirm the principal has the right role assignment.
* **422 invalid_scope errors** arise when a workspace id is missing or named incorrectly. Ensure the route passes
`scopes=["{workspace_id}"]` or sets `scope_param` when calling `require_workspace`.
* **CSRF failures** occur when browser clients forget to send the `X-CSRF-Token` header that matches the cookie-issued token.

Keeping these pieces aligned ensures ADE’s authentication remains predictable, auditable, and easy to extend.
