# Work Package: OAuth / OIDC Login Rollout

## Status
- **Owner:** Platform Squad
- **Last Reviewed:** 2025-10-09
- **State:** Implementation – Milestone 1 ready for review

> **Update (2025-10-09):** Backend and SPA changes for the environment-driven SSO flow have landed. The service enforces the
> hardened validation rules, provisioning policy, and cache behaviour; the frontend now handles the `/auth/callback` exchange
> and honours post-login redirects. Remaining notes below capture verification highlights and follow-up considerations for
> subsequent milestones.

## Milestone 1 Summary
- Environment toggles documented and wired through `Settings`, including HTTPS issuer/redirect validation and domain allowlist
  normalisation.【F:ade/settings.py†L256-L548】
- Auth service enforces PKCE S256, nonce/state validation, SSRF protections, bounded metadata/JWKS caches, strict token checks,
  and deterministic provisioning with the documented auto-provision/domain rules.【F:ade/features/auth/service.py†L700-L1189】
- API router issues scoped state cookies, clears them on callback, and returns the redirect hint consumed by the SPA
  callback handler.【F:ade/features/auth/router.py†L487-L566】【F:frontend/src/features/auth/routes/SsoCallbackRoute.tsx†L1-L74】
- Operator docs and `.env.example` now present the OIDC + SSO variables together with rollout guidance.【F:.env.example†L52-L59】【F:docs/authentication.md†L33-L78】
- Regression tests cover return-target sanitisation, provisioning toggles, domain allowlist, and frontend callback UX alongside
  the existing router tests.【F:ade/features/auth/tests/test_sso.py†L1-L121】【F:frontend/src/test/ssoCallbackRoute.test.tsx†L1-L65】

## Objective
Stabilise the environment-driven OAuth/OIDC login flow so administrators can enable SSO reliably before we build GUI-based configuration.

## Current State Findings
- `Settings` automatically flips `oidc_enabled` on when the client id, secret, issuer, and redirect URL are all supplied. Scopes are normalised from either JSON or comma-separated strings, and provider metadata for discovery is parsed into structured `AuthProviderSettings` objects.【F:ade/settings.py†L335-L592】
- Every toggle exposed via environment variables maps through the `Settings` defaults (e.g. `auth_force_sso=False`, safe JWT secrets, permissive redirect placeholders), so ADE boots with a working local-auth stack even when no OAuth variables are present.【F:ade/settings.py†L207-L335】
- The auth service already implements the PKCE authorisation code flow: it builds state + nonce JWTs, requests the provider metadata, exchanges the code, and validates both ID/access tokens through JWKS. Successful logins reuse the existing provisioning path that creates or reactivates users and assigns the default global role.【F:ade/features/auth/service.py†L528-L1120】
- `/auth/sso/login` and `/auth/sso/callback` are exposed as unauthenticated endpoints. The login route issues a signed state cookie, requires PKCE, and redirects to the IdP; the callback verifies the code/state pair, rejects mismatches, and establishes the ADE session.【F:ade/features/auth/router.py†L487-L569】
- The service provisions missing users immediately and flags them as active, but there is no operator control for auto-provisioning or merge behaviour when a matching email already exists under the built-in auth backend.【F:ade/features/auth/service.py†L763-L884】
- The FastAPI settings layer enforces the `ADE_` environment prefix and automatically maps fields such as `auth_force_sso` and `auth_providers` to predictable names, so any new toggles need to stay aligned with the existing `ADE_AUTH_*` / `ADE_OIDC_*` families.【F:ade/settings.py†L184-L360】
- `.env.example` only lists the base OIDC variables (client ID/secret, issuer, redirect, scopes) and never surfaces `ADE_AUTH_FORCE_SSO` or other auth toggles, leaving administrators without a documented naming template for the extra knobs we plan to introduce.【F:.env.example†L56-L65】
- Automated coverage only asserts the state-mismatch guard at the callback layer. There are no positive-path tests for the handshake, metadata caching, or failure modes like discovery/token exchange errors.【F:ade/features/auth/tests/test_router.py†L360-L439】

> **Note:** Current implementation already signs the state cookie and enforces PKCE, but cookie flags (`Secure`, `HttpOnly`, `SameSite`) and token-claim validation rules need to be documented and hardened to avoid regressions during the rollout.

