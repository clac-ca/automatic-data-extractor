## Context
Administrators needed a complete API key lifecycle with visibility into issued keys, the ability to revoke compromised secrets, and audit trails for both API key usage and SSO logins. The previous iteration only issued keys; operators had to dig in the database for metadata and incidents went unrecorded.

## Outcome
- Implemented `GET /auth/api-keys` and `DELETE /auth/api-keys/{api_key_id}` plus matching CLI commands so admins can list, inspect last-seen metadata, and revoke keys from either interface.
- Centralised API key event logging in the auth service; creation and revocation now emit `auth.api_key.*` events with actor context from both API and CLI flows.
- Extended the SSO callback to emit `auth.sso.login.succeeded` and `auth.sso.login.failed` events (failures commit immediately so they survive rollbacks).
- Added regression tests covering API key listing, revocation, and SSO failure auditing alongside updates to existing SSO success expectations.
- Documented the workflows with new "SSO login quick start" and "API key management" guides, refreshed navigation, and updated the integration overview to reference the management endpoints.
