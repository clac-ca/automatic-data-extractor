# Create and Monitor Runs via API

## Goal

Create a run for an uploaded document, monitor progress, and retrieve run output metadata.

## Before You Start

You need:

- `BASE_URL`
- `API_KEY`
- `WORKSPACE_ID`
- `DOCUMENT_ID` for an existing uploaded document

Set variables:

```bash
export BASE_URL="http://localhost:8001"
export API_KEY="<your-api-key>"
export WORKSPACE_ID="<workspace-uuid>"
export DOCUMENT_ID="<document-uuid>"
```

```python
import os

BASE_URL = os.environ["BASE_URL"]
API_KEY = os.environ["API_KEY"]
WORKSPACE_ID = os.environ["WORKSPACE_ID"]
DOCUMENT_ID = os.environ["DOCUMENT_ID"]
```

```powershell
$env:BASE_URL = "http://localhost:8001"
$env:API_KEY = "<your-api-key>"
$env:WORKSPACE_ID = "<workspace-uuid>"
$env:DOCUMENT_ID = "<document-uuid>"
```

## Steps

### 1. Create a run

```bash
curl -sS -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"inputDocumentId\":\"$DOCUMENT_ID\",\"options\":{\"operation\":\"process\"}}" \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/runs"
```

```python
import requests

headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
payload = {
    "inputDocumentId": DOCUMENT_ID,
    "options": {"operation": "process"},
}
response = requests.post(
    f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/runs",
    headers=headers,
    json=payload,
    timeout=30,
)
response.raise_for_status()
run = response.json()
print(run["id"])
```

```powershell
$headers = @{ "X-API-Key" = $env:API_KEY; "Content-Type" = "application/json" }
$payload = @{
  inputDocumentId = $env:DOCUMENT_ID
  options = @{ operation = "process" }
} | ConvertTo-Json -Depth 5

$run = Invoke-RestMethod `
  -Method Post `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/runs" `
  -Headers $headers `
  -Body $payload
$run.id
```

### 2. Poll run status

Set `RUN_ID` from step 1.

```bash
export RUN_ID="<run-uuid>"
curl -sS \
  -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/runs/$RUN_ID"
```

```python
RUN_ID = "<run-uuid>"
response = requests.get(
    f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/runs/{RUN_ID}",
    headers={"X-API-Key": API_KEY},
    timeout=30,
)
response.raise_for_status()
print(response.json()["status"])
```

```powershell
$env:RUN_ID = "<run-uuid>"
$status = Invoke-RestMethod `
  -Method Get `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/runs/$($env:RUN_ID)" `
  -Headers @{ "X-API-Key" = $env:API_KEY }
$status.status
```

### 3. Read output metadata

```bash
curl -sS \
  -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/runs/$RUN_ID/output"
```

```python
response = requests.get(
    f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/runs/{RUN_ID}/output",
    headers={"X-API-Key": API_KEY},
    timeout=30,
)
response.raise_for_status()
print(response.json())
```

```powershell
$output = Invoke-RestMethod `
  -Method Get `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/runs/$($env:RUN_ID)/output" `
  -Headers @{ "X-API-Key" = $env:API_KEY }
$output
```

## Verify

- Run creation returns `201` and a new run `id`.
- Polling endpoint returns run lifecycle status (`queued`, `running`, `succeeded`, `failed`, or `cancelled`).
- Output metadata endpoint reports readiness (`ready=true`) when output is available.

## If Something Fails

- `401 Unauthorized`: missing/invalid API key.
- `403 Forbidden`: key lacks run permissions in workspace.
- `404 Not Found`: workspace, document, or run ID is invalid.
- `409 Conflict`: run cannot transition (for example cancel or output not ready).
- `422 Unprocessable Content`: invalid run options or conflicting option values.
