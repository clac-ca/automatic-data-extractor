---
Audience: Support teams, Configuration managers
Goal: Describe ADE's configuration model, lifecycle states, and emitted events so teams can reason about revisions safely.
Prerequisites: Access to the ADE configuration UI (or API credentials for automation) and familiarity with the document types you manage.
When to use: Review before authoring, promoting, or auditing configuration revisions.
Validation: Compare concepts with `backend/app/routes/configurations.py` and `backend/app/schemas.py`; ensure glossary terms remain aligned.
Escalate to: Configuration governance lead when lifecycle assumptions change or new states are introduced.
---

# Configuration concepts

ADE stores every configuration as an immutable revision linked to a document type. Most teams interact with these revisions through the configuration UI, which wraps the FastAPI endpoints in `backend/app/routes/configurations.py` and the helper functions in `backend/app/services/configurations.py`. Understanding the underlying lifecycle keeps UI-driven changes predictable and helps automation match the same behaviour.

## Entities and identifiers

- **Configuration** — Immutable JSON payload plus metadata (`configuration_id`, `document_type`, `title`, `version`, `is_active`, `activated_at`, timestamps).
- **Job** — Execution record referencing `configuration_id` and `configuration_version` alongside document metadata. Jobs ensure results can be replayed deterministically.
- **Events** — `configuration.created`, `configuration.updated`, and `configuration.activated` emitted via `backend/app/services/events.py` for every mutation. Use `/configurations/{configuration_id}/events` to inspect history.

## Lifecycle states

ADE supports three explicit states:

```
draft -> active -> retired
  ^        |
  '--------'
```

- **Draft** — Editable revision created via `POST /configurations`. Use for experimentation or staged changes.
- **Active** — Single revision per document type marked with `is_active=true`. Activation happens through `PATCH /configurations/{id}`.
- **Retired** — Any previously active revision automatically transitions to retired when a new active revision is selected. Retired revisions remain immutable for audit purposes.

## Versioning rules

- Versions increment monotonically per `document_type` (see `Configuration.version` in the ORM model).
- `(document_type, version)` is unique. Attempting to activate another revision automatically demotes the prior active row.
- Jobs store both the ULID and version number to guarantee replay correctness even if metadata changes.

## Event families

Events recorded through `backend/app/services/events.py` capture:

- `configuration.created` — Fired on `POST /configurations`; includes document type, version, and title.
- `configuration.updated` — Emitted when metadata or payload fields change via `PATCH`.
- `configuration.activated` — Occurs when a revision becomes active. Includes actor, source, and request metadata.

Use these events with the `/events` feed or the per-entity timeline to audit rollouts and answer "what was live when?".

## Related APIs

- `POST /configurations` — Create drafts or active revisions (`ConfigurationCreate`).
- `GET /configurations/active/{document_type}` — Resolve the default revision used for new jobs.
- `PATCH /configurations/{configuration_id}` — Update metadata, payloads, or activation state (`ConfigurationUpdate`).
- `DELETE /configurations/{configuration_id}` — Remove unused drafts (active revisions cannot be deleted).

Refer to [Publishing and rollback](./publishing-and-rollback.md) for task-focused steps on activating or reverting revisions.
