# Auth Route Truth Snapshot

Date: 2026-02-08  
Baseline commit: `7bbc4e0c` (`origin/development`)

## Purpose

Freeze the auth API surface used for go-live hardening so backend, frontend, docs, and tests all validate against one source of truth.

## Canonical Endpoints

These endpoints are in scope and frozen for this hardening pass.

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/password/forgot`
- `POST /api/v1/auth/password/reset`
- `POST /api/v1/auth/mfa/challenge/verify`
- `GET /api/v1/admin/sso/settings`
- `PUT /api/v1/admin/sso/settings`

## Prohibited Endpoints

These endpoints must not exist or be used.

- `/api/v1/auth/jwt/*`
- `/api/v1/auth/cookie/*`

OpenAPI verification at this baseline:

- `/api/v1/auth/jwt/login`: absent
- `/api/v1/auth/jwt/logout`: absent
- `/api/v1/auth/cookie/login`: absent
- `/api/v1/auth/cookie/logout`: absent

## Security Scheme Truth

The OpenAPI security schemes for auth are:

- `SessionCookie`
- `APIKeyHeader` with header name `X-API-Key`

No bearer JWT scheme is present in the active OpenAPI schema.

## Evidence Collection Commands

```bash
cd backend && uv run python -m ade_api.scripts.api_routes --prefix /api/v1/auth --format csv
cd backend && uv run python -m ade_api.scripts.api_routes --prefix /api/v1/admin/sso --format csv
cd backend && uv run python -m ade_api.scripts.generate_openapi
```
