---
Audience: Platform administrators, Security teams
Goal: Explain ADE's authentication model and document the minimal configuration required to operate it safely.
Prerequisites: Ability to manage environment variables, restart ADE, and provision user accounts.
When to use: Enable or disable authentication, rotate the signing secret, or review how operators obtain API access.
Validation: After updating settings, restart ADE, call `POST /auth/token`, and verify protected routes reject unsigned requests.
Escalate to: Security lead if tokens stop validating, secrets leak, or anonymous access is observed unexpectedly.
---

# Authentication

ADE's authentication stack is intentionally small. Users authenticate with an email/password pair and receive a JSON Web Token
(JWT). The token must accompany every subsequent request via the standard `Authorization: Bearer <token>` header.

There is **no session state or API key subsystem**. Removing those pieces makes the code auditable, avoids hidden database writes,
and keeps operational knobs to a minimum.

## 1. Configure the signer

All tokens are signed with a symmetric key. Set the following environment variables before starting the API:

| Variable | Default | Notes |
| --- | --- | --- |
| `ADE_JWT_SECRET_KEY` | _(unset)_ | Required unless authentication is explicitly disabled. Use a high-entropy value. |
| `ADE_JWT_ALGORITHM` | `HS256` | Algorithm passed to PyJWT. Stick with the default unless you control all clients. |
| `ADE_ACCESS_TOKEN_EXP_MINUTES` | `60` | Minutes until an issued token expires. Shorter lifetimes reduce blast radius. |
| `ADE_AUTH_DISABLED` | `false` | Set to `true` to bypass authentication entirely for local demos. Never use in production. |

Settings are cached on startup. In development you can call `config.reset_settings_cache()` to re-read the environment without a
restart.

`validate_settings()` runs during app start-up and fails fast if authentication is enabled without a signing key. When
`ADE_AUTH_DISABLED=true`, the API logs a loud warning and treats every request as an "anonymous" administrator, mirroring the
previous development-only behaviour.

## 2. Issue tokens

Clients obtain a token by POSTing form-encoded credentials to `/auth/token`:

```bash
curl -X POST https://ade.internal/auth/token \
  -H "content-type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=secret123"
```

Successful responses contain:

```json
{"access_token": "<JWT>", "token_type": "bearer"}
```

The token encodes the user ID, email address, role, and expiry. ADE verifies `exp` and `iat` on every request. Expired tokens
raise `401 Token expired` and callers must authenticate again.

The `/auth/me` endpoint returns the current user's profile, making it easy to confirm which identity a token represents.

## 3. Secure routes

Protected routers declare `Depends(auth_service.get_current_user)`. The dependency decodes the bearer token, looks up the user,
and injects the ORM model into your handler. For event logging, call `auth_service.event_actor_from_user(current_user)` to obtain
consistent `actor_*` metadata.

Example route snippet:

```python
from fastapi import APIRouter, Depends
from backend.app.services import auth as auth_service
from backend.app.models import User

router = APIRouter(prefix="/reports", dependencies=[Depends(auth_service.get_current_user)])

@router.get("/me")
def who_am_i(current_user: User = Depends(auth_service.get_current_user)) -> dict[str, str]:
    return {"email": current_user.email, "role": current_user.role.value}
```

If a request omits the header or the token fails verification, FastAPI returns `401 Not authenticated` with a `WWW-Authenticate:
Bearer` challenge, signalling clients to re-authenticate.

## 4. Manage users

Use the CLI helpers defined in `backend/app/services/auth.py`:

```bash
python -m backend.app auth create-user admin@example.com --password change-me --role admin
python -m backend.app auth set-password analyst@example.com --password new-secret
python -m backend.app auth list-users
```

CLI commands operate directly on the database and log structured messages (`user.created`, `user.password-updated`) for audit
trails. Passwords are hashed with the standard library `hashlib.scrypt` parameters defined in the same module.

## 5. Development shortcuts

For rapid prototyping you can disable authentication entirely by setting `ADE_AUTH_DISABLED=true`. The server logs a warning and
injects a synthetic administrator user so existing dependencies continue to work. Remember to remove the override before
shipping any build beyond local development.

## Validation checklist

- `POST /auth/token` succeeds for known credentials and fails for incorrect ones.
- `GET /auth/me` returns the expected email and role when presented with the issued token.
- Requests without `Authorization: Bearer` headers are rejected with `401 Not authenticated`.
- Tokens with manipulated signatures or expired timestamps raise `401 Invalid token`.
- CLI user management commands run without errors and emit audit logs.

This simplified model keeps the authentication surface small, auditable, and easy to operate.
