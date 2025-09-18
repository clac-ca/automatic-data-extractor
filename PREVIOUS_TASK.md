# Previous Task — Configuration revisions and jobs

## Goal
Finish unifying ADE around the Configuration → Configuration Revision → Job vocabulary. Every API, database table, service helper, UI surface, and document should describe runs as jobs that execute the active configuration revision for a document type.

## Background
- Configuration revisions already store immutable detection, transformation, and metadata payloads per document type with revision sequencing and activation flags.
- Legacy wording referenced checkpoints and snapshots even though jobs now represent the auditable execution record that captures inputs, outputs, metrics, and logs.
- Job payloads must present a consistent JSON shape so downstream tooling, UI pages, and auditors receive the same structure everywhere.

## Scope
- Align service helpers, FastAPI routes, and schema models so job creation, updates, and retrieval follow the standard JSON contract (IDs, timestamps, status, input/output metadata, metrics, logs).
- Ensure configuration revision helpers, routes, and documentation speak in terms of `document_type` and `configuration_revision` instead of `configuration_name` or generic “versions.”
- Replace lingering “checkpoint” or “snapshot” terminology in documentation, planning files, and comments with the Job language.
- Keep glossary, README, and AGENTS aligned with the new naming so the terminology is unambiguous for future contributors.

## Deliverables
1. Service-layer utilities that enforce the single active configuration revision per document type, resolve revisions correctly, and produce sequential job identifiers.
2. FastAPI routers mounted at `/configuration-revisions` and `/jobs` exposing the normalized payloads described in the glossary.
3. Pytest coverage that proves revision sequencing, activation behaviour, job lifecycle updates, and immutable completed jobs.
4. Documentation updates (README, ADE_GLOSSARY.md, AGENTS.md, configuration revision lifecycle doc, planning files) that consistently use Configuration / Configuration Revision / Job terminology and include the canonical job JSON example.

## Definition of done
- `uvicorn backend.app.main:app --reload` boots, creating `configuration_revisions` and `jobs` tables in SQLite with the expected columns.
- Creating a job without specifying a revision binds to the active configuration revision for that document type, and job identifiers follow the `job_YYYY_MM_DD_####` format.
- Updating a job after it finishes returns HTTP 409 and leaves persisted output/metric/log records intact.
- `pytest -q` passes with the updated configuration revision and job tests.
- Glossary, README, AGENTS, and other docs refer to configurations, configuration revisions, active revisions, and jobs instead of schemas, specs, rule sets, snapshots, or checkpoints.
