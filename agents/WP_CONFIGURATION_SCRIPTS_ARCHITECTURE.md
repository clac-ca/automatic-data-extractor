We’re defining the **foundation for ADE’s configuration system** — the layer that tells the future job engine *what* to run and *how* to interpret data.

Each **Configuration** (scoped to a workspace and versioned) defines an ordered list of **Columns**, which describe the output structure (order, label, formatting, etc.).
Columns can optionally link to **Configuration Scripts** — small, versioned Python modules that contain the logic for detecting and normalizing data in those columns.

This work package delivers everything needed to **author, version, and attach scripts to columns**:

* Database schema for configurations, columns, and configuration scripts.
* APIs for editing columns and uploading/validating script versions.
* Frontend editor to manage columns and scripts.

It intentionally **stops before runtime execution** — no runner, scoring logic, or data processing yet.
The outcome is a stable configuration and authoring layer that the job engine can safely consume later.

---

## Decisions locked (v1 ABI & concepts)
* **Reproducibility**: Columns bind to **immutable configuration script versions** (not floating code).
* **Per‑configuration ownership**: Scripts are versioned **within a configuration** (no global library in v1).
* **DB**: SQLite‑first; Postgres‑ready; ULID IDs; TZ‑aware timestamps.

---

## Data model (SQLite‑first, Postgres‑ready)

**`configurations`** — versioned per workspace, one active
**`configuration_script_versions`** — per configuration & canonical key; immutable code
**`configuration_columns`** — ordered export columns + inline binding to a script version

(These are the same structures we discussed; we’re just executing schema + APIs + UI here and leaving runtime to a separate WP.)

---

# Phased delivery plan (checklists)

### Phase 1 — Schema & models (DB + ORM)

**Goal:** Add minimal tables & models to store configurations, columns, and configuration scripts (versioned).

**Checklist**

* [x] **Edit** `ade/alembic/versions/0001_initial_schema.py` to add:

  * [x] `configuration_script_versions` with:
    - `script_version_id` (ULID, PK), `configuration_id` (FK CASCADE)
    - `canonical_key` (TEXT), `version` (INT, monotonic per `{configuration_id, canonical_key}`)
    - `language` (TEXT default `'python'`), `code` (TEXT), `code_sha256` (CHAR(64))
    - `doc_name` (== `canonical_key`), `doc_description` (TEXT), `doc_declared_version` (INT)
    - `validated_at` (ts), `validation_errors` (JSON), `created_by_user_id` (FK→users)
    - timestamps; **UNIQUE(configuration_id, canonical_key, version)**; index `(configuration_id, canonical_key)`
  * [x] `configuration_columns` with:
    - PK `(configuration_id, canonical_key)`, `ordinal` (UNIQUE within configuration)
    - `display_label` (TEXT), `header_color` (TEXT, optional), `width` (INT, optional)
    - `required` (BOOL), `enabled` (BOOL)
    - `script_version_id` (FK→`configuration_script_versions.script_version_id`, RESTRICT, NULL)
    - `params` (JSON default `{}`), timestamps; index `(configuration_id, ordinal)`
  * [x] Ensure `configurations` has unique active per workspace partial index (SQLite: `sqlite_where=sa.text("is_active = 1")`)
* [x] **Recreate** local SQLite DB from this initial schema (no backfill needed).
* [x] Add **ORM models** + relationships for the two new tables.
* [x] Add **Pydantic** schemas:

  * [x] `ConfigurationOptions` (unknown_policy, output, sheet_detection, notes?)
  * [x] `ConfigurationColumnIn/Out` (incl. binding fields)
  * [x] `ConfigurationScriptVersionIn/Out` (incl. code & validation meta)
* [x] Add ULID factory util and timestamp helpers.
* [x] Smoke test migration & constraints.

**Exit criteria**

* Tables exist; constraints/indexes enforce uniqueness; models compile; DB can be recreated cleanly.

---

### Phase 2 — Backend API (FastAPI routers + validation only)

**Goal:** CRUD endpoints to manage configurations/columns; upload & validate configuration script versions; **no runner**.

**Checklist**

* [x] **Configurations**

  * [x] `POST /configurations` (create new version; may clone from active)
  * [x] `POST /configurations/{id}:activate` (enforce one active per workspace)
  * [x] `GET /configurations/{id}` (details, including options)
* [x] **Columns**

  * [x] `GET /configurations/{id}/columns` (ordered list)
  * [x] `PUT /configurations/{id}/columns` (bulk replace identity/order/display)
  * [x] `PUT /configurations/{id}/columns/{canonical_key}/binding`
    - Request: `{ script_version_id?, params?, enabled?, required? }`
    - Enforce `script_version_id` belongs to same `configuration_id`
