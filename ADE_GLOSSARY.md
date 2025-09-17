# ADE Glossary

The glossary defines the vocabulary, identifiers, and lightweight data model that the Automatic Data Extractor (ADE) uses. It is tuned for day-to-day engineering and configuration work—plain words first, precise keys when needed.

---

## Conventions

* **UI labels** use Title Case (`Column Type`).
* **API keys / storage keys** use `snake_case` (`column_type`).
* **Enum values** are lowercase strings (`row_type: "header"`).
* **Snapshots** are immutable. "Live" is a pointer to a snapshot ID stored in SQLite.

---

## Core terms

### Document processing

| Term (UI)     | Key / Identifier           | Stored in    | Summary |
| ------------- | -------------------------- | ------------ | ------- |
| Document      | `document` (path or ID)    | Manifest     | A single file (XLSX, CSV, PDF) processed under one document type. |
| Page          | `page.index`               | Manifest     | Spreadsheet worksheet or PDF page. |
| Table         | `table.index` per page     | Manifest     | Contiguous rows and columns with one header row plus data rows. |
| Row type      | `row_type` (`header`, …)   | Manifest     | Classification produced by the header finder. |
| Header row    | `header_row`               | Manifest     | Winning row index used to name the columns. |
| Column        | `column.index`             | Manifest     | Observed column with header text and sampled values. |

### Column semantics

| Term (UI)       | Key / Identifier     | Stored in | Summary |
| --------------- | ------------------- | --------- | ------- |
| Column catalog  | `column_catalog`     | Snapshot  | List of allowed column type keys for a document type. |
| Column type     | `column_type`        | Snapshot  | Canonical meaning for a column (`member_full_name`, `gross_amount`). |
| Synonyms        | `synonyms`           | Snapshot  | Alternate header strings or regexes used during detection. |
| Detection logic | `detection_logic`    | Snapshot  | Pure Python callable returning a match decision (bool/score). |
| Transformation  | `transformation_logic` | Snapshot | Optional callable to normalize values after mapping. |
| Validation      | `validation_logic`   | Snapshot  | Optional callable to flag invalid or suspicious values. |

### Configuration & outputs

| Term (UI)        | Key / Identifier        | Stored in           | Summary |
| ---------------- | ----------------------- | ------------------- | ------- |
| Snapshot         | `snapshot_id` (ULID)    | `snapshots` table   | Immutable configuration bundle for a document type. |
| Live pointer     | `live_snapshot_id`      | `live_registry`     | Mapping of document type (+ optional profile) to the snapshot currently in production. |
| Profile          | `profile`               | Snapshot            | Optional overrides (extra synonyms, thresholds) keyed by source. |
| Manifest         | `manifest`              | `manifests` table   | Result of a run: mappings, audit data, and the pinned snapshot ID. |
| Column mapping   | `column_mapping`        | Manifest            | Assignment of observed columns to column types with scores and audit notes. |
| Confidence       | `confidence` (0–1)      | Manifest            | Normalized certainty for a mapping. |
| Needs review     | `needs_review` (bool)   | Manifest            | Flag when validation fails or the decision margin is thin. |
| Audit log        | `audit_log`             | Manifest            | Ordered messages showing why a column matched (rules, transforms, validations). |
| Digest           | `digest` (sha256)       | Snapshot & Manifest | Hash of logic source used for caching and auditing. |

---

## Data model essentials

ADE keeps persistence minimal with a single SQLite database (`ade.sqlite` by default). Tables can be created with `sqlite_utils` or standard migrations.

```sql
CREATE TABLE snapshots (
  snapshot_id     TEXT PRIMARY KEY,
  document_type   TEXT NOT NULL,
  status          TEXT NOT NULL CHECK(status IN ('draft','live','archived')),
  created_at      TEXT NOT NULL,
  created_by      TEXT NOT NULL,
  payload         JSON NOT NULL              -- catalog, column types, header finder, schema, profiles
);

CREATE TABLE live_registry (
  document_type      TEXT PRIMARY KEY,
  live_snapshot_id   TEXT NOT NULL,
  profile_overrides  JSON DEFAULT NULL,      -- profile -> snapshot_id
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
  payload        JSON NOT NULL               -- pages, tables, column mappings, stats
);
```

Snapshots and manifests are JSON blobs, so evolving the schema rarely requires migrations. For local experimentation, storing exported JSON files alongside the SQLite database is still encouraged.

### Snapshot payload sketch

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
      "decision": {
        "scoring": "boolean",
        "tie_breaker": "prefer_first_header"
      }
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
        "synonyms_overrides": {
          "member_full_name": ["member"]
        }
      }
    }
  }
}
```

### Manifest payload sketch

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

* **Clone → edit → test → publish** is the lifecycle for snapshots. Publishing updates only the Live pointer.
* **Live pointer updates** are transactional; if anything fails the pointer remains unchanged.
* **Manifests** must always include the `snapshot_id` so reruns are deterministic.
* **Profiles** live inside the snapshot payload to avoid hidden configuration.

---

## Invariants & guardrails

* Snapshots marked `live` or `archived` are read-only. Create a new draft to make changes.
* Every required column type in the schema must exist in the column catalog.
* Detection, transformation, validation, and header rules are pure functions (no I/O, deterministic results).
* Digests are recalculated whenever code changes to support caching and audit checks.
* Table boundaries on a page may not overlap.
* Set `needs_review: true` when validation fails or when the decision margin drops below the configured threshold.

---

## Implementation notes

* Cache compiled logic by `digest` so repeated runs avoid recompilation.
* Allow detectors/transformers to receive a context dict (e.g., `locale`, `currency`) derived from the snapshot profile.
* Execute logic inside a sandbox with CPU and memory limits to keep runs predictable.
* Keep a small labelled corpus per document type to evaluate new snapshots before publishing.

---

Use this glossary as the single source of truth when naming things in code, APIs, or the user interface.
