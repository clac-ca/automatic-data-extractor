# 🔄 Next Task — Reintroduce SSO login and API keys with simple, standard patterns

## Context
We stripped ADE down to local email/password sign-in with first-party JWTs. The next iteration should restore single sign-on for
human users and API keys for automation without reintroducing the sprawling auth matrix we removed. We can lean on standard OIDC
flows and deterministic token hashing so the implementation stays compact while matching industry expectations.

## Goals
1. **Rebuild SSO around a textbook OIDC authorization-code flow** using the discovery metadata we already cache and PyJWT for
   token validation.
2. **Provide programmatic access with hashed API keys** that reuse our existing identity wiring and touch throttling.
3. **Refresh docs and references to describe the new capabilities directly** (no legacy call-outs, because nothing in
   production depends on the old stack).

## Plan of attack
1. **SSO login (OIDC authorization-code + PKCE)**
   * Add config for `sso_client_id`, `sso_client_secret`, `sso_issuer`, `sso_redirect_url`, and a default scope string.
   * Expose `/auth/sso/login` that redirects to `{issuer}/authorize` with `response_type=code`, `code_challenge` (PKCE),
     `client_id`, `redirect_uri`, and `scope`.
   * Implement `/auth/sso/callback` that exchanges the code at the provider’s token endpoint via `httpx`, validates the returned
     ID token with `verify_jwt_via_jwks`, and accepts only access tokens for downstream API calls (`audience = resource_audience`).
   * Map `sub`/`email` to an ADE user (auto-provision when `email_verified` is true), then issue our standard ADE access token so
     the rest of the stack keeps working unchanged.

2. **API key issuance and verification**
   * Define an `api_keys` table with `id`, `user_id`, `token_prefix`, `token_hash`, optional `expires_at`, timestamps, and
     uniqueness on `token_prefix`/`token_hash`.
   * Provide an admin CLI/endpoint that generates `prefix.random_secret`, stores `hash(secret)` (e.g., `hashlib.sha256` + base64),
     and returns the raw key once. Keep touch throttling so we update `last_seen` at most every few minutes.
   * Accept the key through an `X-API-Key` header, parse the prefix to narrow the lookup, compare hashes in constant time, and
     reuse `get_authenticated_identity` to attach the user.

3. **Documentation refresh**
   * Update `README.md`, security docs, and integration guides to describe the SSO redirect/callback flow and API key usage at a
     high level.
   * Remove transitional notes about the now-removed legacy stack—simply document the new capabilities as the authoritative
     behavior.

## Definition of done
- Human users can authenticate through an external IdP via OIDC and receive ADE-issued JWTs for API access.
- Automation clients can use API keys backed by hashed storage and existing throttled touch semantics.
- Documentation explains both flows without referencing deprecated approaches.
