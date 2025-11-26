# Unify configuration identifier to primary key

## Background
- Configurations previously had both `id` (PK) and a separate `configuration_id`, leading to duplicated identifiers across models, routes, and storage.
- Decision: use the primary key as the sole configuration identifier everywhere (APIs, storage, runs/builds), with no backward compatibility or aliases.

## Scope and changes
- Schema/migration: removed the `configuration_id` column from `configurations`; builds and runs now FK directly to `configurations.id`; dropped redundant record/public ID columns across builds/runs; initial migration updated accordingly.
- Models/services: configuration model now only exposes `id`; build/run models, execution contexts, and repositories use that single ID; storage paths and build/run orchestration reference the primary key.
- Schemas/routers/tests: configuration payloads expose `id` (no duplicate `configuration_id` field); version serialization ties to the primary key; tests adjusted to use the unified identifier.

## Notes
- On-disk config/venv/run paths are now keyed by the configuration primary key; no migration/backfill performed by design.
- OpenAPI/types may be regenerated to reflect the new response shapes if clients rely on them.

## Validation
- `source .venv/bin/activate && ade test`
