# Config Packages — Rules Live in Files

**Audience:** Contributors creating or editing configuration packages  
**Goal:** Create, edit, and ship file‑based configs (manifest v0.5 + scripts)

> **At a glance**
>
> - A [config](./02-glossary.md) is a folder (manifest + scripts); no data inside.
> - Exactly one active config per workspace; only `draft` configs are editable.
> - Column modules expose detectors (`detect_*`) and a transformer (`transform`).

## Concept
A config is portable, reviewable code that describes how the system should interpret and clean spreadsheets. The manifest defines canonical columns and execution settings; small Python scripts implement detection, transformation, and optional validation. Because configs are just folders, you can zip, export, import, and version them easily. Secrets live encrypted in the manifest and are only decrypted inside child processes at runtime.

## Why it matters
- Keep behavior as code you can test and review.
- Share rules across environments by copying a folder.
- Make jobs deterministic: the job records exactly which config it used.

## Before you begin
- Location: configs live under `data/configs/<config_id>/`.
- Start from the folder layout below; copy it and fill in your scripts and manifest.
- Terms: review [Glossary](./02-glossary.md) for columns, mapping, and hooks.

## Lifecycle

- Status: `draft | active | archived`.
- Exactly one config is active per [workspace](./02-glossary.md); only `draft` configs are editable.
- Typical flow: create → edit/validate as a draft → activate (publish) → archive.
- The database records activation/archival events so jobs can reference immutable snapshots.

### What configs are and why they have statuses

A config is a versioned set of rules — a folder containing a manifest and scripts that define how data should be detected, transformed, and validated. Each workspace can have many configs, but only one is active at a time (jobs use the active one).

### Draft → active → archived

| Status   | Meaning                                                   | Editable? | Can transition to    |
|----------|-----------------------------------------------------------|-----------|----------------------|
| draft    | Being authored or modified; not yet active                | Yes       | `active`, `archived` |
| active   | The configuration currently in use by workspace jobs      | No        | `archived`           |
| archived | Permanent, read‑only record of an old config              | No        | (none)               |

Rules:

- Only one config can be `active` per workspace.
- Only `draft` configs are editable.
- Activating a draft makes it read‑only and archives the previously active config.
- Archived configs cannot be edited or reactivated — clone to start a new draft.

### Lifecycle in practice

```
create_config()   → status: draft
edit_config()     → status: draft
validate_config() → status: draft

activate_config() → status: active
    ↳ marks previous active (if any) as archived
    ↳ makes new config read‑only

archive_config()  → status: archived
    ↳ optional manual archive of old drafts

clone_config()    → new config with status: draft
    ↳ edit a copy of an archived or active config
```

### Example

```json
[
  { "id": "cfg_001", "status": "archived", "title": "Baseline v1" },
  { "id": "cfg_002", "status": "active",   "title": "Baseline v2" },
  { "id": "cfg_003", "status": "draft",    "title": "Next iteration" }
]
```

Summary: Drafts are editable, actives are live and immutable, archives are locked history.

---

### Roll back to a previous config

Active and archived configs are read‑only. To roll back to a previous version:

- Clone the archived config → creates a new `draft`.
- Optionally update its `title`/`version`/`note`.
- Activate the draft → it becomes `active` and the previously active config is archived.

Minimal API sketch (see Backend API for details):

```bash
# Clone archived config → returns new draft id
NEW_ID=$(curl -sS -X POST \
  /api/v1/workspaces/<WS_ID>/configs/<ARCHIVED_ID>/clone | jq -r '.id')

# Activate the cloned draft
curl -sS -X POST \
  /api/v1/workspaces/<WS_ID>/configs/$NEW_ID/activate
```

Read more in Backend API — Configs: 07-backend-api.md

---

## Folder layout (example)

```text
my-config/
├─ manifest.json
├─ columns/
│  ├─ member_id.py
│  └─ first_name.py
├─ hooks/
│  ├─ on_job_start.py
│  ├─ after_detection.py
│  ├─ after_transformation.py
│  └─ after_validation.py
└─ resources/
   └─ vendor_aliases.csv
```

---

## Manifest (schema v0.5)

The manifest is versioned JSON that describes the [config](./02-glossary.md).

