# API Reference

Endpoint contracts and integration workflows for ADE APIs.

Back to [Docs Home](../../README.md) and [Reference](../README.md).

## Use This Section For

- endpoint behavior and status codes
- authentication transport expectations
- task-oriented API workflows in `curl`, Python, and PowerShell

## API Endpoint References

- [Authentication](authentication.md)
- [Workspaces](workspaces.md)
- [Configurations](configurations.md)
- [Documents](documents.md)
- [Runs](runs.md)
- [Errors and Problem Details](errors-and-problem-details.md)

## Workflow Guides

- [Authenticate with API Key](../../how-to/api-authenticate-with-api-key.md)
- [Manage Configurations via API](../../how-to/api-manage-configurations.md)
- [Upload a Document and Queue Runs](../../how-to/api-upload-and-queue-runs.md)
- [Create and Monitor Runs via API](../../how-to/api-create-and-monitor-runs.md)

## Source of Truth

```bash
cd backend
uv run ade api types
```

Generated artifacts:

- `backend/src/ade_api/openapi.json`
- `frontend/src/types/generated/openapi.d.ts`
