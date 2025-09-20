# Authentication overview

ADE supports HTTP Basic credentials, cookie-backed browser sessions, and optional OIDC single sign-on. Session cookies are
issued automatically whenever authentication is active, so deployments only toggle the primary mechanisms and whether auth is
disabled entirely.

## Environment variables

All configuration flows through `ADE_` environment variables. Common settings include:

| Variable | Description |
| --- | --- |
| `ADE_AUTH_MODES` | Comma separated list drawn from `none`, `basic`, `sso` (default: `basic`). `none` cannot be combined with other values. |
| `ADE_SESSION_COOKIE_NAME` | Session cookie name (default: `ade_session`). |
| `ADE_SESSION_TTL_MINUTES` | Expiry window for issued sessions. |
| `ADE_SESSION_COOKIE_SECURE` | Set to `1` to mark cookies as Secure; required when SameSite is `none`. |
| `ADE_SESSION_COOKIE_SAME_SITE` | Cookie SameSite policy (`lax`, `strict`, `none`). |
| `ADE_SSO_CLIENT_ID` / `ADE_SSO_CLIENT_SECRET` | Credentials for the configured OIDC client. |
| `ADE_SSO_ISSUER` | Base URL for the OIDC provider. |
| `ADE_SSO_REDIRECT_URL` | Callback URL registered with the provider. |
| `ADE_SSO_AUDIENCE` | Expected ID token audience (defaults to the client ID). |
| `ADE_SSO_CACHE_TTL_SECONDS` | Seconds to cache discovery metadata and JWKS responses. |

The service refuses to start if `ADE_AUTH_MODES` resolves to an empty set, combines `none` with another value, or if `sso` is
requested without the required issuer, client, secret, and redirect values.

## SSO validation

ADE verifies ID tokens signed with RS256. JWKS responses are keyed by `kid`, and an unknown key immediately raises a validation
error even when discovery metadata is cached. Both the discovery document and JWKS payloads reuse responses for `ADE_SSO_CACHE_TTL_SECONDS`
so subsequent exchanges avoid redundant network calls without tolerating expired or audience-mismatched tokens.

## User management CLI

Use the CLI to bootstrap and maintain accounts even when the API is offline:

```bash
python -m backend.app.auth.manage create-user admin@example.com --password change-me --role admin
python -m backend.app.auth.manage reset-password admin@example.com --password another-secret
python -m backend.app.auth.manage deactivate user@example.com
python -m backend.app.auth.manage promote operator@example.com
python -m backend.app.auth.manage list-users
```

CLI actions emit `user.*` events with `actor_type="system"` and `source="cli"`, keeping audit trails intact.

## Login flow summary

1. Clients authenticate with HTTP Basic. The login endpoint always issues an opaque session token, hashes it using SHA-256,
   stores the hash in `user_sessions.token_hash`, and returns the raw token as an HttpOnly cookie.
2. Subsequent requests prefer the session cookie. The `CurrentUser` dependency falls back to HTTP Basic and then `Authorization:
   Bearer` when SSO is configured.
3. SSO-enabled deployments expose `/auth/sso/login` and `/auth/sso/callback`. ADE validates the provider's discovery document,
   caches JWKS responses, verifies the ID token signature, and maps the `iss`/`sub` pair to a provisioned user.
4. Session refreshes extend the expiry window and emit `user.session.refreshed` events; logouts revoke the hash and clear the
   browser cookie.

## Password hashing

ADE hashes passwords with the Python standard library's `hashlib.scrypt` implementation. Each hash records the scrypt work
factors alongside a random 16-byte salt so verification always uses the original parameters. ADE derives a 32-byte key using
`N=16384`, `r=8`, and `p=1`, values that balance verification cost and operational headroom while keeping deployments predictable
without optional third-party dependencies.
