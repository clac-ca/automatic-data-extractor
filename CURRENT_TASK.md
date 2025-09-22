# 🔄 Next Task — Add API key expiry updates and timeline coverage

## Context
Operators can now list and revoke API keys, but rotating automation credentials still requires issuing a brand-new key. Support teams have asked for a lighter-weight option to extend or shorten a key's lifetime without deleting it, and audit trails should reflect those changes so reviewers can see when a credential was extended. The next iteration should expose an update endpoint, surface the corresponding events, and teach admins how to use it.

## Goals
1. Allow administrators to update the `expires_at` timestamp for an existing API key via API or CLI.
2. Emit an `auth.api_key.updated` event (or similar) whenever an expiry change is applied, capturing the old/new values and actor metadata.
3. Document the expiry update workflow alongside the existing management guides and ensure the OpenAPI schema reflects the new endpoint.

## Plan of attack
1. **Endpoint & schema**
   * Add `PATCH /auth/api-keys/{api_key_id}` accepting either an absolute `expires_at` ISO timestamp or an `expires_in_days` window.
   * Reuse the service layer to validate input (no back-dating past now) and persist the new expiry.
2. **CLI integration & audits**
   * Introduce `auth update-api-key` CLI command mirroring the API behaviour.
   * Record `auth.api_key.updated` events with actor metadata and the previous/new expiry values; extend tests to cover the event payload.
3. **Docs & references**
   * Update the API key management guide and integration overview to explain how to adjust expiry.
   * Regenerate/refresh OpenAPI descriptions so consumers see the new request/response schema.

## Definition of done
- `PATCH /auth/api-keys/{api_key_id}` and the matching CLI command update expiry values with validation and return the updated metadata.
- Updating an API key emits an audit event alongside the existing create/revoke events.
- Documentation and OpenAPI mention the expiry update workflow and parameters.