## Risks & Open Questions
- OIDC configuration currently insists on a client secret even though PKCE technically allows public clients; confirm whether we must support secret-less native apps in the first milestone.
- Metadata and JWKS caches never expire. We rely on process restarts to pick up key rotations.
- We only accept a single IdP; future multi-tenant requirements might need per-workspace overrides or multiple providers in discovery.
- Need explicit guidance on forced SSO rollouts: should `force_sso` disable local credentials entirely and how does that interact with emergency admin access?
- Clarify the provisioning policy when an SSO login arrives for a new email. Do we auto-create users by default, gate on an `SSO_AUTO_PROVISION` flag, or require manual invitation? How should we handle duplicates when multiple users share the same email?
- Confirm the naming convention for new provisioning toggles so we do not introduce inconsistent environment variables once force-SSO and auto-provision controls ship.【F:ade/settings.py†L184-L360】
- Discovery SSRF: ensure `issuer` is HTTPS and public; block non-HTTPS schemes, private networks, and oversized responses.
- Token validation: specify allowed signing algorithms, reject `none`, and validate `iss`/`aud` (and `azp` when applicable), time-based claims, and nonce.

## Deliverables
1. Hardened backend flow that gracefully handles metadata/token failures and logs actionable errors.
2. Regression tests covering successful logins, expected failure modes, and cache behaviour with mocked IdP responses.
3. Operator documentation that explains the required environment variables, redirect URL expectations, and troubleshooting steps alongside the RBAC docs.
4. Clear configuration model for SSO provisioning controls, including environment variables for `force_sso`, auto-provisioning, and optional allowed email domains.
5. Explicit token validation policy (allowed algorithms, claim checks, clock skew) and PKCE enforcement captured in both docs and implementation.
6. Bounded, refreshable caches for provider metadata and JWKS, with visibility into refresh failures.
7. Break-glass procedure documented and validated for forced-SSO deployments.

## Plan

Phases 1–3 below are now implemented (see linked modules/tests). Keep the detail for historical context and future
regressions; new work should focus on the remaining gaps called out in the Risks and Phase 4 documentation tasks.

### Phase 1 – Configuration & Validation
- Add stricter validation for `oidc_redirect_url` (require HTTPS or resolve relative paths against `server_public_url`) and surface clearer startup errors when required env vars are missing or malformed.
- Decide whether to allow secret-less clients; if so, treat the secret as optional in settings while ensuring HTTP Basic is skipped when absent.
- Lock in the naming plan for SSO provisioning controls (e.g. `ADE_AUTH_FORCE_SSO`, `ADE_AUTH_SSO_AUTO_PROVISION`, optional allowed-domain list), update `.env.example`, and extend `docs/authentication.md` so operators see consistent, descriptive knobs while keeping sensible defaults that leave SSO disabled unless explicitly configured.【F:ade/settings.py†L207-L360】【F:.env.example†L56-L65】 Document the new toggles immediately beneath the existing OIDC sample block so administrators can copy the complete environment configuration in one place.【F:.env.example†L56-L65】
- Extend `.env.example` and `docs/authentication.md` with the expected redirect path, scope guidance, and notes on default role assignment for new SSO users.
- Validate the issuer/discovery URL to mitigate SSRF: enforce HTTPS, block private network ranges, restrict redirects, and set httpx connect/read timeouts plus a bounded response size.
- Document cookie requirements for state/session: `Secure`, `HttpOnly`, `SameSite=Lax` (or `None`+`Secure` if cross-site), and ensure the state token has a short TTL.
- Add an allowlist for `next` redirect targets (same-origin paths only) to prevent open redirects.

### Phase 2 – AuthService Hardening
- Ensure metadata and token exchange paths surface actionable errors while preserving the current structured logging approach.
- Implement bounded caches with TTL or proactive refresh for provider metadata and JWKS keys so key rotations do not require process restarts.
- Ensure `_resolve_sso_user` respects RBAC invariants (e.g. default global role slug still exists) and fails fast with actionable errors when assignments are missing.
- Define the standard provisioning policy: reuse existing users when emails match, auto-provision new users when allowed, and block conflicting duplicates with actionable errors.
- Require PKCE `S256`, rejecting `plain`, and validate `code_verifier` length and entropy.
- Enforce the token validation policy: allowed `alg`, strict `iss`, `aud`/`azp` checks, `exp`/`nbf`/`iat` validation with clock skew, and nonce handling.
- Document how external SSO identities (issuer + subject) are recorded against users for auditability.

