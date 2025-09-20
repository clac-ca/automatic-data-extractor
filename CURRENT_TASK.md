# 📋 AI Agent Prompt — Simplify Authentication (Native FastAPI, Best Practice)

## Context
This is a small internal app. We don’t want complicated auth chains or custom exporters.  
We want to follow **standard, best-practice patterns** using **native FastAPI security features** only.

## Requirements

### Supported authentication
- **Basic Auth** — simple username/password login for internal users.
- **OAuth2 (Bearer tokens)** — for delegated access or SSO/OIDC logins.
- **API Keys** — for programmatic clients, passed as `Authorization: Bearer <API_KEY>`.

### Goals
- **One verification path**: All requests check either a cookie session or a Bearer token.  
  - Humans: login with Basic or OAuth2 → get a server-side session cookie.  
  - Machines: use API key as a Bearer token.  
- **No multi-step fallback chains** (don’t parse Basic or OAuth headers on every request).
- **Minimal OpenAPI extension**: Let FastAPI generate docs, only add `securitySchemes` for:
  - `basicAuth` (http: basic)
  - `bearerAuth` (http: bearer for OAuth2 and API keys)
  - optionally `cookieAuth` (apiKey in: cookie, name: `ade_session`)
- **Errors**: Stick to native FastAPI (`HTTPException`, validation errors). Show examples in docs.
- **Keep it async-native**: Use `async def` for I/O and wrap blocking calls with `run_in_threadpool`.

### Implementation guidelines
1. **Login flows**:  
   - `POST /auth/login/basic` → verify Basic, create session, set cookie.  
   - `GET /auth/sso/callback` → verify OAuth2 provider, create session, set cookie.  
   - `POST /auth/logout` → clear cookie.  
   - API keys are created once and stored hashed.

2. **Per-request auth**:  
   - Dependency `get_current_user()` does exactly one thing:  
     - Extract session cookie OR Bearer token.  
     - Verify against session store or API key table.  
     - Return `UserIdentity` or raise `HTTPException`.

3. **OpenAPI**:  
   - Use `HTTPBasic`, `OAuth2PasswordBearer`, and `APIKeyHeader` directly.  
   - Expose `/openapi.json` with these schemes.  
   - Mark `/health` and `/auth/*` routes as public (`security=[]`).

4. **Docs**:  
   - Show how to login with Basic, OAuth2, and how to use API keys.  
   - Provide cURL examples for each.  

5. **Tests**:  
   - 401 when no creds.  
   - 403 when invalid API key/session.  
   - 200 with valid session or API key.  
   - `AUTH_DISABLED` bypasses auth.

## Deliverable
Refactor the codebase so ADE uses a **simple, idiomatic FastAPI auth setup**:  
- Sessions for humans.  
- API keys for machines.  
- OAuth2 only at login.  
- No per-request fallback chains.  
- Minimal, clean OpenAPI schema.  
