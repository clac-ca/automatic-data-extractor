# Auth Go-Live Security Verification Log

Date: 2026-02-08

## Baseline

- Branch: `codex/auth-go-live-hardening`
- Base: `origin/development` at `7bbc4e0c`

## Commands Run

```bash
cd backend && uv run ade db reset --yes
cd backend && uv run ade db migrate
cd backend && uv run ade api test
cd backend && uv run ade test
cd backend && uv run python -m ade_api.scripts.generate_openapi
cd backend && uv run ade api types
git diff -- backend/src/ade_api/openapi.json frontend/src/types/generated/openapi.d.ts
```

## Results

- `ade db reset --yes`: passed
- `ade db migrate`: passed
- `ade api test`: passed (`125` API unit tests)
- `ade test`: passed (`125` API unit, `16` worker unit, `191` frontend tests)
- OpenAPI and generated TS types regeneration: passed
- Generated artifact diff: clean (no drift)

## Additional Auth-Focused Validation

```bash
cd backend && uv run pytest tests/api/integration/auth/test_auth_sessions.py -q
```

- Result: passed (`7` tests)
- Coverage includes:
- HTTPS-equivalent secure cookie behavior (`Secure` flag when public URL is HTTPS)
- logout CSRF requirement
- MFA recovery replay behavior
- local-login lockout enforcement
- SSO enforcement for non-admin local login
- global-admin local-login path under SSO enforcement

## Issues Found During Verification (Resolved)

1. Failed-login counter persistence could be rolled back on 401 login responses.
- Fix: commit failed-login state before returning 401 in `backend/src/ade_api/features/auth/router.py`.

2. SSO provider admin route could raise `AttributeError` when logging status.
- Fix: normalize enum/string status logging in `backend/src/ade_api/features/sso/service.py`.

## Open Findings After This Pass

- No open P0/P1 findings identified in this verification run.
- No unresolved OpenAPI/type drift after regeneration.
