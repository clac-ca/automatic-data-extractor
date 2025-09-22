# Documentation Plan — Describe SSO login and API key usage plainly

## Goal
Document the reintroduced authentication options so operators and integrators know exactly how to use SSO redirects and API key
authentication without wading through legacy comparisons.

## Deliverables (execute in order)

1. **SSO quick-start page**

   * Create `docs/security/sso-login.md` that sketches the browser redirect → consent → callback sequence, shows the minimal
     environment variables (`ADE_SSO_CLIENT_ID`, `ADE_SSO_CLIENT_SECRET`, `ADE_SSO_ISSUER`, `ADE_SSO_REDIRECT_URL`), and explains
     that ADE issues its own access token after verifying the IdP’s ID/access token.
   * Include a short troubleshooting section covering common OIDC errors (mismatched redirect URI, missing audience, unverified
     email).

2. **API key how-to**

   * Update or create `docs/security/api-keys.md` describing how to generate a key (admin CLI/endpoint), how the key format works
     (`prefix.secret`), and how to send it via `X-API-Key`.
   * Note storage expectations (copy once, treat as a secret, rotate via the admin endpoint) and highlight that verification is
     constant-time with throttled last-seen updates.

3. **Navigation refresh**

   * Link both guides from `docs/security/README.md`, `docs/README.md`, and any relevant integration indexes.
   * Remove lingering references to the deprecated multi-mode auth stack so the documentation simply presents the current
     behavior.

## Out of scope

* Alternative providers or advanced SSO federation patterns (stick to the single-authority flow).
* UI-based key management (document API-first workflow only).

## Source material

* Simplified OIDC and API key implementation outlined in `CURRENT_TASK.md`.
* Existing FastAPI routes and identity helpers.
* Auth tests covering token verification, throttling, and uniqueness.

## Definition of done

* New or updated guides plainly explain how to complete an SSO login and how to call the API with an API key.
* Navigation surfaces both guides without referencing the retired authentication modes.
* Operators have actionable instructions without cross-referencing historical docs.
