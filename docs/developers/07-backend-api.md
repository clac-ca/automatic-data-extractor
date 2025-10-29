# Backend API — Configs (Jobs later)

**Audience:** Backend and client developers integrating with the config service  
**Goal:** Know the RESTful routes for configs (v0.5) and how to call them

> **At a glance**
>
> - Base: `/api/v1/workspaces/{workspace_id}/configs`
> - Only `inactive` configs are editable; exactly one `active` per workspace
> - Supports create/clone/import/export, manifest/files, validate, activate, secrets

## Conventions
Keep routes RESTful and predictable. Use nouns in paths, verbs in HTTP. Responses are JSON. Only `inactive` configs are editable.

## Base prefix

`/api/v1/workspaces/{workspace_id}/configs`

## Workspace‑scoped

- `GET    /` — list configs (`?status=active|inactive|archived|all`)
- `POST   /` — create inactive config `{title?, note?, from_config_id?}` → `{id}`
- `GET    /active` — current active config (404 if none)
- `POST   /import` — upload zip → new inactive config `{id}`

## Config‑scoped

- `GET    /{config_id}` — metadata
- `PATCH  /{config_id}` — update `{title|note|version}`; set `status` to `archived|inactive`
- `DELETE /{config_id}` — delete if not active
- `POST   /{config_id}/activate` — atomically switch active

### Manifest
- `GET /{config_id}/manifest`
- `PUT /{config_id}/manifest` — validate on write; reject plaintext secrets

### Files
- `GET    /{config_id}/files`
- `GET    /{config_id}/files/{path:path}`
- `PUT    /{config_id}/files/{path:path}` — atomic text write
- `DELETE /{config_id}/files/{path:path}`
- `POST   /{config_id}/rename` — atomic column key/file rename

### Import / export / validate / clone
- `GET  /{config_id}/export` — stream zip
- `POST /{config_id}/validate` — run structure + dry‑run checks
- `POST /{config_id}/clone` — deep copy folder → new inactive config

### Secrets (plaintext never returned)
- `GET    /{config_id}/secrets` — list `{name, key_id, created_at}[]`
- `POST   /{config_id}/secrets` — `{name, value}`; server encrypts into manifest
- `DELETE /{config_id}/secrets/{name}`

## Minimal examples

```bash
# Create an inactive config
curl -sS -X POST \
  -H 'Content-Type: application/json' \
  -d '{"title":"Starter","note":"Baseline config"}' \
  /api/v1/workspaces/ws_001/configs

# => { "id": "cfg_A" }
```

```bash
# Activate a config
curl -sS -X POST /api/v1/workspaces/ws_001/configs/cfg_A/activate
# => { "id": "cfg_A", "status": "active" }
```

```bash
# Update manifest (v0.5) — reject plaintext secrets
curl -sS -X PUT \
  -H 'Content-Type: application/json' \
  -d @manifest.json \
  /api/v1/workspaces/ws_001/configs/cfg_A/manifest
```

```bash
# Validate a config (structure + quick dry‑run)
curl -sS -X POST /api/v1/workspaces/ws_001/configs/cfg_A/validate
# => { "ok": true, "diagnostics": [] }
```

> Inventory live routes with `npm run routes:backend`.

## Jobs
Jobs endpoints will be added in a later iteration.

---

Previous: [06-runtime-model.md](./06-runtime-model.md)  
Next: [08-validation-and-diagnostics.md](./08-validation-and-diagnostics.md)