* [x] **Configuration Scripts (versions)**

  * [x] `POST /configurations/{id}/scripts/{canonical_key}/versions`
    - Compute `code_sha256`
    - Parse docstring (`name`, `description`, `version`) → set `doc_*`
    - Enforce `doc_name == canonical_key`
    - **Validate import** in a restricted environment
    - Ensure **at least one `detect_*`** exists
    - **Light return‑shape checks** using a tiny synthetic table for 1 detect & optional transform
    - Persist `validated_at` or `validation_errors`
    - Response: metadata + `ETag: W/"{sha256}"`
  * [x] `GET /configurations/{id}/scripts/{canonical_key}/versions` (list)
  * [x] `GET /configurations/{id}/scripts/{canonical_key}/versions/{version_id}?include_code=true` (fetch)
  * [x] `POST /configurations/{id}/scripts/{canonical_key}/versions/{version_id}:validate` (dry‑run only)
* [x] **Error model**

  * [x] Use Problem+JSON for 400/404/409; return structured `invalid_params` where relevant
  * [x] Support `If‑Match` with `ETag` (sha256) to prevent lost updates
* [x] **Security & limits**

  * [x] Validation sandbox: process isolation, import allowlist, code size cap, per‑validation timeout
  * [x] Network **disabled** during validation (runner will allow network in `setup` only)
* [ ] **OpenAPI**

  * [ ] Document ABI, endpoints, and a minimal example payload

**Exit criteria**

* You can create a config, define columns, upload/validate a configuration script version, and bind it to a column — all via API.

---

### Phase 3 — Frontend (Config & Script editor)

**Goal:** A clean authoring experience to define ordered columns, edit display, upload/validate scripts, and attach versions.

**Checklist**

* [x] **Config list & activation**

  * [x] View configurations per workspace; show active
  * [x] Create a new version (clone or empty); activate with confirmation
* [x] **Column editor**

  * [x] Add/remove/reorder (drag or ordinal)
  * [x] Edit: label, header color, width, required/enabled
  * [x] Attach/detach **script version** (per canonical key) via dropdown
  * [x] Edit per‑column `params` (JSON editor or key/value form)
  * [x] Persist via `PUT /configurations/{id}/columns` and `PUT /.../binding`
* [x] **Script editor**

  * [x] Create/upload a **configuration script version** (per canonical key)
  * [x] Code editor with syntax highlight + docstring preview
  * [x] Call `:validate` and show parsed doc + any `validation_errors`
  * [x] Display `sha256`, `validated_at`, and `doc_version`
* [x] **Guardrails**

  * [x] Confirm before swapping a bound script version on a column
  * [x] Warn when a bound version has validation errors
* [x] **Deep links**

  * [x] URLs that address a specific config version, column, or script version

**Exit criteria**

* A user can fully configure columns and script bindings, upload/validate code, and activate a configuration — end‑to‑end in the UI.

---

### Phase 4 — QA, docs, and rollout (no runtime)

**Goal:** Make the authoring layer reliable, documented, and ready to be consumed by the future runner.

**Checklist**

* [ ] **Validation hardening**

  * [ ] Malicious code tests in validation (import denial, infinite loop timeout)
  * [ ] Large file/code limits enforced
* [ ] **Security**

  * [ ] Confirm isolation & blocked network in validation
  * [ ] Ensure ETag/If‑Match works for script edits
* [ ] **Performance**

  * [ ] Bench script validation durations & memory use
* [ ] **Docs**

  * [ ] Authoring Guide (this WP + template + best practices)
  * [ ] API examples for columns/bindings/script versions
* [ ] **Feature flag**

  * [ ] Gate new endpoints if needed; staged rollout plan

**Exit criteria**

* Validation is safe and predictable; docs are clear; UI & API are ready for a runner to consume later.

---

## Acceptance criteria (for this work package)

* **Schema**: `configuration_script_versions` and `configuration_columns` exist with constraints; `configurations` keeps one active per workspace.
* **API**: create/activate configuration, CRUD columns, upload/validate script versions, and bind versions to columns.
* **UI**: configure columns, upload/validate/attach scripts, and activate a configuration.
* **ABI**: Script signature and return shapes are documented and validated; ready for a future runner to execute.

---

## Reference — Configuration Script Template (verbatim)

A **Configuration Script** is a single Python module for one canonical column key (e.g., `full_name`). The pack can include:

* an optional `setup(context)` that runs **once** and returns a `state` object,
* **one or more** `detect_*` functions (names must start with `detect_`) that run **per physical column** and return **score adjustments** (positive or negative) for `self` and/or other columns,
* an optional `transform_cell(...)` that runs **per cell** after mapping and returns **row cell outputs** for `self` and optionally other columns (fill-if-empty merge policy).

