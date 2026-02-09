# Manage Configurations via API

## Goal

Create, inspect, and archive workspace configurations through the ADE API.

## Before You Start

You need:

- `BASE_URL`
- `API_KEY`
- `WORKSPACE_ID`

Set variables:

```bash
export BASE_URL="http://localhost:8001"
export API_KEY="<your-api-key>"
export WORKSPACE_ID="<workspace-uuid>"
```

```python
import os

BASE_URL = os.environ["BASE_URL"]
API_KEY = os.environ["API_KEY"]
WORKSPACE_ID = os.environ["WORKSPACE_ID"]
```

```powershell
$env:BASE_URL = "http://localhost:8001"
$env:API_KEY = "<your-api-key>"
$env:WORKSPACE_ID = "<workspace-uuid>"
```

## Steps

### 1. List configurations

Pass an explicit status filter so clients never rely on implicit defaults.

```bash
STATUS_FILTER='[{"id":"status","operator":"in","value":["draft","active"]}]'
curl -sS \
  -H "X-API-Key: $API_KEY" \
  --get \
  --data-urlencode "limit=20" \
  --data-urlencode "filters=$STATUS_FILTER" \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/configurations"
```

```python
import requests
import json

headers = {"X-API-Key": API_KEY}
filters = [{"id": "status", "operator": "in", "value": ["draft", "active"]}]
response = requests.get(
    f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/configurations",
    headers=headers,
    params={"limit": 20, "filters": json.dumps(filters)},
    timeout=30,
)
response.raise_for_status()
print(response.json())
```

```powershell
$headers = @{ "X-API-Key" = $env:API_KEY }
$filters = '[{"id":"status","operator":"in","value":["draft","active"]}]'
$configs = Invoke-RestMethod `
  -Method Get `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/configurations?limit=20&filters=$([uri]::EscapeDataString($filters))" `
  -Headers $headers
$configs
```

### 2. Create a draft from template

```bash
curl -sS -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"displayName":"API Draft Config","source":{"type":"template"},"notes":"created from API"}' \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/configurations"
```

```python
payload = {
    "displayName": "API Draft Config",
    "source": {"type": "template"},
    "notes": "created from API",
}
response = requests.post(
    f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/configurations",
    headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    json=payload,
    timeout=30,
)
response.raise_for_status()
configuration = response.json()
print(configuration["id"])
```

```powershell
$payload = @{
  displayName = "API Draft Config"
  source = @{ type = "template" }
  notes = "created from API"
} | ConvertTo-Json -Depth 5
$jsonHeaders = @{ "X-API-Key" = $env:API_KEY; "Content-Type" = "application/json" }

$config = Invoke-RestMethod `
  -Method Post `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/configurations" `
  -Headers $jsonHeaders `
  -Body $payload
$config.id
```

### 3. Archive a configuration

Set `CONFIGURATION_ID` to a draft or active configuration you want to archive.

```bash
export CONFIGURATION_ID="<configuration-uuid>"
curl -sS -X POST \
  -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/workspaces/$WORKSPACE_ID/configurations/$CONFIGURATION_ID/archive"
```

```python
CONFIGURATION_ID = "<configuration-uuid>"
response = requests.post(
    f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/configurations/{CONFIGURATION_ID}/archive",
    headers={"X-API-Key": API_KEY},
    timeout=30,
)
response.raise_for_status()
print(response.json()["status"])
```

```powershell
$env:CONFIGURATION_ID = "<configuration-uuid>"
$archived = Invoke-RestMethod `
  -Method Post `
  -Uri "$($env:BASE_URL)/api/v1/workspaces/$($env:WORKSPACE_ID)/configurations/$($env:CONFIGURATION_ID)/archive" `
  -Headers $headers
$archived.status
```

## Verify

- List endpoint shows the new or archived configuration status.
- Archived records should report `status` as archived in the response payload.

## If Something Fails

- `401 Unauthorized`: missing/invalid API key.
- `403 Forbidden`: key lacks workspace configuration permissions.
- `404 Not Found`: workspace/configuration ID not found.
- `409 Conflict`: attempted mutation is invalid for current configuration state.
- `422 Unprocessable Content`: payload shape or source configuration data is invalid.
