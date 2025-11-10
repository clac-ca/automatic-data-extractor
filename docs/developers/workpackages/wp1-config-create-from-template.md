# WP1 — Config Metadata & Create-from-Template / Clone

## Goal
Persist configuration metadata per workspace and allow the API to create new **draft** configs by copying either a bundled template or another config folder.

## Scope
* Introduce a `configurations` table keyed by `(workspace_id, config_id)` with lifecycle metadata.
* Implement `POST /api/v1/workspaces/{workspace_id}/configurations` with a discriminated `source` object.
* Wire up filesystem copy → validate → promote (atomic rename) → insert DB row.

## Database
Create table `configurations` with:
* `workspace_id TEXT`, `config_id TEXT` (composite primary key)
* `display_name TEXT`
* `status TEXT CHECK IN ('draft','active','inactive') DEFAULT 'draft'`
* `config_version INTEGER NOT NULL DEFAULT 0`
* `content_digest TEXT NULL`
* `created_at TEXT`, `updated_at TEXT`, `activated_at TEXT NULL`
* `last_editor TEXT NULL`
* Index on `(workspace_id, status)` for quick filters
* Defer the “one active per workspace” unique index to WP3

## API
```
POST /api/v1/workspaces/{workspace}/configurations
Body {
  "config_id": "membership-v2",
  "display_name": "Membership v2",
  "source": {
    "type": "template" | "existing",
    "template_id"?: "default",
    "config_id"?: "membership"
  }
}
```

Responses:
* `201 Created` → row metadata with `status="draft"` and `config_version=0`
* `409 Conflict` → `(workspace_id, config_id)` already exists
* `404`/`422` → bad source references

## Key Behaviors
* **Templates** come from `apps/api/app/templates/config_packages/{template_id}/`.
* **Existing** clones source the workspace config folder at `${ADE_CONFIGS_DIR}/{workspace}/config_packages/{config_id}/`.
* Copy filters: skip `.git/`, `__pycache__/`, `*.pyc`, `.DS_Store`, `.venv/`, `node_modules/`, IDE/build artifacts; reject symlinks.
* Validation requires `src/ade_config/` plus a parseable `manifest.json`; warn (not fail) if `pyproject.toml` is missing.
* Copy into `…/.creating-<ulid>` then atomically rename to the final path after validation succeeds.

## Acceptance
* Drafts can be created from both templates and existing configs.
* Duplicate IDs yield `409`.
* Validation failures never leave partial folders at the final path.
* Final tree contains a ready-to-edit config with readable manifest + package layout.
