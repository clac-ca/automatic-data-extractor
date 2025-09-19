# Configuration lifecycle redesign

## Core goals

ADE's configuration control guarantees three promises:

1. **Deterministic jobs** – every job can be replayed with the exact configuration version that produced it.
2. **Safe iteration** – operators can experiment without disturbing the active behaviour until they explicitly promote a new configuration version.
3. **Observable history** – we can answer "what was live?" and "when did it change?" without digging through logs.

We call the executable bundle of logic for a document type a **configuration**. Each configuration row represents an immutable version of that logic. The current single-table design with a mutable `is_active` flag supports toggling, but it breaks determinism and obscures history because payloads mutate in place and jobs cannot prove which logic ran.

## Reference patterns from other systems

Mature configuration systems keep things simple:

- **Feature flag platforms** (LaunchDarkly, Optimizely) treat every change as a new immutable version. They expose the latest version by default while allowing explicit selection by version number.
- **AWS AppConfig** issues sequential versions and promotes one to the hosted slot. Previous versions stay immutable and selectable for rollbacks.
- **Kubernetes ConfigMaps** and Helm releases roll forward only; a new manifest creates a new version, and consumers pin to a particular version if needed.

All of these solutions revolve around immutable versions, a monotonic counter per document type, and a single pointer to the active version. ADE can adopt the same approach without inventing extra lifecycle stages.

## Proposed direction

### Domain model

Create a `configurations` table that stores immutable versions of configuration logic:

| Column | Purpose |
| --- | --- |
| `configuration_id` (ULID) | Stable identifier referenced by jobs. |
| `document_type` | Logical grouping (invoice, packing_slip, etc.). |
| `title` | Human-friendly name shown in the UI. |
| `version` (int) | Sequential counter per `document_type`. |
| `is_active` (bool) | Flags the single active version per document type. |
| `activated_at` | Populated when the version becomes active. |
| `payload` (JSON) | Canonical configuration logic captured as JSON. |
| `created_at` / `updated_at` | Audit timestamps for creation and metadata edits. |

Add a companion `jobs` table that records execution runs using the active configuration version. Each job captures:

- `job_id` following the `job_YYYY_MM_DD_####` pattern.
- `document_type`, `configuration_id`, and `configuration_version` for the logic that ran.
- Status lifecycle (`pending`, `running`, `completed`, `failed`) with `created_at`, `updated_at`, and `created_by` metadata.
- Structured JSON blobs for `input`, `outputs`, `metrics`, and `logs`, matching the canonical job JSON documented in the glossary.

Constraints keep the tables honest:

- Unique index on `(document_type, version)` ensures we never reuse a version number.
- Application logic enforces a single active configuration version per document type by demoting others on activation.
- Jobs remain mutable only while `status` is `pending` or `running`; once marked `completed` or `failed`, records become immutable audit entries.

### Lifecycle

We only need three lifecycle steps:

```
draft -> active -> retired
  ^        |
  '--------'
```

- **Draft configuration version** – working copy. Payload and metadata are editable. Duplicating an existing version creates a new draft.
- **Active configuration version** – the lone version used for default jobs. Payload is immutable; metadata edits are limited to annotations (description, rollout notes).
- **Retired configuration version** – frozen history for auditing and deterministic replays. Retiring the active version occurs automatically when another version is activated.

Publishing is a single operation: mark one draft as active, automatically demote the previous active configuration version, and stamp the audit fields. Rolling back simply activates an older version (which clones into a new draft first so the version numbers keep increasing).

Every mutation records an immutable audit event:

- `configuration.created` captures the initial title, document type, and version.
- `configuration.updated` lists changed fields (title, payload, activation flag) whenever metadata shifts.
- `configuration.activated` fires when a revision becomes the active configuration for its document type.

Events include the actor label (`api`, `scheduler`, etc.) so operators can trace who promoted each revision.

### Configuration resolution and APIs

Resolver logic mirrors other configuration stores:

- `resolve_configuration(document_type, configuration_identifier)` returns the active configuration when `configuration_identifier` is `None`.
- `invoice@7` fetches the invoice configuration version with `version = 7`.
- Supplying a ULID fetches the exact row.

Current FastAPI routers expose:

1. `POST /configurations` – create a configuration (draft or immediately active).
2. `GET /configurations` – list configurations ordered by `created_at` descending.
3. `GET /configurations/{configuration_id}` – fetch a single configuration by ULID.
4. `GET /configurations/active/{document_type}` – resolve the active configuration for a document type.
5. `PATCH /configurations/{configuration_id}` – update metadata, payloads, and activation state while enforcing the single-active rule.
6. `DELETE /configurations/{configuration_id}` – remove unused configurations (draft clean-up).
7. `POST /jobs` – create a job bound to the active or explicitly requested configuration version.
8. `GET /jobs` – list jobs ordered by creation time.
9. `GET /jobs/{job_id}` – retrieve a single job record.
10. `PATCH /jobs/{job_id}` – update running jobs (`status`, `outputs`, `metrics`, `logs`). Completed or failed jobs return HTTP 409 on further updates.

These endpoints all emit the canonical job JSON documented in the glossary and README so downstream systems receive a uniform contract.

Future extensions may introduce dedicated activation or retirement endpoints instead of the current `PATCH` workflow, plus lifecycle event logs (`version_events`) for audit trails similar to LaunchDarkly or AWS AppConfig.

### Data integrity and automation

- Store payloads as canonical JSON so change detection works reliably.
- Compute `version` by selecting `max(version) + 1` for the document type within the same transaction that inserts the new draft. SQLite serialization plus the unique constraint handles race protection.
- Require jobs to store both `configuration_id` and `configuration_version`. During replay we verify that the recorded version still exists.
- Soft-delete drafts if necessary by introducing an `is_archived` flag instead of `DELETE` so historical references always resolve.

## Migration plan

1. **Database** – add `configurations` and `jobs`, keeping the legacy `snapshots` table during migration.
2. **Backfill** – copy each legacy snapshot into `configurations`. Assign version numbers by ordering on `created_at`. Mark rows with `is_published = true` as active, others as draft.
3. **Dual writes** – update services to create a new immutable row on every publish while still updating the old table until consumers switch.
4. **Cutover** – flip reads to `configurations` and persist jobs alongside each run once confidence is high.
5. **Cleanup** – when no code references the old table, archive or drop it.

## Open questions

- Do we need a UI affordance for cloning retired versions directly into drafts, or is a single "Activate previous version" button enough?
- Should activation require approval (two-person rule) or can we log approval in `version_events` later if needed?
- What retention policy do we need for drafts that never activate? Scheduled cleanup might be necessary to keep the table tidy.
- Should job logs be capped or paginated once very large runs are introduced?
