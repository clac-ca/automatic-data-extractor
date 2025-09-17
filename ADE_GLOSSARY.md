# ADE Glossary

Plain language first. Names in `code` are the identifiers you will see in the API, SQLite, and the UI.

---

## Naming basics

* **UI labels** – Title Case (`Column Type`).
* **API keys & SQLite columns** – `snake_case` (`column_type`).
* **Enum values** – lower-case strings (`row_type: "header"`).
* **Snapshots** – Immutable bundles; `live` is only a pointer stored in SQLite.

---

## Core concepts

| Term | Identifier | Stored in | Description |
| --- | --- | --- | --- |
| Document type | `document_type` | `snapshots`, `manifests` | Family of documents that share rules (e.g., payroll remittance). |
| Snapshot | `snapshot_id` (ULID) | `snapshots` | Immutable configuration bundle for a document type. Drafts are editable; live and archived snapshots are read-only. |
| Profile | `profile` | Snapshot payload | Optional overrides (synonyms, thresholds, context) scoped to a source, customer, or locale. |
| Run | `run_id` (ULID) | `manifests` | Execution of the processing engine against a document + snapshot. |
| Manifest | `payload` | `manifests.payload` | Result of a run: detected tables, column mappings, audit data, stats, and the `snapshot_id` used. |
| Live pointer | `live_snapshot_id` | `live_registry` | Maps a document type (and optional profile) to the snapshot used in production. |

---

## Document anatomy

| UI term | Identifier | Stored in | Description |
| --- | --- | --- | --- |
| Document | `document` (path or upload id) | `manifests.document` | File processed for a document type (XLSX, CSV, PDF, etc.). |
| Page | `page.index` | Manifest payload | Worksheet or PDF page. |
| Table | `table.index` per page | Manifest payload | Contiguous range of rows/columns with a single header row. |
| Row type | `row_type` (`header`, `data`, `group_header`, `note`) | Manifest payload | Classification emitted by the header finder. |
| Header row | `header_row` | Manifest payload | Winning row index used to name the columns. |
| Column | `column.index` | Manifest payload | Observed column with header text, samples, and metadata. |

---

## Column logic

| UI term | Identifier | Stored in | Description |
| --- | --- | --- | --- |
| Column catalogue | `column_catalog` | Snapshot payload | Allowed column type keys for a document type. |
| Column type | `column_type` | Snapshot payload | Canonical meaning (`member_full_name`, `gross_amount`, etc.). |
| Synonyms | `synonyms` | Snapshot payload | Header strings or regexes that hint the column type. |
| Detection logic | `detection_logic` | Snapshot payload | Pure Python callable (code + digest) returning a match decision/score. |
| Transformation | `transformation_logic` | Snapshot payload | Optional callable to normalise raw values. |
| Validation | `validation_logic` | Snapshot payload | Optional callable to flag invalid or suspicious values. |
| Schema rules | `schema` | Snapshot payload | Lists of required and optional column types. |

---

## Run results

| Term | Identifier | Stored in | Description |
| --- | --- | --- | --- |
| Column mapping | `column_mapping` | Manifest payload | Assignment of observed columns to column types with scores and audit notes. |
| Confidence | `confidence` (0–1) | Manifest payload | Normalised certainty for a mapping or decision. |
| Needs review | `needs_review` (bool) | Manifest payload | Flag set when validation fails or the decision margin is thin. |
| Audit log | `audit_log` | Manifest payload | Ordered messages explaining why a column matched, including rule hits and transforms. |
| Digest | `digest` (`sha256:…`) | Snapshot & manifest payloads | Hash of logic source used for caching and audit trails. |
| Stats | `stats` | Manifest payload | Summary counts (tables found, rows processed, warnings, etc.). |

---

## Platform & access

| Term | Identifier | Stored in | Description |
| --- | --- | --- | --- |
| User | `user_id` | `users` | Account that can sign in to the UI. Stores hashed passwords or SSO metadata. |
| Role | `role` | `users.role` | Access level: `viewer`, `editor`, or `admin`. Governs editing and publishing rights. |
| API key | `api_key_id` | `api_keys` | Token issued by an admin that maps to a user and inherits their role. |
| Session | `session_token` | `sessions` | Short-lived token created during UI sign-in. |

