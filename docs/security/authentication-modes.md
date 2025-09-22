---
Audience: Platform administrators, Security teams
Goal: Explain ADE's authentication model and document the minimal configuration required to operate it safely.
Prerequisites: Ability to manage environment variables, restart ADE, and provision user accounts.
When to use: Enable or disable authentication, rotate the signing secret, or review how operators obtain API access.
Validation: After updating settings, restart ADE, call `POST /auth/token`, and verify protected routes reject unsigned requests.
Escalate to: Security lead if tokens stop validating, secrets leak, or anonymous access is observed unexpectedly.
---

# Authentication

ADE ships with three complementary authentication flows that all converge on the same authorisation checks:

1. **Email/password** – call `POST /auth/token` to receive a short-lived JWT.
2. **OIDC single sign-on** – redirect to `/auth/sso/login`, complete the provider's authorisation flow, and exchange the code at `/auth/sso/callback`.
3. **API keys** – issue hashed keys for automation clients and send them in the `X-API-Key` header.

## 1. Configure the core settings

| Variable | Default | Notes |
| --- | --- | --- |
| `ADE_AUTH_DISABLED` | `false` | Set to `true` only for local demos. All requests run as an administrator when disabled. |
| `ADE_JWT_SECRET_KEY` | _(unset)_ | Required whenever authentication is enabled. Use a high-entropy string. |
| `ADE_JWT_ALGORITHM` | `HS256` | Algorithm passed to PyJWT when signing ADE-issued tokens. |
| `ADE_ACCESS_TOKEN_EXP_MINUTES` | `60` | Lifetime for ADE access tokens returned by both password and SSO flows. |
| `ADE_SSO_CLIENT_ID` | _(unset)_ | OIDC client identifier used during `/auth/sso/login`. Required for SSO. |
| `ADE_SSO_CLIENT_SECRET` | _(unset)_ | Confidential client secret presented to the token endpoint. |
| `ADE_SSO_ISSUER` | _(unset)_ | Issuer URL used to download the discovery document and JWKS payloads. |
| `ADE_SSO_REDIRECT_URL` | _(unset)_ | Redirect URI registered with the identity provider (must match `/auth/sso/callback`). |
| `ADE_SSO_SCOPE` | `openid email profile` | Space-separated scope string requested during the authorisation step. |
| `ADE_SSO_RESOURCE_AUDIENCE` | _(unset)_ | Optional audience to require on provider access tokens. Leave blank for IdPs that do not include an audience claim. |
| `ADE_API_KEY_TOUCH_INTERVAL_SECONDS` | `300` | Minimum gap between `last_seen` updates for API keys. Increase to reduce write load on busy integrations. |

`validate_settings()` runs during application start-up and fails fast if the signer or SSO configuration is incomplete.

## 2. Email/password tokens

The password flow remains a simple form-encoded POST. Clients submit credentials to `/auth/token` and receive a JSON payload
containing the access token:

```bash
curl -X POST https://ade.internal/auth/token \
  -H "content-type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=secret123"
```

The returned token embeds the user ID, email address, role, and expiry. Include it on subsequent calls via
`Authorization: Bearer <token>`. `GET /auth/me` resolves the current user and is useful for smoke tests or debugging new
integrations.

## 3. Single sign-on

Configure the OIDC environment variables listed above to enable `/auth/sso/login`. The endpoint performs the following steps:

1. Fetch and cache the provider discovery document to locate the authorisation and token endpoints.
2. Generate a PKCE code verifier/challenge pair plus a signed state cookie (`ade_sso_state`).
3. Redirect the browser to the provider's authorisation URL.

When the provider calls back into `/auth/sso/callback`, ADE exchanges the code, validates the RS256 ID token via the JWKS cache,
optionally enforces an access-token audience, and provisions the user automatically when `email_verified` is true. Successful
callbacks return the same ADE bearer token produced by the password flow, so the frontend and API clients do not need separate
handling.

## 4. API keys

Issue API keys for automation clients with the CLI:

```bash
python -m backend.app auth create-api-key analyst@example.com --expires-in-days 30
```

The CLI prints the raw key once. Store it securely and present it on every request using the `X-API-Key` header. ADE stores only
the prefix and a salted SHA-256 hash and updates the `last_seen_at`, `last_seen_ip`, and `last_seen_user_agent` columns at most
once per the configured touch interval. Keys automatically stop working after their optional expiry timestamp.

Use `GET /auth/api-keys` or `python -m backend.app auth list-api-keys` to review active keys, and `DELETE /auth/api-keys/{api_key_id}`
or `python -m backend.app auth revoke-api-key <api_key_id>` to revoke credentials immediately. Both creation and revocation emit
audit events so operators can track who issued or disabled a key.

## 5. Manage users and roles

User management is unchanged: use the CLI for provisioning and password resets. ADE
validates addresses with the `email-validator` library, stores the canonical form in
`users.email_canonical`, and keeps the original casing in `users.email` for display.
Lookups always use the canonical column so operators can sign in regardless of
case or Unicode composition.

```bash
python -m backend.app auth create-user admin@example.com --password change-me --role admin
python -m backend.app auth set-password analyst@example.com --password new-secret
python -m backend.app auth list-users
```

All commands emit structured logs for audit trails. Passwords continue to use `hashlib.scrypt` with fixed parameters in
`auth_service.hash_password()`.

## Validation checklist

- `POST /auth/token` succeeds for valid credentials and fails for invalid ones.
- `/auth/sso/login` redirects to the configured identity provider and `/auth/sso/callback` returns an ADE token for verified
  users.
- API requests with `X-API-Key` resolve to the expected user while malformed keys return `401 Invalid API key`.
- `GET /auth/me` returns the correct profile for both bearer tokens and API keys.
- Requests without credentials receive `401 Not authenticated` with a `WWW-Authenticate: Bearer` challenge.
- CLI user and API key commands run without errors and write audit logs.
