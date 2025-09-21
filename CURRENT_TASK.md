# 🔄 Next Task — Add CLI commands for API key lifecycle management

## Context
Operators can now manage API keys through the REST API, but ADE's bundled CLI still lacks any workflow for bootstrapping keys in environments without HTTP access. Mirroring the API functionality at the command line keeps automation simple and ensures every credential change continues to emit audit events.

## Goals
1. Extend `backend/app/services/auth.py` CLI registration to include subcommands for listing, creating, and revoking API keys, returning the raw token to stdout only when a key is created.
2. Reuse the existing `mint_api_key` and `revoke_api_key` helpers so the CLI follows the same hashing, prefix collision handling, and event logging as the API.
3. Expand `backend/tests/test_auth.py` with coverage for the new CLI commands, including assertions that revoked keys are unusable and that events are recorded.

## Definition of done
- CLI invocations allow operators to mint, list, and revoke API keys without touching the database directly.
- CLI output includes the token value exactly once during creation while other commands surface only metadata.
- Authentication and event tests pass, demonstrating that CLI-managed keys behave identically to those provisioned via the API.
