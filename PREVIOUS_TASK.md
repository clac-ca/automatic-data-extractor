# ✅ Completed Task — Reintroduce SSO login and API keys with standard flows

## Context
We needed to restore single sign-on and programmatic credentials after simplifying the authentication stack to basic JWTs. The
implementation had to reuse standard OIDC flows, keep API key storage deterministic, and document the new behaviour.

## Outcome
- Added PKCE-based `/auth/sso/login` and `/auth/sso/callback` endpoints backed by cached OIDC discovery metadata, JWKS
  validation, and automatic user provisioning when `email_verified` is true.
- Implemented hashed API keys with last-seen throttling, CLI issuance, `X-API-Key` authentication, and updated request
  dependencies that gracefully support bearer tokens or API keys.
- Extended configuration, database models, migrations, and documentation to cover the new SSO and API key settings, refreshed
  the OpenAPI security schemes, and captured regression tests for both authentication paths.
