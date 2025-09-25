# User Guide

This guide explains how operators interact with the Automatic Data Extractor API. The workflows map directly to FastAPI routers in `backend/api/modules/` so you can cross-reference the code when exploring behaviours.

## Before you start
- Obtain an access token or API key from an administrator. Authentication flows live in [`backend/api/modules/auth/router.py`](../../backend/api/modules/auth/router.py).
- Identify the workspace you belong to and note its identifier. Workspace context binding happens in [`backend/api/modules/workspaces/dependencies.py`](../../backend/api/modules/workspaces/dependencies.py).
- Export the following environment variables for reuse in examples:
  ```bash
  export ADE_API_URL="http://localhost:8000"
  export ADE_TOKEN="<paste-your-bearer-token>"
  export ADE_WORKSPACE_ID="<workspace-ulid>"
  ```

## Core workflows

The API is structured around a few stable resources:

1. **Documents** – upload source files, list metadata, download stored bytes, and request removal. Implemented in [`documents/router.py`](../../backend/api/modules/documents/router.py).
2. **Jobs** – submit an extraction request and monitor progress. Routes live in [`jobs/router.py`](../../backend/api/modules/jobs/router.py) and rely on the background task queue wired in [`backend/api/core/task_queue.py`](../../backend/api/core/task_queue.py).
3. **Results** – fetch extracted tables linked to documents or jobs. Served from [`results/router.py`](../../backend/api/modules/results/router.py).
4. **Events** – inspect the immutable audit trail exposed by [`events/router.py`](../../backend/api/modules/events/router.py).

Upcoming sections will expand each workflow with concrete request/response examples and recommended error handling patterns. The surface above is stable and matches the production API today, so you can already build tooling around these routes.
