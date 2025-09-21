# 🔄 Next Task — Harden SSO State Token Verification

## Context
While aligning the auth routes with the shared dependency we observed the SSO callback tests occasionally fail with
`Invalid state token signature`. The `_verify_state_token` helper currently splits the base64 payload with
`decoded.rsplit(b".", 1)`, which breaks whenever the HMAC signature itself contains a dot byte. That makes the SSO login
round-trip flaky and can reject legitimate callbacks.

## Goals
1. Update the state token packing and `_verify_state_token` parsing so arbitrary HMAC bytes are handled without relying on
   delimiter characters that may appear in the signature.
2. Add a regression test that exercises a signature containing dot bytes to prove the fix and keep the behaviour stable.
3. Keep the state token format backwards compatible for tokens minted before the change, or provide a short compatibility
   shim so active login attempts are still honoured.
4. Ensure the existing negative-path tests (unexpected nonce, expired state, etc.) still pass without code duplication.

## Implementation notes
- Consider encoding the signature separately (e.g. base64) or prefixing lengths to avoid delimiter collisions.
- Focus on clear, linear control flow—no new abstractions or generic helpers beyond what is needed for correctness.
- Update or extend only the SSO-specific tests that cover this bug; avoid touching unrelated authentication flows.

## Definition of done
- SSO callbacks consistently succeed for valid states; the regression suite no longer flakes on `Invalid state token signature`.
- New tests cover the previously failing scenario.
- No new dependencies introduced.
