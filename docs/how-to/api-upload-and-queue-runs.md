# Upload a Document and Queue Runs

## Goal

Upload a document with API key auth and queue a run with sheet-selection options.

## Before You Start

You need:

- ADE already running
- a valid API key for a user with workspace document upload permissions
- target workspace ID
- input file path

Set required variables:

```bash
export BASE_URL="http://localhost:8001"
export API_KEY="<your-api-key>"
export WORKSPACE_ID="<workspace-uuid>"
export INPUT_FILE="/absolute/path/to/input.xlsx"
```

```python
import os

BASE_URL = os.environ["BASE_URL"]
API_KEY = os.environ["API_KEY"]
WORKSPACE_ID = os.environ["WORKSPACE_ID"]
INPUT_FILE = os.environ["INPUT_FILE"]
```

```powershell
$env:BASE_URL = "http://localhost:8001"
$env:API_KEY = "<your-api-key>"
$env:WORKSPACE_ID = "<workspace-uuid>"
$env:INPUT_FILE = "C:\path\to\input.xlsx"
```

Run queueing preconditions:

- the workspace has an active configuration
- workspace processing is not paused

## Steps

### 1. Auth (API key)

Send a quick request with `X-API-Key`:

```bash
curl -sS \
  -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/me"
```

```python
import requests

response = requests.get(
    f"{BASE_URL}/api/v1/me",
    headers={"X-API-Key": API_KEY},
    timeout=30,
)
response.raise_for_status()
print(response.json()["email"])
```

```powershell
$headers = @{ "X-API-Key" = $env:API_KEY }
$me = Invoke-RestMethod `
  -Method Get `
  -Uri "$($env:BASE_URL)/api/v1/me" `
  -Headers $headers
$me.email
```

### 2. Upload and queue a run

`POST /api/v1/workspaces/{workspaceId}/documents` accepts multipart form fields:

- `file` (required)
- `metadata` (optional JSON string)
- `run_options` (optional JSON string)
- `conflictMode` (optional: `reject`, `upload_new_version`, `keep_both`)

`run_options` keys should use API-style names:

- `activeSheetOnly`
- `inputSheetNames`

Do not send both in the same request.

#### Example A: default upload behavior

```bash
curl -sS -X POST \
  -H "X-API-Key: $API_KEY" \
  -F "file=@$INPUT_FILE" \
  -F 'metadata={"source":"api-guide","mode":"default"}' \
  -F "conflictMode=keep_both" \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/documents"
```

```python
import json
from pathlib import Path

import requests

with Path(INPUT_FILE).open("rb") as file_handle:
    response = requests.post(
        f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/documents",
        headers={"X-API-Key": API_KEY},
        files={"file": (Path(INPUT_FILE).name, file_handle)},
        data={
            "metadata": json.dumps({"source": "api-guide", "mode": "default"}),
            "conflictMode": "keep_both",
        },
        timeout=120,
    )
response.raise_for_status()
print(response.json()["id"])
```

```powershell
$headers = @{ "X-API-Key" = $env:API_KEY }
$upload = Invoke-RestMethod `
  -Method Post `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/documents" `
  -Headers $headers `
  -Form @{
    file = Get-Item $env:INPUT_FILE
    metadata = '{"source":"api-guide","mode":"default"}'
    conflictMode = "keep_both"
  }
$upload.id
```

#### Example B: queue run with active sheet only

Use this for XLSX uploads when the run should process only the workbook's active sheet.

```bash
curl -sS -X POST \
  -H "X-API-Key: $API_KEY" \
  -F "file=@$INPUT_FILE" \
  -F 'metadata={"source":"api-guide","mode":"active-sheet-only"}' \
  -F 'run_options={"activeSheetOnly":true}' \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/documents"
```

