# Authenticate with API Key

## Goal

Verify API-key authentication against ADE and retrieve your caller profile.

## Before You Start

You need:

- ADE API base URL
- valid API key

Set variables:

```bash
export BASE_URL="http://localhost:8001"
export API_KEY="<your-api-key>"
```

```python
import os

BASE_URL = os.environ["BASE_URL"]
API_KEY = os.environ["API_KEY"]
```

```powershell
$env:BASE_URL = "http://localhost:8001"
$env:API_KEY = "<your-api-key>"
```

## Steps

### 1. Send a profile request with `X-API-Key`

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
print(response.json())
```

```powershell
$headers = @{ "X-API-Key" = $env:API_KEY }
$me = Invoke-RestMethod `
  -Method Get `
  -Uri "$($env:BASE_URL)/api/v1/me" `
  -Headers $headers
$me
```

### 2. Confirm workspace visibility (optional)

```bash
curl -sS \
  -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/workspaces?limit=5"
```

```python
response = requests.get(
    f"{BASE_URL}/api/v1/workspaces",
    headers={"X-API-Key": API_KEY},
    params={"limit": 5},
    timeout=30,
)
response.raise_for_status()
print(response.json())
```

```powershell
$workspaces = Invoke-RestMethod `
  -Method Get `
  -Uri "$($env:BASE_URL)/api/v1/workspaces?limit=5" `
  -Headers $headers
$workspaces
```

## Verify

Authentication is working when:

- `/api/v1/me` returns `200` with your user profile
- `/api/v1/workspaces` returns `200` and a workspace list (or an empty list)

## If Something Fails

- `401 Unauthorized`: missing, revoked, or invalid API key.
- `403 Forbidden`: key is valid but lacks the required permission/scope.
- `404 Not Found`: incorrect base URL or API prefix.

Notes:

- API-key transport is `X-API-Key`.
- `Authorization: Bearer <api-key>` is not the supported API-key transport.
