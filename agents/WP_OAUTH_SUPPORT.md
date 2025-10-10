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
- `Settings` automatically flips `oidc_enabled` on when the client id, secret, issuer, and redirect URL are all supplied. Scopes are normalised from either JSON or comma-separated strings, and redirect paths are resolved against the public URL so deployments can copy a concise configuration block.【F:ade/settings.py†L361-L456】
- Every toggle exposed via environment variables maps through the `Settings` defaults (e.g. `auth_force_sso=False`, safe JWT secrets, permissive redirect placeholders), so ADE boots with a working local-auth stack even when no OAuth variables are present.【F:ade/settings.py†L207-L335】
- The auth service already implements the PKCE authorisation code flow: it builds state + nonce JWTs, requests the provider metadata, exchanges the code, and validates both ID/access tokens through JWKS. Successful logins reuse the existing provisioning path that creates or reactivates users and assigns the default global role.【F:ade/features/auth/service.py†L528-L1120】
- `/auth/sso/login` and `/auth/sso/callback` are exposed as unauthenticated endpoints. The login route issues a signed state cookie, requires PKCE, and redirects to the IdP; the callback verifies the code/state pair, rejects mismatches, and establishes the ADE session.【F:ade/features/auth/router.py†L487-L569】
- The service provisions missing users immediately when `ADE_AUTH_SSO_AUTO_PROVISION` is true, assigns the default global role, and persists the SSO identity; when disabled it returns a "not invited" error so administrators can reconcile access manually.【F:ade/features/auth/service.py†L870-L1459】
- The FastAPI settings layer enforces the `ADE_` environment prefix and automatically maps fields such as `auth_force_sso`, so any new toggles need to stay aligned with the existing `ADE_AUTH_*` / `ADE_OIDC_*` families.【F:ade/settings.py†L184-L335】
- `.env.example` documents the required OIDC variables alongside the rollout toggle (`ADE_AUTH_FORCE_SSO`) so operators can copy a complete configuration block.【F:.env.example†L58-L66】
- Automated coverage exercises state-mismatch guards, positive callback handshakes, and provisioning behaviour; the remaining gap is deeper failure-mode coverage for discovery/token exchange errors.【F:ade/features/auth/tests/test_router.py†L1-L140】【F:ade/features/auth/tests/test_sso.py†L1-L215】

> **Note:** Current implementation already signs the state cookie and enforces PKCE, but cookie flags (`Secure`, `HttpOnly`, `SameSite`) and token-claim validation rules need to be documented and hardened to avoid regressions during the rollout.

## Risks & Open Questions
- Auto-provisioning is now unconditional; confirm operators are comfortable with every verified IdP email creating an ADE user automatically.
- We only accept a single IdP; future multi-tenant requirements might need per-workspace overrides or multiple providers in discovery.
- Need explicit guidance on forced SSO rollouts: should `force_sso` disable local credentials entirely and how does that interact with emergency admin access?
- Discovery SSRF: ensure `issuer` is HTTPS and public; block non-HTTPS schemes, private networks, and oversized responses.
- Token validation: specify allowed signing algorithms, reject `none`, and validate `iss`/`aud` (and `azp` when applicable), time-based claims, and nonce.

## Deliverables
1. Hardened backend flow that gracefully handles metadata/token failures and logs actionable errors.
2. Regression tests covering successful logins and failure modes using mocked IdP responses.
3. Operator documentation that explains the required environment variables, redirect URL expectations, and troubleshooting steps alongside the RBAC docs.
4. Confirmed provisioning policy (automatic creation of new users) with operator sign-off and audit logging expectations.
5. Explicit token validation policy (allowed algorithms, claim checks, clock skew) and PKCE enforcement captured in both docs and implementation.
6. Break-glass procedure documented and validated for forced-SSO deployments.

## Plan

Phases 1–3 below are now implemented (see linked modules/tests). Keep the detail for historical context and future
regressions; new work should focus on the remaining gaps called out in the Risks and Phase 4 documentation tasks.

