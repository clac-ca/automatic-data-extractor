---
Audience: Platform administrators
Goal: Configure and validate ADE's OIDC SSO integration, including recovery procedures for rotating secrets or clearing caches.
Prerequisites: Identity provider credentials (client ID, client secret), redirect URL registered with the provider, and ADE admin access.
When to use: Enable SSO for the first time, rotate secrets/keys, or troubleshoot login issues specific to the OIDC flow.
Validation: Complete a full login via `/auth/sso/login`, inspect logs for cache behaviour, and confirm `user.sso.login.*` events are recorded.
Escalate to: Security team or identity provider owners if tokens fail validation or cache resets do not resolve login errors.
---

# SSO setup and recovery

ADE's SSO support lives in `backend/app/auth/sso.py` and relies on configuration values loaded through `backend/app/config.py`. The flow implements standard OIDC code exchange with cached discovery and JWKS responses.

## Prerequisites

- An OIDC provider capable of issuing ID tokens signed with RS256.
- Registered redirect URL pointing to `https://<your-domain>/auth/sso/callback`.
- Client credentials (ID and secret) supplied by the provider.
- Existing ADE admin account to configure environment variables and monitor events.

## Configure environment variables

Set the following variables (see [Environment variables](../reference/environment-variables.md)):

| Variable | Purpose |
| --- | --- |
| `ADE_AUTH_MODES` | Include `sso` (e.g., `basic,sso`). |
| `ADE_SSO_CLIENT_ID` | OIDC client identifier. |
| `ADE_SSO_CLIENT_SECRET` | Secret used for token exchange and state signing. |
| `ADE_SSO_ISSUER` | Provider base URL (used to fetch discovery document). |
| `ADE_SSO_REDIRECT_URL` | Redirect/callback URL registered with the provider. |
| `ADE_SSO_AUDIENCE` | Optional expected audience; defaults to the client ID. |
| `ADE_SSO_SCOPES` | Requested scopes (default `openid email profile`). |
| `ADE_SSO_CACHE_TTL_SECONDS` | Cache lifetime (seconds) for discovery + JWKS responses. |
| `ADE_SSO_AUTO_PROVISION` | `true` to create users automatically when allowed. |

Restart ADE after updating environment variables to ensure settings reload.

## How discovery and caching work (`backend/app/auth/sso.py`)

- Discovery and JWKS payloads are cached in-memory keyed by issuer/JWKS URI.
- Cache entries expire after `ADE_SSO_CACHE_TTL_SECONDS` seconds.
- Unknown keys or expired tokens raise `SSOExchangeError` immediately, even when cached data exists.
- State tokens are HMAC-signed using the client secret and expire after five minutes.

To clear caches manually (e.g., after rotating keys), open a Python shell in the deployment and run:

```python
from backend.app.services import auth as auth_service

auth_service.clear_caches()
```

Alternatively, restart the service to drop caches.

## Validation steps

1. Visit `/auth/sso/login` in a browser to trigger the redirect to the provider.
2. Complete the provider login. ADE exchanges the code for tokens and validates the ID token signature.
3. On success, ADE sets the standard session cookie and redirects back to the UI root.
4. Inspect application logs for `SSO` messages noting cache reuse or refresh.
5. Query `/events?event_type=user.sso.login.success` (or inspect the per-user timeline) to confirm the login event recorded with `source="sso"`.

If login fails, review logs for `SSOConfigurationError` (missing settings) or `SSOExchangeError` (failed discovery, JWKS retrieval, or token validation).

## Recovery procedures

### Rotate secrets or keys

1. Update `ADE_SSO_CLIENT_SECRET` (and other credentials) in the environment.
2. Call `auth_service.clear_caches()` or restart the service.
3. Validate by logging in again and confirming events and logs reflect the new run.

### Clear stale caches without redeploying

- Use the `clear_caches()` helper above when providers rotate keys unexpectedly.
- Monitor logs for `Failed to load OIDC discovery document` errors; repeated failures may indicate provider downtime.

### Disable SSO temporarily

- Remove `sso` from `ADE_AUTH_MODES` or set `ADE_AUTH_MODES=basic`.
- Restart ADE. Users fall back to existing basic credentials.
- Re-enable SSO once the identity provider stabilises; document the outage in runbooks.

Escalate if repeated cache clears do not resolve signature errors or if `/auth/sso/login` continues to fail with valid credentials—this often signals provider-side issues or clock skew between ADE and the identity platform.
