# WP‑1 — Create Config (copy → draft) + Validate (digest + checks)

> Status note: templates now come from the ade-engine CLI (`ade-engine config init`); the API no longer ships embedded template folders. This document describes the older flow where templates lived under `apps/ade-api/src/ade_api/templates/config_packages/`.

## What we’re doing (in one paragraph)

A config package is a folder the engine imports (`ade_config`). To create one, we **copy** an existing folder—either a backend‑embedded **template** or a **clone** of another config by its **ULID**—into the workspace, validate its minimal shape, and publish it as a **draft** by an **atomic rename**. Drafts are editable via file endpoints (later work). **Validate** recomputes a deterministic **content digest** and returns issues; for WP‑1 every **build** simply re-runs validate first instead of relying on stored metadata. **Activate** locks the config and enforces “one active per workspace” (later WP).

---

## Identities & locations

* **ID**: `config_id` is a **ULID** assigned by the server at creation.
* **Templates (read‑only)**: `apps/ade-api/src/ade_api/templates/config_packages/<template_id>/`
* **Destination**: `${ADE_CONFIGS_DIR}/{workspace_id}/config_packages/{config_id}/`

---

## States

* **draft** — editable; can **validate** and later **build**; file changes happen via file APIs (WP‑2).
* **active** — selected for the workspace; read‑only.
* **inactive** — not selected; read‑only.
  (Activate/inactivate come later.)

---

## Data model (enough for create + validate, future-proof for later)

```sql
TABLE configurations (
  workspace_id    TEXT NOT NULL,
  config_id       TEXT NOT NULL,              -- ULID (server-assigned)
  display_name    TEXT NOT NULL,

  status          TEXT NOT NULL DEFAULT 'draft',  -- draft | active | inactive
  config_version  INTEGER NOT NULL DEFAULT 0,     -- bumps on activate (later)

  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  activated_at    TEXT NULL,                      -- set on activate (later)

  PRIMARY KEY (workspace_id, config_id)
);
CREATE INDEX IF NOT EXISTS idx_cfg_ws_status ON configurations(workspace_id, status);
```

> Activation will later add `CREATE UNIQUE INDEX idx_cfg_ws_active ON configurations(workspace_id) WHERE status = 'active'` to enforce “one active per workspace” without revisiting the schema added here. We deliberately keep the table minimal for WP‑1 because validation does not persist digests or timestamps yet; later work can introduce those columns when the flow needs them.

**Digest rule (used by validate and later by build checks):**

* Walk the **logical code set** (include/exclude rules below) in **sorted relative-path order**.
* Hash `relative_path + 0x00 + file_bytes` for each file, then SHA-256 of the concatenation → `content_digest`.

---

## Minimal shape of a valid config folder

* **Required files**: `manifest.toml`, `pyproject.toml`.  We will enforce richer structure in later work packages.
* **Digest include set**: during validate we only hash files under the config folder whose extension is `.py`, `.toml`, or `.json`. Everything else is ignored for WP‑1 to keep hashing fast and deterministic.

---

## API

### Create (copy → draft)

The server **generates** the ULID `config_id` and returns it. Creation is a **copy**: resolve source → copy to staging with filters → validate minimal shape → atomic rename → insert draft row. There is no background validation; clients run `validate` whenever they want the latest feedback.

```http
POST /api/v1/workspaces/{workspace_id}/configurations
Content-Type: application/json
```

**From template**

```json
{
  "display_name": "Membership v2",
  "source": { "type": "template", "template_id": "default" }
}
```

**Clone (by ULID within same workspace)**

```json
{
  "display_name": "Membership (Copy)",
  "source": { "type": "clone", "config_id": "01JC0M4G4K5W7QK1YW7W2W1Q7C" }
}
```

Cloning is scoped to the same workspace: the API resolves `{workspace_id, config_id}` and copies from that path.

**201 Created**

```json
{
  "workspace_id": "ws_123",
  "config_id": "01JC0M8YH1Y7A6RNK3Q3JK22QX",
  "display_name": "Membership v2",
  "status": "draft",
  "config_version": 0,
  "created_at": "2025-11-10T14:20:31Z",
  "updated_at": "2025-11-10T14:20:31Z"
}
```

Errors: `404 source_not_found`, `422 invalid_source_shape`, `409 publish_conflict` (rare race on rename).

---

### Validate (compute digest + fast checks)

Validate is allowed **only for drafts**. It walks the canonical include set, recomputes the digest, performs shape checks, and returns the issues. WP‑1 purposely keeps this stateless: the API does not persist the digest or timestamps. Any workflow that needs a clean tree (e.g., `build`) simply calls `validate` immediately beforehand and fails fast if issues exist.

```http
POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/validate
```

**200 OK**

```json
{
  "workspace_id": "ws_123",
  "config_id": "01JC0M8YH1Y7A6RNK3Q3JK22QX",
  "status": "draft",
  "content_digest": "sha256:ab12cd34…",
  "issues": []
}
```

If issues are found (e.g., malformed `manifest.toml`), return them in `issues` and omit `content_digest` from the payload. Build callers are expected to stop when issues are present and try again after fixes. A future WP can persist results or add status fields when the workflow needs historical data.

Error: `409 configuration_not_editable` if state ≠ `draft`.

---

## Acceptance

* Create from **template** or **clone** produces a draft folder and row.
* Validate recomputes the digest (limited to `.py/.toml/.json` files), reports issues, and does not persist anything; any caller that needs guarantees re-runs it ad hoc.
* Drafts remain editable; whenever files change, rerun validate to confirm a clean state.
* Activation and build are separate steps; each begins by invoking validate and only proceeds when the response contains `issues: []`.

This keeps the flow intuitive: **copy → draft**, edit files freely, **validate** until clean, **build** as needed, then **activate** when ready.
