## Context
The rebuilt FastAPI backend still lacked API key lifecycle management and a functional SSO callback, leaving automation clients without credentials and administrators unable to onboard users through the identity provider.

## Outcome
- Added an `APIKey` ORM model with repository/service helpers so keys can be issued, listed with metadata, authenticated via `X-API-Key`, and revoked while recording last-seen details.
- Exposed `POST /auth/api-keys`, `GET /auth/api-keys`, and `DELETE /auth/api-keys/{api_key_id}` endpoints guarded by the shared access-control decorator, plus integration tests covering rotation and revocation failure paths.
- Extended the auth dependency stack to accept API keys alongside JWTs, updating request context and throttled last-seen stamps for auditability.
- Implemented the SSO login redirect + callback flow using provider discovery, PKCE, and user provisioning/lookup, with tests asserting state-mismatch failures.
- Expanded configuration to cover SSO and API key settings so environments can enable the new authentication paths deterministically.
