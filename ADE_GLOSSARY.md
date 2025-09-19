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
- **Document type** – Family of documents that share a configuration (`configurations.document_type`, `jobs.document_type`).
- **Document record** – Canonical metadata for an uploaded file (`documents.document_id`, `documents.original_filename`, `documents.content_type`, `documents.byte_size`, `documents.sha256`, `documents.stored_uri`, `documents.metadata`, `documents.expires_at`, `documents.deleted_at`, `documents.deleted_by`, `documents.delete_reason`). Document identifiers are ULIDs reused as filenames under `var/documents/uploads/`.
- **Configuration** – Executable detection, transformation, and metadata logic that defines how ADE processes a document type. Each configuration row is immutable and stored as JSON (`configurations.configuration_id`, `configurations.version`, `configurations.is_active`, `configurations.activated_at`, `configurations.payload`).
- **Active configuration** – The single configuration with `is_active = true` for a document type. API consumers use it by default when they do not supply an explicit `configuration_id`.
- **Profile** – Optional overrides for a source, customer, or locale stored in the configuration payload (`payload.profiles`).
- **Job** – One execution of the processing engine against an input document using a specific configuration version (`jobs.job_id`, `jobs.configuration_version`, `jobs.status`, `jobs.created_by`, `jobs.metrics`, `jobs.logs`). Jobs stay mutable while `status` is `pending` or `running` and become immutable once marked `completed` or `failed`.
- **Event** – Immutable record that captures what happened to an entity, who triggered it, and any structured context (`events.event_id`, `events.event_type`, `events.entity_type`, `events.entity_id`, `events.occurred_at`, `events.actor_type`, `events.actor_id`, `events.actor_label`, `events.source`, `events.request_id`, `events.payload`). Document deletions emit `document.deleted`, metadata edits emit `document.metadata.updated` by default (callers may supply a more specific type), configuration lifecycle changes emit `configuration.created` / `configuration.updated` / `configuration.activated`, and jobs report `job.created`, `job.status.*`, and `job.results.published` entries. Timelines are available at `GET /documents/{document_id}/events`, `GET /configurations/{configuration_id}/events`, and `GET /jobs/{job_id}/events`; document, configuration, and job responses embed an `entity` summary with the identifiers, filenames, and statuses needed for UI headers, and the shared `/events` feed reuses the same summary when filters scope to a single entity.

---

## Document anatomy
- **Document** – Canonical upload tracked by ADE. The API exposes its metadata via `/documents` (`documents.document_id`, `documents.stored_uri`). Document IDs are ULIDs reused as filenames, so files live at `var/documents/uploads/{document_id}` for uploads and `var/documents/output/` for derived artefacts.
- **Stored URI** – Canonical relative path that jobs reference when describing inputs (`documents.stored_uri`). Uses deterministic segments such as `uploads/{document_id}` for source files and `output/<name>` for generated artefacts anchored under `var/documents/` on disk.
- **Document hash** – SHA-256 digest captured for auditing and integrity checks (`documents.sha256`). Prefixed with `sha256:` in responses.
- **Page** – Worksheet or PDF page captured in a manifest (`pages[].index`).
- **Table** – Contiguous rows and columns with a single header row (`tables[].index`).
- **Row type** – Classification emitted by the header finder (`header`, `data`, `group_header`, `note`) (`rows[].row_type`).
- **Header row** – Row index that names the columns (`tables[].header_row`).
- **Column** – Observed column with header text, samples, and metadata (`columns[].index`).
- **Document expiration** – Timestamp describing when operators may purge the stored bytes (`documents.expires_at`). Defaults to 30 days after ingest and may be overridden per upload. Future retention metadata (legal hold flags, override provenance) will extend this section.
- **Legal hold** – Boolean flag that blocks deletion until cleared (`documents.legal_hold`).
- **Manual deletion markers** – Soft-delete columns plus the events feed capturing intentional removal of stored bytes (`documents.deleted_at`,
  `documents.deleted_by`, `documents.delete_reason`, corresponding `events` rows with `event_type="document.deleted"`).
- **Purge markers** – (Planned) lifecycle timestamps for automated deletions (`documents.purge_requested_at`,
  `documents.purged_at`, `documents.purged_by`).

---

## Column logic
- **Column catalogue** (`column_catalog`) – Allowed column type keys for a document type. Lives inside the configuration payload.
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
- `configurations` – Configuration metadata, JSON payloads, immutable history, and lifecycle state.
- `documents` – Uploaded file metadata, SHA-256 digests, and canonical storage URIs.
- `jobs` – Job inputs, outputs, metrics, logs, and status tied to configurations.
- `users` – Accounts with roles and optional SSO subjects.
- `api_keys` – Issued API keys linked to users.
- `job_documents` – (Planned) join table linking jobs to the documents they consume or emit. Useful for future retention checks.
- `events` – Immutable history of ADE actions keyed by ULID with optional actor/source metadata and structured payloads.
- `maintenance_status` – Keyed JSON payloads for background maintenance loops (e.g. `automatic_document_purge` stores the last
  automatic purge summary returned by `/health`).
