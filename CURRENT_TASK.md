# 🔄 Next Task — Implement API key provisioning endpoints for operators

## Context
API key tokens already authenticate requests through `ApiKey` rows and `get_authenticated_identity`, yet there is no supported workflow for issuing or revoking credentials. Operators must still seed the database by hand, which bypasses event logging and makes it easy to leak raw tokens. Shipping a small admin-facing API will let us create, list, and revoke API keys deterministically while keeping token material hashed at rest.

## Goals
1. Add service helpers in `backend/app/services/auth.py` to mint and revoke API keys: generate a random token, persist the hashed form plus a stable prefix, record creation/revocation events, and update usage metadata when keys are touched.
2. Introduce Pydantic schemas and FastAPI routes (e.g. `/auth/api-keys`) that require an admin identity, return API key metadata, emit the raw token only on creation, and allow revoking keys without deleting rows.
3. Extend `backend/tests/test_auth.py` to cover create/list/revoke flows end to end, confirming that revoked keys fail authentication and that events are recorded.

## Definition of done
- Admins can manage API keys entirely via the API without manual database edits; creation responses include the token once, while only hashed values persist.
- Listing endpoints surface active and revoked keys with usage metadata, and revocation flips `revoked_at` so authentication rejects the token.
- Authentication and API key management tests pass, exercising both the new service helpers and HTTP routes.