- `info` — schema, title, version, description.
- `env` — environment variables available to scripts.
- `secrets` — encrypted values; decrypted only inside child processes (see [secrets](./02-glossary.md)).
- `engine.defaults` — execution limits like `timeout_ms`, `memory_mb`, `allow_net`.
- `hooks` — optional scripts that run at specific points (job start, after detection/transformation/validation, job end if defined).
- `columns.order` — canonical column order in the normalized output.
- `columns.meta[*]` — per‑column metadata. Keys must match canonical column ids in `order`. Include:
  - `label` — human‑readable name.
  - `required` — whether the column must be present and non‑blank.
  - `enabled` — toggle column on/off (kept in metadata even if disabled).
  - `script` — path to the column module implementing detectors/transform.

Manifest (excerpt):

```json
{
  "info": {
    "schema": "ade.manifest/v0.5",
    "title": "Example Membership Config",
    "version": "1.0.0",
    "description": "Detectors and transforms for member data."
  },
  "env": { "LOCALE": "en-CA" },
  "secrets": {},
  "engine": { "defaults": { "timeout_ms": 120000, "memory_mb": 256, "allow_net": false } },
  "hooks": {
    "on_job_start":       [ { "script": "on_job_start.py" } ],
    "after_detection":    [ { "script": "after_detection.py" } ],
    "after_transformation":[ { "script": "after_transformation.py" } ],
    "after_validation":   [ { "script": "after_validation.py" } ]
  },
  "columns": {
    "order": ["member_id","member_full_name"],
    "meta": {
      "member_id":        { "label": "Member ID",        "required": true,  "enabled": true, "script": "columns/member_id.py" },
      "member_full_name": { "label": "Member Full Name", "required": true,  "enabled": true, "script": "columns/member_full_name.py" }
    }
  }
}
```

---

## Script contracts

- Hooks — export `run(**kwargs)` with keyword‑only args (ids, env, paths, and a small context per hook). See `06-runtime-model.md`.
- Column modules — export one or more detectors (`detect_*`) and exactly one transformer (`transform`). Detectors run on small samples and return scores; the transformer runs over the entire assigned raw column and returns normalized values and warnings.

Detector signature (typical):

`detect_*(*, header: str, values: list, column_index: int | None = None, table: dict | None = None, env: dict | None = None, **_) -> {"scores": {"self": float, "<other_key>": float}}`

Transform signature (typical):

`transform(*, header: str | None = None, values: list, column_index: int | None = None, table: dict | None = None, env: dict | None = None, **_) -> {"values": list, "warnings": list}`

---

## Minimal example
Detector + transform + validate for a `member_id` column (≤30 lines).

```python
# columns/member_id.py
def detect_header_keywords(*, header: str, values: list, **_):
    if header and "member" in header.lower() and "id" in header.lower():
        return {"scores": {"self": 1.5}}
    return {"scores": {}}

def transform(*, values: list, **_):
    out = [(str(v).strip().upper() or None) if v is not None else None for v in values]
    return {"values": out, "warnings": []}

def validate(*, values: list, **_):
    issues = []
    for i, v in enumerate(values):
        if v is not None and len(str(v)) > 32:
            issues.append({"row": i + 1, "code": "TOO_LONG"})
    return {"issues": issues}
```

---

## Notes & pitfalls
- Keep detectors cheap; operate on samples only—never scan full sheets in detection.
- Detectors return scores; the assignment step decides raw→canonical.
- Transforms should be pure and column‑wise; avoid external I/O unless allowed.
- Do not emit plaintext secrets; keep them encrypted in the manifest.
- Keep `columns.order` and `columns.meta` keys in sync; mismatches degrade mapping UX.
- Use `engine.defaults.allow_net` sparingly; prefer offline logic in detectors/transforms.

## What’s next
- See the multi‑pass flow in [04-jobs-pipeline.md](./04-jobs-pipeline.md)
- Learn how scripts are invoked in [06-runtime-model.md](./06-runtime-model.md)
- Validate configs and read error shapes in [08-validation-and-diagnostics.md](./08-validation-and-diagnostics.md)
- Explore the starter files in `backend/app/features/configs/templates/default_config/`

---

Previous: [01-overview.md](./01-overview.md)  
Next: [04-jobs-pipeline.md](./04-jobs-pipeline.md)