### Phase 3 – Testing
- Build async unit tests that mock httpx + PyJWKClient to simulate: successful handshake, metadata 4xx/timeout, token exchange failure, bad ID token claims, and resource audience validation.
- Add service-level tests covering cache hit/miss paths, nonce/state expiry, and JWKS rotation (unknown `kid` → refresh → success).
- Cover provisioning permutations in tests: force-SSO-enabled instance with disabled local auth, auto-provision toggled on/off, and duplicate-email conflict handling.
- Add negative tests for issuer/discovery SSRF defences, open-redirect attempts on `next`, and clock-skew edges on token validation.

### Phase 4 – Documentation & Rollout Prep
- Update `docs/authentication.md` and `docs/permission_catalog.md` with the OAuth setup narrative, including RBAC implications for newly provisioned users.
- Draft operator runbook entries describing rotating client secrets, invalidating caches, and troubleshooting common 4xx/5xx responses from IdPs.
- Document force-SSO rollout guidance, including emergency break-glass access, expected environment variables, and user provisioning policies.
- Capture follow-up work to design GUI-based configuration once env-based flow is stable.
- Add provider-specific quickstarts (Okta, Auth0, Azure AD, Keycloak) with example values and screenshots for consistency.

## Provisioning Policy (M1)
- If the IdP email matches an existing ADE user, sign that user in and persist the external identity (issuer + subject) against the account.
- If there is no email match and `ADE_AUTH_SSO_AUTO_PROVISION=true`, create the user with the default global role; otherwise deny the login with a "not invited" error.
- Never create duplicates for the same email. If the email belongs to another user that already has an SSO identity, deny the login and emit an actionable log for administrators.
- Trust the IdP-supplied email value in M1; no additional verification or `userinfo` fallback is required.

## Testing Strategy
- `pytest` with httpx/JWK mocks for AuthService.
- `pytest` router-level tests covering redirects and session establishment.
- `mypy` + `ruff` on touched modules.
- `bandit` on updated auth modules for security linting.

## Out of Scope
- Building the GUI configuration surface or precedence rules between env vars and settings UI.
- Supporting workspace-specific IdPs.
- Non-OIDC OAuth providers (Google, GitHub) that do not expose OpenID Connect metadata.
- Device code/CLI flow, SCIM provisioning, or dynamic client registration.
- Logout integration via `end_session_endpoint` or front-/back-channel logout flows.

## Configuration knobs (to add to `.env.example` and docs)
- `ADE_AUTH_FORCE_SSO` (bool; default `false`).
- `ADE_AUTH_SSO_AUTO_PROVISION` (bool; default `true`).
- `ADE_AUTH_SSO_ALLOWED_DOMAINS` (csv; optional).

## Security & Compliance Checklist
- Issuer/discovery hardening (HTTPS only, no private IPs), bounded httpx timeouts, and capped response size.
- Enforce PKCE `S256`; strong `code_verifier` constraints.
- Token validation: allow only `RS256`/`ES256`, reject `none`; strict `iss`/`aud`/`azp`; validate `exp`/`nbf`/`iat` with clock skew; require nonce.
- State cookie: signed, short TTL, `Secure`, `HttpOnly`, `SameSite` appropriate for deployment.
- Session cookie: `Secure`, `HttpOnly`, `SameSite`; rotate on login and document TTL.
- Prevent open redirects on `next` parameter (same-origin paths only).
- JWKS caching with TTL and background refresh; handle unknown `kid` gracefully.
- Structured logs that avoid PII/secrets while emitting counters/latency histograms for SSO interactions.

## Operational Rollout Checklist
1. Configure IdP redirect URIs and verify discovery works in staging.
2. Ensure the default global role exists and is referenced correctly for provisioning.
3. (Optional) Configure `ADE_AUTH_SSO_ALLOWED_DOMAINS` before rollout.
4. Test break-glass access; store credentials securely; verify the audit trail for emergency use.
5. Enable SSO alongside local auth; monitor login success/failure counts and latency.
6. Flip `ADE_AUTH_FORCE_SSO` after verification, keeping break-glass procedures documented and tested.
