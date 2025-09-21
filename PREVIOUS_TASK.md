# ✅ Completed Task — Add CLI commands for API key lifecycle management

## Context
Operators can now mint and revoke API keys over HTTP, but the bundled CLI lacked equivalent workflows. Providing lifecycle commands keeps air-gapped environments manageable and ensures CLI actions emit the same audit trail as API-driven changes.

## Outcome
- Extended `mint_api_key` and `revoke_api_key` to accept a `source` label so non-HTTP actors can reuse the helpers while emitting accurate audit metadata.
- Added `list-api-keys`, `create-api-key`, and `revoke-api-key` CLI subcommands that reuse the existing helpers, require an administrator operator for write operations, and print the raw token exactly once during creation.
- Expanded `backend/tests/test_auth.py` with coverage for the new commands, asserting that events are recorded with the `cli` source and that revoked keys immediately lose access.
