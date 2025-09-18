# Configuration revision lifecycle redesign

## Core goals

ADE's configuration control guarantees three promises:

1. **Deterministic jobs** – every job can be replayed with the exact configuration revision that produced it.
2. **Safe iteration** – operators can experiment without disturbing the active behaviour until they explicitly promote a new configuration revision.
3. **Observable history** – we can answer "what was live?" and "when did it change?" without digging through logs.

We call the executable bundle of logic for a document type a **configuration revision**. The current single-table design with a mutable `is_active` flag supports toggling, but it breaks determinism and obscures history because payloads mutate in place and jobs cannot prove which logic ran.

## Reference patterns from other systems

Mature configuration systems keep things simple:

- **Feature flag platforms** (LaunchDarkly, Optimizely) treat every change as a new immutable revision. They expose the latest revision by default while allowing explicit selection by revision number.
- **AWS AppConfig** issues sequential revisions and promotes one to the hosted slot. Previous revisions stay immutable and selectable for rollbacks.
- **Kubernetes ConfigMaps** and Helm releases roll forward only; a new manifest creates a new revision, and consumers pin to a particular revision if needed.

All of these solutions revolve around immutable revisions, a monotonic counter per document type, and a single pointer to the active revision. ADE can adopt the same approach without inventing extra lifecycle stages.

## Proposed direction

### Domain model

Create a `configuration_revisions` table that stores immutable revisions of configuration logic:

| Column | Purpose |
| --- | --- |
| `configuration_revision_id` (ULID) | Stable identifier referenced by jobs. |
| `document_type` | Logical grouping (invoice, packing_slip, etc.). |
| `title` | Human-friendly name shown in the UI. |
| `revision_number` (int) | Sequential counter per `document_type`. |
| `is_active` (bool) | Flags the single active revision per document type. |
| `activated_at` | Populated when the revision becomes active. |
| `payload` (JSON) | Canonical configuration logic captured as JSON. |
| `created_at` / `updated_at` | Audit timestamps for creation and metadata edits. |

Add a companion `jobs` table that records execution runs using the active configuration revision. Each job captures:

- `job_id` following the `job_YYYY_MM_DD_####` pattern.
- `document_type`, `configuration_revision_id`, and `configuration_revision_number` for the logic that ran.
- Status lifecycle (`pending`, `running`, `completed`, `failed`) with `created_at`, `updated_at`, and `created_by` metadata.
- Structured JSON blobs for `input`, `outputs`, `metrics`, and `logs`, matching the canonical job JSON documented in the glossary.

Constraints keep the tables honest:

- Unique index on `(document_type, revision_number)` ensures we never reuse a revision number.
- Application logic enforces a single active configuration revision per document type by demoting others on activation.
- Jobs remain mutable only while `status` is `pending` or `running`; once marked `completed` or `failed`, records become immutable audit entries.

### Lifecycle

We only need three lifecycle steps:

```
draft -> active -> retired
  ^        |
  '--------'
```

- **Draft configuration revision** – working copy. Payload and metadata are editable. Duplicating an existing revision creates a new draft.
- **Active configuration revision** – the lone revision used for default jobs. Payload is immutable; metadata edits are limited to annotations (description, rollout notes).
- **Retired configuration revision** – frozen history for auditing and deterministic replays. Retiring the active revision occurs automatically when another revision is activated.

Publishing is a single operation: mark one draft as active, automatically demote the previous active configuration revision, and stamp the audit fields. Rolling back simply activates an older revision (which clones into a new draft first so the revision numbers keep increasing).

### Revision resolution and APIs

Resolver logic mirrors other configuration stores:

- `resolve_configuration_revision(document_type, revision_identifier)` returns the active configuration revision when `revision_identifier` is `None`.
- `invoice@7` fetches the invoice configuration revision with `revision_number = 7`.
- Supplying a ULID fetches the exact row.

Minimal API surface:

1. `POST /configuration-revisions` – create a draft (optionally cloning from another configuration revision).
2. `PATCH /configuration-revisions/{id}` – edit a draft.
3. `POST /configuration-revisions/{id}/activate` – promote a draft to active. Automatically demotes the previous active configuration revision.
4. `POST /configuration-revisions/{id}/retire` – move an active configuration revision to retired without activating a replacement (emergency stop).
5. `GET /configuration-revisions` – list configuration revisions filtered by document type and state.
6. `GET /configuration-revisions/{id}` – fetch a single configuration revision.
7. `GET /configuration-revisions/{document_type}/active` – convenience endpoint for the active configuration revision.

Lifecycle events (`revision_events`) remain optional but recommended for detailed auditing (state, actor, timestamp, optional notes). They mirror LaunchDarkly's event log or AWS AppConfig's deployment history.

### Data integrity and automation

- Store payloads as canonical JSON so change detection works reliably.
- Compute `revision_number` by selecting `max(revision_number) + 1` for the document type within the same transaction that inserts the new draft. SQLite serialization plus the unique constraint handles race protection.
- Require jobs to store both `configuration_revision_id` and `configuration_revision_number`. During replay we verify that the recorded revision still exists.
- Soft-delete drafts if necessary by introducing an `is_archived` flag instead of `DELETE` so historical references always resolve.

## Migration plan

1. **Database** – add `configuration_revisions` and `jobs`, keeping the legacy `snapshots` table during migration.
2. **Backfill** – copy each legacy snapshot into `configuration_revisions`. Assign revision numbers by ordering on `created_at`. Mark rows with `is_published = true` as active, others as draft.
3. **Dual writes** – update services to create a new immutable row on every publish while still updating the old table until consumers switch.
4. **Cutover** – flip reads to `configuration_revisions` and persist jobs alongside each run once confidence is high.
5. **Cleanup** – when no code references the old table, archive or drop it.

## Open questions

- Do we need a UI affordance for cloning retired revisions directly into drafts, or is a single "Activate previous revision" button enough?
- Should activation require approval (two-person rule) or can we log approval in `revision_events` later if needed?
- What retention policy do we need for drafts that never activate? Scheduled cleanup might be necessary to keep the table tidy.
- Should job logs be capped or paginated once very large runs are introduced?
