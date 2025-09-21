# ✅ Completed Task — Implement API key provisioning endpoints for operators

## Context
Authentication already trusts rows in the `api_keys` table, but administrators lacked a safe workflow for issuing or revoking credentials. This task aimed to expose a concise API so operators can mint, inspect, and revoke API keys without touching the database directly.

## Outcome
- Added `mint_api_key` and `revoke_api_key` helpers in `backend/app/services/auth.py` to issue random secrets, persist hashed tokens with stable prefixes, and emit audit events on creation and revocation.
- Introduced admin-only `/auth/api-keys` endpoints plus Pydantic schemas that list existing keys, mint new ones while returning the secret once, and mark keys as revoked without deleting rows.
- Expanded `backend/tests/test_auth.py` with end-to-end coverage for the provisioning flow, confirming that audit events are recorded and revoked keys can no longer authenticate requests.
