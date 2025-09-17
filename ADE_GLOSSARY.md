# ADE glossary

Use this glossary when naming database columns, API fields, and UI copy. Keep wording aligned with the tables and payloads
listed beside each term.

---

## Access
- **User** – Account that can sign in. Stores an email, role, and either a password hash or an SSO subject (`users.user_id`,
  `users.email`, `users.role`).
- **Role** – Permission tier. Default roles: `viewer`, `editor`, `admin`.
- **Session** – Short-lived token created during UI sign-in (`sessions.session_token`).
- **API key** – Token issued by an admin; inherits the linked user’s role (`api_keys.api_key_id`, `api_keys.user_id`).

---

## Core domain
- **Document type** – Family of documents that share extraction rules (`snapshots.document_type`).
- **Snapshot** – Immutable bundle of logic for a document type. Drafts can change; the published snapshot is read only
  (`snapshots.snapshot_id` ULID, `snapshots.is_published`, `snapshots.published_at`).
- **Profile** – Optional overrides for a source, customer, or locale stored in the snapshot payload (`payload.profiles`).
- **Live snapshot** – The single published snapshot for a document type. API consumers use it by default when they do not
  supply an explicit `snapshot_id` (`snapshots.is_published = 1`).
- **Run** – Execution of the processing engine against one or more documents (`manifests.run_id` ULID).
- **Manifest** – JSON result of a run: tables, column mappings, audit data, statistics, and the `snapshot_id` used
  (`manifests.payload`).

---

## Document anatomy
- **Document** – Path or upload ID for the file being processed (XLSX, CSV, PDF, etc.). Files live in `var/documents/`
  (`manifests.document`).
- **Page** – Worksheet or PDF page captured in a manifest (`pages[].index`).
- **Table** – Contiguous rows and columns with a single header row (`tables[].index`).
- **Row type** – Classification emitted by the header finder (`header`, `data`, `group_header`, `note`) (`rows[].row_type`).
- **Header row** – Row index that names the columns (`tables[].header_row`).
- **Column** – Observed column with header text, samples, and metadata (`columns[].index`).

---

## Column logic
- **Column catalogue** (`column_catalog`) – Allowed column type keys for a document type. Lives inside the snapshot payload.
- **Column type** (`column_type`) – Canonical meaning such as `member_full_name` or `gross_amount`.
- **Synonyms** (`synonyms`) – Header strings or regexes that hint at the column type.
- **Detection logic** (`detection_logic`) – Pure Python callable (code + digest) returning a match decision or score.
- **Transformation** (`transformation_logic`) – Optional callable that normalises raw values.
- **Validation** (`validation_logic`) – Optional callable that flags invalid or suspicious values.
- **Schema rules** (`schema`) – Required and optional column types.

---

## Run outputs
- **Column mapping** (`column_mapping`) – Assignment of observed columns to column types with scores and audit notes.
- **Confidence** (`confidence`, 0–1) – Normalised certainty for a mapping or decision.
- **Needs review** (`needs_review`) – Boolean flag when validation fails or the decision margin is thin.
- **Audit log** (`audit_log`) – Ordered messages explaining why a column matched (rule hits, transforms, etc.).
- **Digest** (`digest`, e.g., `sha256:…`) – Hash of logic source used for caching and audit trails.
- **Stats** (`stats`) – Summary counts such as tables found, rows processed, and warnings.

---

## Storage foundation
ADE stores everything in SQLite (`var/ade.sqlite`). Tables expected on day one:
- `snapshots` – Snapshot metadata, JSON payloads, and publication state.
- `manifests` – Run outputs and manifest payloads.
- `users` – Accounts with roles and optional SSO subjects.
- `api_keys` – Issued API keys linked to users.

Back up the SQLite file alongside the `var/documents/` directory.

---

## Payload cheat sheets
```jsonc
// Snapshot payload (abbreviated)
{
  "snapshot": {
    "snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
    "document_type": "remittance",
    "title": "Remittance default rules",
    "header_finder": {
      "rules": [
        {"name": "has_amount_headers", "code": "...", "digest": "sha256:…"}
      ]
    },
    "column_catalog": ["member_full_name", "gross_amount"],
    "column_types": {
      "gross_amount": {
        "synonyms": ["gross remittance"],
        "detection_logic": {"code": "...", "digest": "sha256:…"}
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

```jsonc
// Manifest payload (abbreviated)
{
  "run_id": "run_01J8Q…",
  "document_type": "remittance",
  "snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
  "document": "examples/remittance.xlsx",
  "pages": [
    {
      "index": 0,
      "tables": [
        {
          "header_row": 2,
          "column_mapping": [
            {
              "column_index": 0,
              "column_type": "member_full_name",
              "confidence": 0.92,
              "needs_review": false,
              "audit_log": ["synonym: member name"]
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

## Working agreements
- Snapshots flow draft → test → publish; publishing only updates the live pointer.
- Always compare snapshots before publishing to understand behavioural changes.
- Manifests include the `snapshot_id` so reruns remain deterministic.
- Profiles stay inside the snapshot payload to avoid hidden configuration.
- Detection, transformation, validation, and header rules are pure functions (no I/O, deterministic results).
- Flag `needs_review: true` when validation fails or confidence dips below the configured threshold.
- Table boundaries on a page must not overlap.

---

This glossary is the naming authority for code, APIs, and UI copy.