- **Max upload bytes** – Configurable request ceiling (default 25 MiB) enforced by `POST /documents`. Controlled via the
  `ADE_MAX_UPLOAD_BYTES` environment variable; exceeding the limit returns HTTP 413 with `error=document_too_large` plus the
  configured threshold in the response body.
- **Document retention defaults** – Uploads expire after the configured window (`ADE_DEFAULT_DOCUMENT_RETENTION_DAYS`,
  30 days by default). Callers may override a document's expiry during upload by setting the `expires_at` form field.

Back up the SQLite file alongside the `var/documents/` directory.

---

## Payload cheat sheets
```jsonc
// Health response with automatic purge summary (abbreviated)
{
  "status": "ok",
  "purge": {
    "status": "succeeded",
    "processed_count": 2,
    "bytes_reclaimed": 4096,
    "recorded_at": "2024-01-01T00:05:00+00:00",
    "interval_seconds": 3600
  }
}
```

```jsonc
// Configuration payload (abbreviated)
{
  "configuration": {
    "configuration_id": "cfg_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
    "document_type": "remittance",
    "version": 7,
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
  "configuration": 3,

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

```jsonc
// Document response (abbreviated)
{
  "document_id": "01J8Z0Z4YV6N9Q8XCN5P7Q2RSD",
  "original_filename": "remittance.pdf",
  "content_type": "application/pdf",
  "byte_size": 542118,
  "sha256": "sha256:bd5c3d9a6c5fe0d4f4a2c1b8e0f9db03a1376c64f071c7f1f0c7c6b8f019ab12",
  "stored_uri": "uploads/01J8Z0Z4YV6N9Q8XCN5P7Q2RSD",
  "metadata": {},
  "expires_at": "2025-10-17T18:42:00+00:00",
  "created_at": "2025-09-17T18:42:00+00:00",
  "updated_at": "2025-09-17T18:42:00+00:00"
}
```

```jsonc
// Event (document deleted)
{
  "event_id": "01JABCXY45MNE678PQRS012TU3",
  "event_type": "document.deleted",
  "entity_type": "document",
  "entity_id": "01J8Z0Z4YV6N9Q8XCN5P7Q2RSD",
  "occurred_at": "2024-08-02T17:25:14.123456+00:00",
  "actor_type": "user",
  "actor_label": "ops@ade.local",
  "source": "api",
  "payload": {
    "deleted_by": "ops@ade.local",
    "delete_reason": "cleanup",
    "byte_size": 542118,
    "stored_uri": "uploads/01J8Z0Z4YV6N9Q8XCN5P7Q2RSD",
    "sha256": "sha256:bd5c3d9a...",
    "expires_at": "2025-10-17T18:42:00+00:00"
  }
}
```

```jsonc
// Audit event (configuration activated)
{
  "event_type": "configuration.activated",
  "entity_type": "configuration",
  "entity_id": "01JCFG7890ABCDEFFEDCBA3210",
  "actor_label": "api",
  "source": "api",
  "payload": {
    "document_type": "invoice",
    "title": "Invoice v3",
    "version": 4,
    "is_active": true,
    "activated_at": "2025-01-10T08:01:12+00:00"
  }
}
```

```jsonc
// Audit event (job results published)
{
  "event_type": "job.results.published",
  "entity_type": "job",
  "entity_id": "job_2025_09_17_0001",
  "actor_label": "api",
  "payload": {
    "document_type": "remittance",
    "configuration_id": "01JCFG7890ABCDEFFEDCBA3210",
    "configuration_version": 4,
    "status": "completed",
    "outputs": {
      "json": {
        "uri": "var/outputs/remit_final.json",
        "expires_at": "2026-01-01T00:00:00Z"
      }
    },
    "metrics": {
      "rows_extracted": 125,
      "processing_time_ms": 4180,
      "errors": 0
    }
  }
}
```

---

## Working agreements
- Configurations flow draft → active → retired; activation only updates the live pointer.
- Always compare configurations before activating to understand behavioural changes.
- Jobs include the `configuration_id` so reruns remain deterministic.
- Profiles stay inside the configuration payload to avoid hidden configuration drift.
- Detection, transformation, validation, and header rules are pure functions (no I/O, deterministic results).
- Flag `needs_review: true` when validation fails or confidence dips below the configured threshold.
- Table boundaries on a page must not overlap.

---

This glossary is the naming authority for code, APIs, and UI copy.
