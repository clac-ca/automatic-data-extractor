# Manage Runtime Settings

## Goal

Update runtime-admin settings with one consistent model:

1. Environment override (highest priority)
2. Database value (`application_settings.data`)
3. Code default

## Hard-Cutover Notes

- Authentication policy now uses `auth.mode` and method-scoped settings.
- Old auth runtime keys are removed.
- Old auth env vars are removed and invalid
  (`ADE_AUTH_EXTERNAL_ENABLED`, `ADE_AUTH_FORCE_SSO`,
  `ADE_AUTH_SSO_AUTO_PROVISION`, `ADE_AUTH_ENFORCE_LOCAL_MFA`).
- Existing environments should reset `application_settings.data` to `{}`
  (or seed the new shape) before starting the updated app.

## Permissions

- `system.settings.read` to read settings
- `system.settings.manage` to update settings

## Read Current Effective Settings

```bash
curl -sS \
  -H "X-API-Key: <admin-api-key>" \
  http://localhost:8001/api/v1/admin/settings
```

Response includes:

- `schemaVersion`
- `revision`
- `values` (effective values)
- `meta` (`source`, `lockedByEnv`, `envVar`, `restartRequired` per field)
- `updatedAt`, `updatedBy`

## Runtime Fields

| Field | Type | Default | Env Override |
| --- | --- | --- | --- |
| `safeMode.enabled` | boolean | `false` | `ADE_SAFE_MODE` |
| `safeMode.detail` | string | built-in safe mode message | `ADE_SAFE_MODE_DETAIL` |
| `auth.mode` | enum | `password_only` | `ADE_AUTH_MODE` |
| `auth.password.resetEnabled` | boolean | `true` | `ADE_AUTH_PASSWORD_RESET_ENABLED` |
| `auth.password.mfaRequired` | boolean | `false` | `ADE_AUTH_PASSWORD_MFA_REQUIRED` |
| `auth.password.complexity.minLength` | integer | `12` | `ADE_AUTH_PASSWORD_MIN_LENGTH` |
| `auth.password.complexity.requireUppercase` | boolean | `false` | `ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE` |
| `auth.password.complexity.requireLowercase` | boolean | `false` | `ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE` |
| `auth.password.complexity.requireNumber` | boolean | `false` | `ADE_AUTH_PASSWORD_REQUIRE_NUMBER` |
| `auth.password.complexity.requireSymbol` | boolean | `false` | `ADE_AUTH_PASSWORD_REQUIRE_SYMBOL` |
| `auth.password.lockout.maxAttempts` | integer | `5` | `ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS` |
| `auth.password.lockout.durationSeconds` | integer | `300` | `ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS` |
| `auth.identityProvider.provisioningMode` | enum (`disabled`, `jit`, `scim`) | `jit` | `ADE_AUTH_IDP_PROVISIONING_MODE` |

`auth.mode` values:

- `password_only`
- `idp_only`
- `password_and_idp`

## Update Settings

`PATCH /api/v1/admin/settings` is atomic and partial.

- Always send the latest `revision`.
- Send only changed fields under `changes`.
- If any changed field is env-locked, the request fails with `409 setting_locked_by_env`.

Example: switch to mixed sign-in mode and require password MFA.

```bash
curl -sS -X PATCH \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <admin-api-key>" \
  http://localhost:8001/api/v1/admin/settings \
  -d '{
    "revision": 12,
    "changes": {
      "auth": {
        "mode": "password_and_idp",
        "password": {
          "mfaRequired": true,
          "resetEnabled": true
        },
        "identityProvider": {
          "provisioningMode": "jit"
        }
      }
    }
  }'
```

Example: harden password complexity and lockout.

```bash
curl -sS -X PATCH \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <admin-api-key>" \
  http://localhost:8001/api/v1/admin/settings \
  -d '{
    "revision": 13,
    "changes": {
      "auth": {
        "password": {
          "complexity": {
            "minLength": 14,
            "requireUppercase": true,
            "requireLowercase": true,
            "requireNumber": true,
            "requireSymbol": true
          },
          "lockout": {
            "maxAttempts": 5,
            "durationSeconds": 900
          }
        }
      }
    }
  }'
```

## SSO Setup Order

Provider setup and policy mode are separate by design:

1. Validate provider metadata: `POST /api/v1/admin/sso/providers/validate`
2. Create/update provider: `POST/PATCH /api/v1/admin/sso/providers*`
3. Activate provider: `PATCH /api/v1/admin/sso/providers/{id}` with `status=active`
4. Then switch `auth.mode` as needed in `PATCH /api/v1/admin/settings`

## Failure Handling

- `409 settings_revision_conflict`: re-read settings and retry with latest `revision`.
- `409 setting_locked_by_env`: env override owns that field.
- `422 active_provider_required`: `auth.mode=idp_only` requires at least one active provider.
- `422 validation_error`: unknown key/type mismatch or invalid value range.

## Verify

1. `GET /api/v1/admin/settings` shows expected `values` and `meta`.
2. DB-managed fields update immediately.
3. Env-managed fields show `lockedByEnv=true` and reject patch updates.
4. `revision` increments only when persisted data changes.

## Password Policy Consumers

`auth.password.*` runtime settings are enforced by:

- first-admin setup (`POST /api/v1/auth/setup`)
- user provisioning with explicit password (`POST /api/v1/users`, `passwordProfile.mode=explicit`)
- user provisioning with generated password (`POST /api/v1/users`, `passwordProfile.mode=auto_generate`)
- password reset (`POST /api/v1/auth/password/reset`)
- authenticated password change (`POST /api/v1/auth/password/change`)
