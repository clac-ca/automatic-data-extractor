# API Capability Map

## Purpose

This page gives a plain-language map of what the API can do.

Use OpenAPI output for exact request/response schemas.

## How to Discover Current Routes

```bash
cd backend
uv run ade-api routes
uv run ade-api types
```

## Capability Areas

| Area | Typical URL prefixes | Main use |
| --- | --- | --- |
| Auth | `/api/v1/auth/*`, `/api/v1/me*` | sign-in, session bootstrap, provider discovery |
| Workspaces | `/api/v1/workspaces*` | create/update workspaces, manage members |
| Configurations | `/api/v1/workspaces/{workspaceId}/configurations*` | create/validate/publish config packages |
| Documents | `/api/v1/workspaces/{workspaceId}/documents*` | upload, list, update, tag, preview documents |
| Runs | `/api/v1/runs*`, `/api/v1/workspaces/{workspaceId}/runs*` | start runs, inspect status, fetch output |
| Roles/Permissions | `/api/v1/roles*`, `/api/v1/permissions*` | access-control management |
| System | `/api/v1/system/safemode` | view/change safe mode |
| Health/Meta | `/api/v1/health`, `/api/v1/info`, `/api/v1/meta/versions` | health and version info |

## Common Flows

### First Login Setup

1. Check `/api/v1/auth/setup`.
2. Create first admin if setup is incomplete.
3. Sign in and load `/api/v1/me/bootstrap`.

### Document to Output

1. Upload a document.
2. Start a run.
3. Poll or stream run updates.
4. Download output.

### Access Administration

1. Create/update users.
2. Assign roles (global or workspace).
3. Verify effective permissions.