---

## SQLite quick reference

Everything lives in one database file (`var/ade.sqlite`). Key tables:

```sql
CREATE TABLE snapshots (
  snapshot_id     TEXT PRIMARY KEY,
  document_type   TEXT NOT NULL,
  status          TEXT NOT NULL CHECK(status IN ('draft','live','archived')),
  created_at      TEXT NOT NULL,
  created_by      TEXT NOT NULL,
  payload         JSON NOT NULL
);

CREATE TABLE live_registry (
  document_type      TEXT PRIMARY KEY,
  live_snapshot_id   TEXT NOT NULL,
  profile_overrides  JSON DEFAULT NULL,
  updated_at         TEXT NOT NULL,
  updated_by         TEXT NOT NULL
);

CREATE TABLE manifests (
  run_id         TEXT PRIMARY KEY,
  snapshot_id    TEXT NOT NULL,
  document_type  TEXT NOT NULL,
  profile        TEXT,
  generated_at   TEXT NOT NULL,
  document       TEXT NOT NULL,
  payload        JSON NOT NULL
);

CREATE TABLE users (
  user_id      TEXT PRIMARY KEY,
  email        TEXT UNIQUE NOT NULL,
  role         TEXT NOT NULL CHECK(role IN ('viewer','editor','admin')),
  password_hash TEXT,
  sso_subject   TEXT
);

CREATE TABLE api_keys (
  api_key_id   TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL,
  hashed_key   TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  revoked_at   TEXT
);
```

Snapshots and manifests live as JSON blobs so evolving the schema rarely requires migrations. Backups are a file copy.

---

## Snapshot payload cheat sheet

```json
{
  "snapshot": {
    "snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
    "document_type": "remittance",
    "title": "Remittance default rules",
    "note": "Baseline rules for 2025",
    "header_finder": {
      "rules": [
        {"name": "has_amount_headers", "code": "...", "digest": "sha256:…"}
      ],
      "decision": {"scoring": "boolean", "tie_breaker": "prefer_first_header"}
    },
    "column_catalog": ["member_full_name", "gross_amount"],
    "column_types": {
      "gross_amount": {
        "synonyms": ["gross remittance"],
        "detection_logic": {"code": "...", "digest": "sha256:…"},
        "transformation_logic": {"code": "..."},
        "validation_logic": {"code": "..."}
      }
    },
    "schema": {
      "required_column_types": ["member_full_name", "gross_amount"],
      "optional_column_types": ["union_local"]
    },
    "profiles": {
      "default": {
        "synonyms_overrides": {"member_full_name": ["member"]}
      }
    }
  }
}
```

---

## Manifest payload cheat sheet

```json
{
  "run_id": "run_01J8Q…",
  "document_type": "remittance",
  "snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
  "profile": "default",
  "document": "examples/remittance.xlsx",
  "pages": [
    {
      "index": 0,
      "tables": [
        {
          "header_row": 2,
          "rows": [{"index": 1, "row_type": "group_header"}],
          "columns": [{"index": 0, "header_text": "Member Name"}],
          "column_mapping": [
            {
              "column_index": 0,
              "column_type": "member_full_name",
              "confidence": 0.92,
              "needs_review": false,
              "audit_log": ["synonym: member name", "transform: title_case"]
            }
          ]
        }
      ]
    }
  ],
  "stats": {"tables_found": 1}
}
```

---

## Workflow reminders

* Draft → test → publish is the lifecycle for snapshots; publishing only updates the live pointer.
* Run comparisons between snapshots before publishing to understand behaviour changes.
* Manifests must always include the `snapshot_id` so reruns remain deterministic.
* Profiles live inside the snapshot payload to avoid hidden configuration.

---

## Guardrails

* Snapshots marked `live` or `archived` are read-only; create a new draft for changes.
* Every required column type in the schema must exist in the column catalogue.
* Detection, transformation, validation, and header rules are pure functions (no I/O, deterministic results).
* Digests are recalculated whenever code changes to support caching and audit checks.
* Table boundaries on a page may not overlap.
* Set `needs_review: true` when validation fails or confidence drops below the configured threshold.

---

This glossary is the single source of truth when naming things in code, APIs, or the UI.
