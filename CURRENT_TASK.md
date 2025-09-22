# 🔄 Next Task — Finish API key lifecycle management and audit coverage

## Context
API keys can now be issued, but administrators cannot inspect existing keys, rotate them, or see when they were last used. We
also lack audit events for API key creation and SSO logins. The next iteration should expose the lifecycle endpoints and surface
activity so operators can manage credentials without digging into the database.

## Goals
1. Provide read/revoke endpoints for API keys, including last-seen metadata and optional expiry updates.
2. Emit structured events whenever API keys are issued or revoked and when SSO logins succeed or fail.
3. Update documentation and OpenAPI descriptions to reflect the management APIs and new audit fields.

## Plan of attack
1. **API key listing/revocation**
   * Add `GET /auth/api-keys` (admin-only) returning issued keys with `token_prefix`, `expires_at`, and last-seen metadata.
   * Implement `DELETE /auth/api-keys/{api_key_id}` to revoke keys immediately and clear their hashes.
   * Extend the CLI with `list-api-keys`/`revoke-api-key` commands that wrap the new service functions.

2. **Audit events and logging**
   * Record `auth.api_key.created`/`auth.api_key.revoked` events with actor metadata, and `auth.sso.login.*` events capturing
     provider, email, and outcome.
   * Ensure events reuse the existing event recording service so they appear in `/events` feeds.

3. **Docs and OpenAPI refresh**
   * Document the new endpoints and CLI commands in the authentication guides and reference tables.
   * Update the OpenAPI schema to describe the API key response model and the new audit events.

## Definition of done
- Administrators can list and revoke API keys via API or CLI, and responses include last-seen information.
- SSO logins and API key lifecycle actions emit audit events visible through the existing event APIs.
- Documentation and OpenAPI reflect the management endpoints and describe the new audit signals.
