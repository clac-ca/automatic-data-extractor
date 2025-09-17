# ADE Glossary

Plain language first. API field names or SQLite columns appear in backticks. Use this glossary when naming code, API
contracts, or UI elements.

---

## Naming conventions

* **UI labels** — Title Case (`Column Type`).
* **API keys and SQLite columns** — `snake_case` (`column_type`).
* **Enum values** — lowercase strings (`row_type: "header"`).
* **Snapshots** — Immutable; "live" is just a pointer stored in SQLite.

---

## Document lifecycle terms

| Term (UI) | Key / Identifier | Stored in | Summary |
| --- | --- | --- | --- |
| Document | `document` (path or upload id) | `manifests.payload.document` | Input file (XLSX, CSV, PDF) processed for a document type. |
| Page | `page.index` | Manifest payload | Worksheet or PDF page. |
| Table | `table.index` per page | Manifest payload | Contiguous rows/columns with one header row plus data rows. |
| Row type | `row_type` (`header`, `data`, `group_header`, `note`) | Manifest payload | Classification emitted by the header finder. |
| Header row | `header_row` | Manifest payload | Winning row index used to name the columns. |
| Column | `column.index` | Manifest payload | Observed column with header text and sampled values. |

---

## Column semantics

| Term (UI) | Key / Identifier | Stored in | Summary |
| --- | --- | --- | --- |
| Column catalog | `column_catalog` | Snapshot payload | Allowed column type keys for a document type. |
| Column type | `column_type` | Snapshot payload | Canonical meaning for a column (`member_full_name`, `gross_amount`). |
| Synonyms | `synonyms` | Snapshot payload | Header strings or regexes used during detection. |
| Detection logic | `detection_logic` | Snapshot payload | Pure Python callable returning a match decision (bool/score). |
| Transformation | `transformation_logic` | Snapshot payload | Optional callable to normalise values. |
| Validation | `validation_logic` | Snapshot payload | Optional callable to flag invalid or suspicious values. |

---

## Configuration & release

| Term (UI) | Key / Identifier | Stored in | Summary |
| --- | --- | --- | --- |
| Snapshot | `snapshot_id` (ULID) | `snapshots` table | Immutable configuration bundle for a document type. |
| Snapshot status | `status` (`draft`, `live`, `archived`) | `snapshots` table | Drafts are editable; live/archived are read-only. |
| Live pointer | `live_snapshot_id` | `live_registry` table | Maps document type (+ optional profile) to the snapshot in production. |
| Profile | `profile` | Snapshot payload | Optional overrides (extra synonyms, thresholds) scoped to a source or customer. |
| Snapshot export | `.json` file | Filesystem | JSON dump of a snapshot payload used for review and backup. |

Rule of thumb: create a new draft instead of mutating a live snapshot.

---

## Run output

| Term (UI) | Key / Identifier | Stored in | Summary |
| --- | --- | --- | --- |
| Manifest | `manifest` | `manifests` table | Result of a run: mappings, audit data, and the pinned snapshot ID. |
| Column mapping | `column_mapping` | Manifest payload | Assignment of observed columns to column types with scores and audit notes. |
| Confidence | `confidence` (0–1) | Manifest payload | Normalised certainty for a mapping. |
| Needs review | `needs_review` (bool) | Manifest payload | Flag when validation fails or the decision margin is thin. |
| Audit log | `audit_log` | Manifest payload | Ordered messages showing why a column matched (rules, transforms, validations). |
| Digest | `digest` (`sha256:…`) | Snapshot & Manifest | Hash of logic source used for caching and auditing. |

---

## Platform components

| Term | Summary |
| --- | --- |
| **Frontend** | Vite-powered TypeScript UI that consumes the FastAPI routes for configuration, testing, publishing, and uploads. |
| **FastAPI backend** | Stateless Python application exposing REST routes and OpenAPI docs. |
| **Processing engine** | Pure Python module that runs table detection, header finding, column mapping, and value logic. |
| **Document storage** | Folder mounted into the container (`./var/documents` by default) that holds uploaded files. |
| **SQLite (`ade.sqlite`)** | Single-file database containing snapshots, live registry, manifests, and audit metadata. |
| **Docker image** | Deployable artefact bundling the frontend, backend, and processing engine. |

---

## SQLite storage model

ADE persists everything in one SQLite database (`ade.sqlite`). Schema expressed in SQL for quick reference:

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
```

Snapshots and manifests live as JSON blobs, so evolving the schema rarely needs migrations. Export those blobs for
experimentation, review, or backup.

---

## Snapshot payload sketch

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

---

## Manifest payload sketch

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

* Clone → edit → test → publish is the lifecycle for snapshots. Publishing only updates the live pointer.
* Live pointer updates are transactional; failures leave the pointer untouched.
* Manifests must always include the `snapshot_id` so reruns remain deterministic.
* Profiles live inside the snapshot payload to avoid hidden configuration.

---

## Invariants & guardrails

* Snapshots marked `live` or `archived` are read-only; create a new draft to change behaviour.
* Every required column type in the schema must exist in the column catalog.
* Detection, transformation, validation, and header rules are pure functions (no I/O, deterministic results).
* Digests are recalculated whenever code changes to support caching and audit checks.
* Table boundaries on a page may not overlap.
* Set `needs_review: true` when validation fails or the decision margin drops below the configured threshold.

---

## Implementation notes

* Cache compiled logic by `digest` so repeated runs avoid recompilation.
* Allow detectors and transformers to receive a context dict (for locale, currency) derived from the snapshot profile.
* Execute logic inside a sandbox with CPU and memory limits to keep runs predictable.
* Maintain a small labelled corpus per document type to evaluate new snapshots before publishing.

---

This glossary is the single source of truth when naming things in code, APIs, or the UI.
