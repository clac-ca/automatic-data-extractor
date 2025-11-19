# ADE schema placement update

## What now ships with `ade_engine`
- Manifest Pydantic models (`ManifestV1`, `ManifestContext`, etc.) remain intact and mirror the `manifest.v1` JSON schema while exposing helpers such as `column_order`, `column_meta`, and defaults/writer accessors.【F:apps/ade-engine/src/ade_engine/schemas/manifest.py†L11-L188】
- Telemetry envelope and event models enforce the shared schema tag, alias field names (`timestamp` → `emitted_at`), and emit compact JSON payloads.【F:apps/ade-engine/src/ade_engine/schemas/telemetry.py†L10-L48】
- The manifest and telemetry JSON schemas are bundled as package data so `importlib.resources` can load them at runtime.【F:apps/ade-engine/src/ade_engine/schemas/manifest.v1.schema.json†L1-L171】【F:apps/ade-engine/src/ade_engine/schemas/telemetry.event.v1.schema.json†L1-L83】【F:apps/ade-engine/pyproject.toml†L17-L28】

## Current consumers
- **Engine (primary user):** Validates manifests using the bundled JSON schema, converts them to `ManifestV1`, and wraps raw data in `ManifestContext` for downstream pipeline helpers.【F:apps/ade-engine/src/ade_engine/runtime.py†L10-L98】 Telemetry sinks build `TelemetryEvent`/`TelemetryEnvelope` objects for every emitted job event.【F:apps/ade-engine/src/ade_engine/sinks.py†L10-L142】
- **API:** Streams engine telemetry; `RunStreamFrame` is a union of run lifecycle events plus `TelemetryEnvelope`, and the router serializes the envelope with model aliases when streaming NDJSON.【F:apps/ade-api/src/ade_api/features/runs/service.py†L14-L188】【F:apps/ade-api/src/ade_api/features/runs/router.py†L9-L115】 The API now depends on `ade-engine` instead of the removed `ade-schemas` package.【F:apps/ade-api/pyproject.toml†L14-L35】
- **Frontend:** Imports the telemetry JSON schema directly from the engine package to derive the canonical schema string and TypeScript shape for streamed events.【F:apps/ade-web/src/schema/adeTelemetry.ts†L1-L21】

## Rationale and follow-ups
- Co-locating schemas with the engine makes the runtime the single source of truth while still letting downstream services consume the telemetry envelope without bespoke packaging.
- With `ade-schemas` retired, developer setup and Docker images install only `ade-engine` and `ade-api`, removing one editable install step.【F:infra/docker/api.Dockerfile†L1-L34】【F:setup.sh†L1-L14】【F:README.md†L117-L167】
- Future improvement: generate OpenAPI/TypeScript types from the bundled schema files so the SPA can stop relying on hand-written envelope interfaces.