### Phase 1 – Configuration & Validation
- Add stricter validation for `oidc_redirect_url` (require HTTPS or resolve relative paths against `server_public_url`) and surface clearer startup errors when required env vars are missing or malformed.
- Require confidential clients by treating the client secret as mandatory whenever OIDC is enabled; incomplete configs should raise immediately.
- Keep `.env.example` and `docs/authentication.md` focused on the required OIDC variables plus `ADE_AUTH_FORCE_SSO`, noting the default role assignment for newly provisioned users.【F:.env.example†L58-L66】
- Document the default post-login behaviour (return-to hints, preferred workspace fallback) so the SPA and backend narratives stay aligned.
- Validate the issuer/discovery URL to mitigate SSRF: enforce HTTPS, block private network ranges, restrict redirects, and set httpx connect/read timeouts plus a bounded response size.
- Document cookie requirements for state/session: `Secure`, `HttpOnly`, `SameSite=Lax` (or `None`+`Secure` if cross-site), and ensure the state token has a short TTL.
- Add an allowlist for `next` redirect targets (same-origin paths only) to prevent open redirects.

### Phase 2 – AuthService Hardening
- Ensure metadata and token exchange paths surface actionable errors while preserving the current structured logging approach.
- Keep metadata and JWKS fetch behaviour simple and deterministic; request discovery documents and keys on demand with tight timeouts instead of in-process caches.
- Ensure `_resolve_sso_user` respects RBAC invariants (e.g. default global role slug still exists) and fails fast with actionable errors when assignments are missing.
- Define the standard provisioning policy: reuse existing users when emails match, auto-provision new users, and block conflicting duplicates with actionable errors.
- Require PKCE `S256`, rejecting `plain`, and validate `code_verifier` length and entropy.
- Enforce the token validation policy: allowed `alg`, strict `iss`, `aud`/`azp` checks, `exp`/`nbf`/`iat` validation with clock skew, and nonce handling.
- Document how external SSO identities (issuer + subject) are recorded against users for auditability.

### Phase 3 – Testing
- Build async unit tests that mock httpx + token verification to simulate: successful handshake, metadata 4xx/timeout, token exchange failure, and bad ID token claims.
- Add service-level tests covering nonce/state expiry, JWKS retrieval errors, and duplicate-email conflict handling during provisioning.
- Cover provisioning permutations in tests: force-SSO-enabled instance with disabled local auth and duplicate SSO identity attempts.
- Add negative tests for issuer/discovery SSRF defences, open-redirect attempts on `next`, and clock-skew edges on token validation.

### Phase 4 – Documentation & Rollout Prep
- Update `docs/authentication.md` and `docs/permission_catalog.md` with the OAuth setup narrative, including RBAC implications for newly provisioned users.
- Draft operator runbook entries describing rotating client secrets, invalidating caches, and troubleshooting common 4xx/5xx responses from IdPs.
- Document force-SSO rollout guidance, including emergency break-glass access, expected environment variables, and user provisioning policies.
- Capture follow-up work to design GUI-based configuration once env-based flow is stable.
- Add provider-specific quickstarts (Okta, Auth0, Azure AD, Keycloak) with example values and screenshots for consistency.

## Provisioning Policy (M1)
- If the IdP email matches an existing ADE user, sign that user in and persist the external identity (issuer + subject) against the account.
- If there is no email match, create the user with the default global role and persist the new identity so subsequent logins reuse the same account.
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

## Security & Compliance Checklist
- Issuer/discovery hardening (HTTPS only, no private IPs), bounded httpx timeouts, and capped response size.
- Enforce PKCE `S256`; strong `code_verifier` constraints.
- Token validation: allow only `RS256`/`ES256`, reject `none`; strict `iss`/`aud`/`azp`; validate `exp`/`nbf`/`iat` with clock skew; require nonce.
- State cookie: signed, short TTL, `Secure`, `HttpOnly`, `SameSite` appropriate for deployment.
- Session cookie: `Secure`, `HttpOnly`, `SameSite`; rotate on login and document TTL.
- Prevent open redirects on `next` parameter (same-origin paths only).
- JWKS retrieval with tight timeouts; surface actionable errors when keys cannot be fetched.
- Structured logs that avoid PII/secrets while emitting counters/latency histograms for SSO interactions.

## Operational Rollout Checklist
1. Configure IdP redirect URIs and verify discovery works in staging.
2. Ensure the default global role exists and is referenced correctly for provisioning.
3. Test break-glass access; store credentials securely; verify the audit trail for emergency use.
4. Enable SSO alongside local auth; monitor login success/failure counts and latency.
5. Flip `ADE_AUTH_FORCE_SSO` after verification, keeping break-glass procedures documented and tested.
