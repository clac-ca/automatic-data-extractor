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
- **Document type** – Family of documents that share a configuration (`configuration_revisions.document_type`, `jobs.document_type`).
- **Configuration** – Executable detection, transformation, and metadata logic that defines how ADE processes a document type. Stored as JSON on each configuration revision (`configuration_revisions.payload`).
- **Configuration revision** – Immutable record of configuration logic for a document type. Draft revisions can change; activating one freezes the payload (`configuration_revisions.configuration_revision_id` ULID, `configuration_revisions.revision_number`, `configuration_revisions.is_active`, `configuration_revisions.activated_at`).
- **Active configuration revision** – The single revision with `is_active = true` for a document type. API consumers use it by default when they do not supply an explicit `configuration_revision_id`.
- **Profile** – Optional overrides for a source, customer, or locale stored in the configuration payload (`payload.profiles`).
- **Job** – One execution of the processing engine against an input document using a specific configuration revision (`jobs.job_id`, `jobs.configuration_revision_number`, `jobs.status`, `jobs.created_by`, `jobs.metrics`, `jobs.logs`). Jobs stay mutable while `status` is `pending` or `running` and become immutable once marked `completed` or `failed`.

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
- **Column catalogue** (`column_catalog`) – Allowed column type keys for a document type. Lives inside the revision payload.
- **Column type** (`column_type`) – Canonical meaning such as `member_full_name` or `gross_amount`.
- **Synonyms** (`synonyms`) – Header strings or regexes that hint at the column type.
- **Detection logic** (`detection_logic`) – Pure Python callable (code + digest) returning a match decision or score.
- **Transformation** (`transformation_logic`) – Optional callable that normalises raw values.
- **Validation** (`validation_logic`) – Optional callable that flags invalid or suspicious values.
- **Configuration requirements** (`configuration.required_column_types`, `configuration.optional_column_types`) – Required and optional column types.

---

## Job payload
- **Input** (`jobs.input`) – Source document metadata with `uri`, `hash`, and optional `expires_at`.
- **Outputs** (`jobs.outputs`) – Mapping of output artefacts (e.g., JSON, Excel) to URIs and expiration timestamps.
- **Status** (`jobs.status`) – Lifecycle state: `pending`, `running`, `completed`, or `failed`.
- **Metrics** (`jobs.metrics`) – Summary statistics such as `rows_extracted`, `processing_time_ms`, and `errors`.
- **Logs** (`jobs.logs`) – Ordered log entries with timestamp, level, and message for auditability.

---

## Storage foundation
ADE stores everything in SQLite (`var/ade.sqlite`). Tables expected on day one:
- `configuration_revisions` – Configuration metadata, JSON payloads, immutable history, and lifecycle state.
- `jobs` – Job inputs, outputs, metrics, logs, and status tied to configuration revisions.
- `users` – Accounts with roles and optional SSO subjects.
- `api_keys` – Issued API keys linked to users.

Back up the SQLite file alongside the `var/documents/` directory.

---

## Payload cheat sheets
```jsonc
// Configuration revision payload (abbreviated)
{
    "configuration_revision": {
    "configuration_revision_id": "rev_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
    "document_type": "remittance",
    "revision_number": 7,
    "is_active": false,
    "title": "Remittance default configuration",
    "payload": {
      "column_catalog": ["member_full_name", "gross_amount"],
      "column_types": {
        "gross_amount": {
          "synonyms": ["gross remittance"],
          "detection_logic": {"code": "...", "digest": "sha256:…"},
          "transformation_logic": {"code": "...", "digest": "sha256:…"},
          "validation_logic": {"code": "...", "digest": "sha256:…"},
          "scoring_logic": {"code": "...", "digest": "sha256:…"}
        }
      },
      "configuration": {
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
}
```

```jsonc
// Job payload (abbreviated)
{
  "job_id": "job_2025_09_17_0001",
  "document_type": "Remittance PDF",
  "configuration_revision": 3,

  "status": "completed",
  "created_at": "2025-09-17T18:42:00Z",
  "updated_at": "2025-09-17T18:45:11Z",
  "created_by": "jkropp",

  "input": {
    "uri": "var/documents/remit_2025-09.pdf",
    "hash": "sha256:a93c...ff12",
    "expires_at": "2025-10-01T00:00:00Z"
  },

  "outputs": {
    "json": {
      "uri": "var/outputs/remit_2025-09.json",
      "expires_at": "2026-01-01T00:00:00Z"
    },
    "excel": {
      "uri": "var/outputs/remit_2025-09.xlsx",
      "expires_at": "2026-01-01T00:00:00Z"
    }
  },

  "metrics": {
    "rows_extracted": 125,
    "processing_time_ms": 4180,
    "errors": 0
  },

  "logs": [
    { "ts": "2025-09-17T18:42:00Z", "level": "info", "message": "Job started" },
    { "ts": "2025-09-17T18:42:01Z", "level": "info", "message": "Detected table 'MemberContributions'" },
    { "ts": "2025-09-17T18:44:59Z", "level": "info", "message": "125 rows processed" },
    { "ts": "2025-09-17T18:45:11Z", "level": "info", "message": "Job completed successfully" }
  ]
}
```

---

## Working agreements
- Configuration revisions flow draft → active → retired; activation only updates the live pointer.
- Always compare configuration revisions before activating to understand behavioural changes.
- Jobs include the `configuration_revision_id` so reruns remain deterministic.
- Profiles stay inside the configuration payload to avoid hidden configuration drift.
- Detection, transformation, validation, and header rules are pure functions (no I/O, deterministic results).
- Flag `needs_review: true` when validation fails or confidence dips below the configured threshold.
- Table boundaries on a page must not overlap.

---

This glossary is the naming authority for code, APIs, and UI copy.
