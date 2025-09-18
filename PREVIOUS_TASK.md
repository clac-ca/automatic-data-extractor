# Current Task — Document ingestion safeguards

## Goal
Add guardrails around document uploads so ADE rejects oversized files with clear errors and operators understand the retention
expectations for stored documents.

## Background
- The `/documents` API now persists uploads, deduplicates on SHA-256, and restores missing files, but it accepts arbitrarily large
  payloads.
- Operations teams need a configurable size ceiling to prevent runaway disk usage and to deliver predictable failure modes.
- Documentation already calls out the pending size-limit TODO; this task implements the limit and ensures the behaviour is tested
  and well communicated.

## Scope
- Introduce a configurable `max_upload_bytes` setting on the backend (default to a conservative value such as 25 MiB) and expose
  it via environment variables.
- Enforce the size limit in `POST /documents` while streaming uploads. Return HTTP 413 with a descriptive error body when the
  payload exceeds the configured cap.
- Cover the new behaviour with pytest cases (success within the limit, rejection when the limit is exceeded, and override via
  configuration).
- Update README, ADE_GLOSSARY.md, and AGENTS.md with the new setting, operational guidance, and the error semantics.
- Note any open follow-ups (e.g., retention policies or delete endpoints) that should be planned next.

## Deliverables
1. Backend configuration updates with a documented `max_upload_bytes` setting.
2. Service and route changes that reject oversized uploads with HTTP 413 while still deduplicating valid files.
3. Automated tests verifying the limit, configuration overrides, and error payloads.
4. Documentation updates describing the default cap, how to tune it, and the resulting API errors.

## Definition of done
- `/documents` rejects files larger than the configured limit with HTTP 413 and a helpful error message.
- Successful uploads under the cap continue to return canonical metadata and reuse stored files based on digest.
- The new configuration is covered in tests and documentation, and README/AGENTS no longer describe the size limit as TODO.
- `pytest -q` passes with the expanded document ingestion test suite.
