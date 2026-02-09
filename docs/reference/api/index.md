# API Reference Hub

## Purpose

Use this section to navigate ADE API reference and task-focused API guides.

- Reference pages describe endpoint contracts and behavior.
- How-to pages show copy/paste workflows in `curl`, Python, and PowerShell.

## Audience

This section is for integrators and operators who call ADE APIs directly.

## Reference Pages

- [Authentication](authentication.md)
- [Errors and Problem Details](errors-and-problem-details.md)
- [Workspaces](workspaces.md)
- [Configurations](configurations.md)
- [Documents](documents.md)
- [Runs](runs.md)

## How-To Guides

- [Authenticate with API Key](../../how-to/api-authenticate-with-api-key.md)
- [Manage Configurations](../../how-to/api-manage-configurations.md)
- [Upload a Document and Queue Runs](../../how-to/api-upload-and-queue-runs.md)
- [Create and Monitor Runs](../../how-to/api-create-and-monitor-runs.md)

## Source of Truth

Use generated OpenAPI for exact schema shape:

```bash
cd backend
uv run ade api types
```

Then inspect:

- `backend/src/ade_api/openapi.json`
- `frontend/src/types/generated/openapi.d.ts`
