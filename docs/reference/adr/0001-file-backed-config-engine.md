# ADR 0001 — File-backed Configuration Engine

**Status:** Accepted  
**Date:** 2024-05-28

## Context

The original configuration system stored drafts, versions, and scripts inside
the database. Each API call stitched together metadata, inline source files,
and runtime secrets. This approach proved difficult to reason about, expensive
to migrate, and fragile when provisioning new environments. Jobs needed to pull
large blobs from SQLite, decrypt secrets in-process, and rebuild module
packages before every execution.

## Decision

ADE v0.5 replaces the database-centric design with a deterministic,
file-backed configuration engine. Every configuration now lives under
`data/configs/<config_id>/` alongside a manifest, hook scripts, and one Python
module per canonical output column. Metadata (title, status, ownership, hashes)
remains in the database, but behaviour ships exclusively through the filesystem
bundle.

Key traits:

- **Single active config per workspace.** The database enforces at most one
  `active` configuration while allowing `inactive` edits and `archived`
  snapshots.
- **Explicit script APIs.** Hook modules expose keyword-only `run(...)`
  functions, while column modules offer multiple `detect_*` heuristics and a
  single `transform(...)` implementation.
- **Sandboxed execution.** Jobs run hooks and column modules in isolated
  subprocesses with hardened environment variables, per-call timeouts, and
  optional network access.
- **Deterministic packaging.** Import/export and cloning are simple
  directory/zipped copies. Validation inspects manifests, scripts, and
  quick dry-runs before activation.
- **Secret handling.** Manifest secrets stay encrypted at rest via
  AES-256-GCM/HKDF using `ADE_SECRET_KEY`; plaintext is injected only in the
  sandboxed child process.

## Consequences

- Config authors work against real files instead of opaque database blobs,
  making changes auditable via Git, zip bundles, or local file edits.
- API routes cover manifest editing, file mutations, cloning, import/export,
  validation, activation, and per-config secret management.
- Jobs resolve the active configuration once per run, execute the
  detect→assign→transform pipeline, and surface warnings alongside output data.
- The legacy configuration package has been removed; runtime paths now resolve
  exclusively to the file-backed engine.

## Rollout Plan

1. Retire the legacy configuration package and remove remaining references.
2. Introduce new SQLAlchemy models, Alembic migrations, and filesystem helpers.
3. Ship the new Config service and router alongside updated job flows.
4. Update documentation, tests, and templates to reflect the v0.5 manifest and
   pipeline semantics.
5. Migrate existing workspaces by exporting legacy configs, importing them into
   the file-backed engine, and validating before activation.

## Rollback Strategy

- Retain exports of legacy configuration data until the migration completes.
- Toggle the workspace `active_config_id` pointer back to the archived legacy
  configuration if critical regressions surface.
- Restore the database from pre-migration backups and redeploy the v0.4 code
  if a full rollback is required.

## References

- [`backend/app/features/configs`](../../backend/app/features/configs) for the
  implementation.
- [`backend/tests/api/configs`](../../backend/tests/api/configs) for API
  coverage.