```python
import json
from pathlib import Path

import requests

with Path(INPUT_FILE).open("rb") as file_handle:
    response = requests.post(
        f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/documents",
        headers={"X-API-Key": API_KEY},
        files={"file": (Path(INPUT_FILE).name, file_handle)},
        data={
            "metadata": json.dumps({"source": "api-guide", "mode": "active-sheet-only"}),
            "run_options": json.dumps({"activeSheetOnly": True}),
        },
        timeout=120,
    )
response.raise_for_status()
print(response.json()["id"])
```

```powershell
$headers = @{ "X-API-Key" = $env:API_KEY }
$upload = Invoke-RestMethod `
  -Method Post `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/documents" `
  -Headers $headers `
  -Form @{
    file = Get-Item $env:INPUT_FILE
    metadata = '{"source":"api-guide","mode":"active-sheet-only"}'
    run_options = '{"activeSheetOnly":true}'
  }
$upload.id
```

#### Example C: queue run with specific sheets

Use this for XLSX uploads when the run should process only named sheets.

```bash
curl -sS -X POST \
  -H "X-API-Key: $API_KEY" \
  -F "file=@$INPUT_FILE" \
  -F 'metadata={"source":"api-guide","mode":"selected-sheets"}' \
  -F 'run_options={"inputSheetNames":["Sheet1","Sheet2"]}' \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/documents"
```

```python
import json
from pathlib import Path

import requests

with Path(INPUT_FILE).open("rb") as file_handle:
    response = requests.post(
        f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/documents",
        headers={"X-API-Key": API_KEY},
        files={"file": (Path(INPUT_FILE).name, file_handle)},
        data={
            "metadata": json.dumps({"source": "api-guide", "mode": "selected-sheets"}),
            "run_options": json.dumps({"inputSheetNames": ["Sheet1", "Sheet2"]}),
        },
        timeout=120,
    )
response.raise_for_status()
print(response.json()["id"])
```

```powershell
$headers = @{ "X-API-Key" = $env:API_KEY }
$upload = Invoke-RestMethod `
  -Method Post `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/documents" `
  -Headers $headers `
  -Form @{
    file = Get-Item $env:INPUT_FILE
    metadata = '{"source":"api-guide","mode":"selected-sheets"}'
    run_options = '{"inputSheetNames":["Sheet1","Sheet2"]}'
  }
$upload.id
```

## Verify the Run Was Queued

List documents and inspect `lastRun` for the uploaded document:

```bash
curl -sS \
  -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/documents?limit=20"
```

```python
import requests

response = requests.get(
    f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/documents",
    headers={"X-API-Key": API_KEY},
    params={"limit": 20},
    timeout=30,
)
response.raise_for_status()

for document in response.json().get("items", []):
    last_run = document.get("lastRun")
    if last_run:
        print(document["name"], last_run["id"], last_run["status"])
```

```powershell
$headers = @{ "X-API-Key" = $env:API_KEY }
$docs = Invoke-RestMethod `
  -Method Get `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/documents?limit=20" `
  -Headers $headers

foreach ($doc in $docs.items) {
  if ($null -ne $doc.lastRun) {
    "$($doc.name) $($doc.lastRun.id) $($doc.lastRun.status)"
  }
}
```

Upload can succeed while no run is queued. Common reasons:

- no active configuration in the workspace
- workspace processing is paused

## If Something Fails

- `401 Unauthorized`: API key missing, revoked, or invalid.
- `403 Forbidden`: key does not have workspace upload permissions.
- `400 Bad Request`: malformed `run_options` JSON or invalid sheet option combination.
- `413 Content Too Large`: file exceeds upload size limit.
- `429 Too Many Requests`: upload concurrency limit reached.
- `409 Conflict`: duplicate document name when `conflictMode=reject`.

## Notes

- API key transport is `X-API-Key`.
- `Authorization: Bearer <api-key>` is not a supported API-key transport.
- PowerShell examples assume PowerShell 7+ (`Invoke-RestMethod -Form`).
