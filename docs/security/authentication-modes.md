---
Audience: Platform administrators, Security teams
Goal: Compare ADE authentication modes and document the configuration steps for each, including session management.
Prerequisites: Ability to manage environment variables, restart ADE, and provision user accounts.
When to use: Decide which authentication mode to enable, adjust session cookie settings, or review password handling.
Validation: After updating settings, restart ADE, log in via `/auth/login/basic`, and confirm sessions behave as documented.
Escalate to: Security lead if login flows fail, password hashing drifts from policy, or unauthenticated access becomes possible unexpectedly.
---

# Authentication modes

Authentication is implemented in `backend/app/config.py`, `backend/app/auth/manage.py`, and `backend/app/auth/sessions.py`. ADE supports deterministic login behaviour with optional OIDC SSO layered on top of HTTP Basic and cookie sessions.

## 1. Choose an auth mode

Configure `ADE_AUTH_MODES` with a comma-separated list drawn from `basic`, `sso`, and `none`.

- `basic` — Enables HTTP Basic login plus cookie sessions (default).
- `sso` — Adds OIDC single sign-on endpoints; still relies on cookie sessions.
- `none` — Disables authentication entirely (use only for local demos). Cannot be combined with other modes.

API keys complement these modes for automation clients. Humans still log in with Basic or SSO to receive a session cookie; services send `Authorization: Bearer <API_KEY>` on every request.

Settings are parsed via `Settings.auth_mode_sequence`; invalid values raise a `ValueError` during startup.

### Environment variables

| Variable | Description |
| --- | --- |
| `ADE_AUTH_MODES` | Allowed modes: `none`, `basic`, `sso`. `none` must be the only value when used. |
| `ADE_SESSION_COOKIE_NAME` | Name of the issued session cookie (default `ade_session`). |
| `ADE_SESSION_TTL_MINUTES` | Session lifetime in minutes before expiry (default `720`). |
| `ADE_SESSION_COOKIE_SECURE` | `true` / `false`; mark cookies Secure. Required when SameSite=`none`. |
| `ADE_SESSION_COOKIE_SAME_SITE` | `lax`, `strict`, or `none`. Validated in `Settings._validate_same_site`. |
| `ADE_SESSION_COOKIE_DOMAIN` | Optional domain attribute for multi-host deployments. |
| `ADE_SESSION_COOKIE_PATH` | Path scope for the cookie (default `/`). |

Restart ADE after changing these variables or call `config.reset_settings_cache()` in development.

## 2. Configure session cookies (`backend/app/auth/sessions.py`)

- Session tokens are opaque values stored hashed (`SHA-256`) in the `user_sessions` table.
- The session cookie is HttpOnly and inherits Secure/SameSite flags from the environment configuration.
- Refreshing a session issues a new expiry (`session_ttl_minutes`) and records `user.session.refreshed` events.

Validation: Log in, inspect the `Set-Cookie` header, and ensure TTL, domain, and SameSite attributes match expectations.

## 3. Manage users via CLI (`backend/app/auth/manage.py`)

Use the bundled CLI to provision accounts even when the API is offline:

```bash
python -m backend.app.auth.manage create-user admin@example.com --password change-me --role admin
python -m backend.app.auth.manage reset-password admin@example.com --password another-secret
python -m backend.app.auth.manage deactivate user@example.com
python -m backend.app.auth.manage promote operator@example.com
python -m backend.app.auth.manage list-users
```

Each command emits `user.*` events (actor_type `system`, source `cli`) so audit logs record administrative actions.

## 4. Understand the login flow (`backend/app/routes/auth.py`)

1. Client submits HTTP Basic credentials to `POST /auth/login/basic`.
2. ADE validates credentials against the `users` table (passwords hashed with `hashlib.scrypt` using `N=16384`, `r=8`, `p=1`).
3. On success, ADE issues an opaque session token, stores its SHA-256 hash, and sets the cookie defined above.
4. Subsequent requests must present either the session cookie or `Authorization: Bearer <API_KEY>`. HTTP Basic and OAuth tokens are accepted only on the dedicated login endpoints.
5. `POST /auth/logout` revokes the hash and clears the cookie.

Password hashing policy lives entirely in the standard library; no external dependencies are required. Each stored hash records the original parameters, so verification always uses the same work factors.

## 5. API keys for automation

- **Header contract:** Integrations must send `Authorization: Bearer <API_KEY>` on every request. ADE verifies the hashed token stored in the `api_keys` table.
- **Storage:** Keys are stored hashed; distribute the raw token once at creation time. Rotation is a database operation until dedicated tooling ships.
- **Coexistence with sessions:** Human operators continue to rely on cookie sessions. API keys provide a deterministic credential for service accounts without impacting the UI.

Example client request using an API key:

```bash
curl -H "Authorization: Bearer $ADE_API_KEY" https://ade.example.com/documents
```

## Validation checklist

- Log in with HTTP Basic credentials and confirm a session cookie is issued.
- Call `POST /auth/refresh` and ensure the cookie expiry advances.
- Run `python -m backend.app.auth.manage list-users` to verify CLI access.
- Inspect `/events?event_type=user.session.*` to confirm authentication events are captured.

For SSO-specific configuration (client IDs, discovery caching, recovery), continue to [SSO setup and recovery](./sso-setup.md).
