# ADE Glossary

Plain language first. Terms shown in `code` match identifiers in the API, SQLite schema, or UI.

---

## Accounts & access

- **User** (`user_id`, table `users`): Account that can sign in. Stores hashed password or SSO metadata.
- **Role** (`role`): `viewer`, `editor`, or `admin`; determines editing, publishing, and user management rights.
- **Session** (`session_token`, table `sessions`): Short-lived token created during UI sign-in.
- **API key** (`api_key_id`, table `api_keys`): Token issued by an admin. Keys inherit the linked user’s role permissions.

---

## Documents, logic, and runs

- **Document type** (`document_type`): Family of documents that share rules (e.g., payroll remittance). Stored alongside snapshots and manifests.
- **Snapshot** (`snapshot_id`, ULID, table `snapshots`): Immutable configuration for a document type. Drafts are editable; live and archived snapshots are read-only.
- **Profile** (`profile`): Optional overrides scoped to a source, customer, or locale. Lives inside the snapshot payload.
- **Live pointer** (`live_snapshot_id`, table `live_registry`): Maps a document type (and optional profile) to the snapshot used in production.
- **Run** (`run_id`, ULID, table `manifests`): Execution of the processing engine against a document plus one or more snapshots.
- **Manifest** (`payload`, column `manifests.payload`): Result of a run—tables, column mappings, audit data, stats, and the `snapshot_id` used.

---

## Document anatomy

- **Document** (`document`): Path or upload ID for the file being processed (XLSX, CSV, PDF, etc.). Stored in `manifests.document`.
- **Page** (`page.index`): Worksheet or PDF page reference inside a manifest.
- **Table** (`table.index`): Contiguous rows/columns with a single header row.
- **Row type** (`row_type`: `header`, `data`, `group_header`, `note`): Classification emitted by the header finder.
- **Header row** (`header_row`): Chosen row index that names the columns.
- **Column** (`column.index`): Observed column with header text, samples, and metadata.

---

## Column logic

- **Column catalogue** (`column_catalog`): List of allowed column type keys for a document type. Lives in the snapshot payload.
- **Column type** (`column_type`): Canonical meaning such as `member_full_name` or `gross_amount`.
- **Synonyms** (`synonyms`): Header strings or regexes that hint the column type.
- **Detection logic** (`detection_logic`): Pure Python callable (code + digest) returning a match decision or score.
- **Transformation** (`transformation_logic`): Optional callable to normalise raw values.
- **Validation** (`validation_logic`): Optional callable to flag invalid or suspicious values.
- **Schema rules** (`schema`): Lists of required and optional column types.

---

## Run results

- **Column mapping** (`column_mapping`): Assignment of observed columns to column types with scores and audit notes.
- **Confidence** (`confidence`, 0–1): Normalised certainty for a mapping or decision.
- **Needs review** (`needs_review`): Boolean flag when validation fails or the decision margin is thin.
- **Audit log** (`audit_log`): Ordered messages explaining why a column matched (rule hits, transforms, etc.).
- **Digest** (`digest`, e.g., `sha256:…`): Hash of logic source used for caching and audit trails.
- **Stats** (`stats`): Summary counts such as tables found, rows processed, and warnings.

---

## Storage quick reference

Everything lives in a single SQLite database file (`var/ade.sqlite`). Key tables:

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
  user_id       TEXT PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  role          TEXT NOT NULL CHECK(role IN ('viewer','editor','admin')),
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

Snapshots and manifests live as JSON blobs so evolving the schema rarely requires migrations. Backups are a file copy of the SQLite database plus the `var/documents/` directory.

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

- Draft → test → publish is the lifecycle for snapshots; publishing only updates the live pointer.
- Run comparisons between snapshots before publishing to understand behaviour changes.
- Manifests must always include the `snapshot_id` so reruns remain deterministic.
- Profiles live inside the snapshot payload to avoid hidden configuration.

---

## Guardrails

- Snapshots marked `live` or `archived` are read-only; create a new draft for changes.
- Every required column type in the schema must exist in the column catalogue.
- Detection, transformation, validation, and header rules are pure functions (no I/O, deterministic results).
- Digests are recalculated whenever code changes to support caching and audit checks.
- Table boundaries on a page may not overlap.
- Set `needs_review: true` when validation fails or confidence drops below the configured threshold.

---

This glossary is the single source of truth when naming things in code, APIs, or the UI.
