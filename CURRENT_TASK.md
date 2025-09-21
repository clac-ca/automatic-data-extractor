# ✅ Follow-up Task — Harden Authentication Coverage & Edge Cases

## Context
The simplified authentication stack is now in place. Sessions, API keys, and SSO all share the same dependency, and routes expose
clear OpenAPI metadata. Before we move on, we need stronger regression coverage that exercises the new control flow and makes sure
we do not regress on critical edge cases (API-key clients, SSO-only tenants, and environments with auth disabled).

## Goals
1. Cover the most important success paths with end-to-end tests so we can refactor safely.
2. Lock down failure cases (bad credentials, revoked keys, expired SSO tokens) so we surface the intended HTTP statuses.
3. Verify helper utilities (`api_keys.touch_api_key_usage`, `sessions.touch_session`) behave correctly when invoked through
   real requests instead of direct unit calls.

## Implementation guidelines
- **API key flows**
  - Add an integration test that hits `/auth/logout` while authenticated only via API key (should remain authorised because only
    cookies are cleared).
  - Assert that `touch_api_key_usage` updates `last_used_at` when a request is made with an API key.
  - Add a negative test for a revoked API key (mark an existing key as revoked and ensure requests return 403).
- **SSO regression checks**
  - Extend the existing SSO callback test to assert that cached discovery/JWKS responses are respected and that repeated
    callbacks reuse the cache without hitting the fake endpoints multiple times.
  - Add a test that covers an SSO login for a user that is provisioned on the fly (`sso_auto_provision=True`) and confirm
    sessions are issued correctly.
  - Include a failure test for an unexpected nonce to guarantee the dependency raises a 400 with the correct detail.
- **AUTH_DISABLED coverage**
  - Add tests verifying that `/auth/login/basic` and `/auth/logout` respond with 404/200 appropriately when `AUTH_DISABLED` is
    set, and that request-scoped auth context matches the synthetic admin user.
- Keep new tests deterministic; use fixtures to clean the `Event` and `ApiKey` tables where required.
- If any helper needs a minor tweak to surface observability (e.g. returning refreshed objects), keep the implementation simple
  and update existing call sites.

## Definition of done
- New or updated tests cover each of the scenarios above.
- `pytest` passes without race conditions or flakiness.
- No regressions to current behaviour (manual smoke test against `/auth/session` is optional but encouraged).