The host application handles discovery, merging, tie-breaking, and application of transforms. Authors only write small, obvious functions with a uniform return shape.


```python
"""
name: full_name
description: Detect a “Full Name” column; transform can optionally split into first/last.
version: 1
"""

# -----------------------------------------------------------------------------
# HOW THIS PACK IS USED
# • ADE imports this file.
# • OPTIONAL setup(context) runs ONCE; its return is passed to every detect_* / transform_cell as `state`.
# • ADE calls EVERY top-level function whose name starts with `detect_`.
#   Each detect_* MUST return:
#     {
#       "scores": {
#         "self": <float>,            # boosts THIS pack’s score
#         # You can also nudge OTHER columns (optional):
#         # "first_name": -1.0, "last_name": -1.0
#       }
#     }
# • After columns are mapped, ADE calls transform_cell(...) per cell (if present).
#   transform_cell MUST return:
#     {
#       "cells": {
#         "self": <normalized value>,   # written to THIS column
#         # Optional: write to OTHER columns in the SAME row (fill-if-empty):
#         # "first_name": "<value>", "last_name": "<value>"
#       }
#     }
# • Special key "self" refers to THIS pack’s canonical column key (the `name:` above).
# • setup() can also install dependencies or open client connections if your runtime allows it.
# -----------------------------------------------------------------------------

import re

# OPTIONAL — runs ONCE; keep it simple. Whatever you return here is available as `state`.
def setup(*, context):
    return {
        "common_first_names": {"john", "jane", "michael", "sarah", "david"},
        "last_comma_first_pat": re.compile(r"^\s*(?P<last>[^,]+),\s*(?P<first>[^,]+)\s*$"),
    }

# --------------------------- DETECT FUNCTIONS ---------------------------------
# Keep them tiny and obvious. Names MUST start with `detect_`.
# Each returns: {"scores": {...}}

def detect_common_first_names(
    *, header=None, values=None, table=None, column_index=None,
    sheet_name=None, bounds=None, state=None, context=None, **_
):
    """Boost if any value begins with a common first name (very simple heuristic)."""
    names = (state or {}).get("common_first_names", set())
    vals  = [str(v).strip() for v in (values or []) if str(v).strip()]
    hit   = any((v.split(",", 1)[1].strip().split()[0] if "," in v else v.split()[0]).lower() in names
                for v in vals if v)
    return {
        "scores": { **({"self": 1.0} if hit else {}) }
    }

def detect_last_comma_first_pattern(
    *, header=None, values=None, table=None, column_index=None,
    sheet_name=None, bounds=None, state=None, context=None, **_
):
    """Boost if any value matches 'Last, First'; also gently reduce first_name/last_name to avoid confusion."""
    pat  = (state or {}).get("last_comma_first_pat") or re.compile(r"^\s*[^,]+,\s*[^,]+\s*$")
    vals = [str(v).strip() for v in (values or []) if str(v).strip()]
    hit  = any(pat.match(v) for v in vals)
    return {
        "scores": {
            **({"self": 1.0} if hit else {}),
            **({"first_name": -1.0, "last_name": -1.0} if hit else {}),
        }  # +1 to self, -1 to first_name and last_name to reduce false positives when we see “Last, First”.
    }

# ------------------------------ TRANSFORM CELL --------------------------------
# Always return the same simple structure: {"cells": {...}}.

def transform_cell(
    *, value=None, row_index=None, column_index=None, table=None,
    context=None, state=None, **_
):
    """
    Normalize to 'First Last' when possible, and suggest first_name/last_name for the same row.
    Keep this readable and minimal.
    """
    s   = ("" if value is None else str(value)).strip()
    pat = (state or {}).get("last_comma_first_pat") or re.compile(r"^\s*(?P<last>[^,]+),\s*(?P<first>[^,]+)\s*$")

    # Derive first/last in the simplest possible way:
    m = pat.match(s)
    first = (m.group("first").strip().title() if m else (s.split()[0].title()  if len(s.split()) == 2 else None))
    last  = (m.group("last").strip().title()  if m else (s.split()[1].title()  if len(s.split()) == 2 else None))

    return {
        "cells": {
            # For THIS column ("self"), prefer normalized "First Last" if we derived both parts:
            "self": (f"{first} {last}" if (first and last) else s),
            # If we extracted parts, also emit first_name / last_name for the SAME row (fill-if-empty):
            **({"first_name": first, "last_name": last} if (first and last) else {}),
        }
    }
```
