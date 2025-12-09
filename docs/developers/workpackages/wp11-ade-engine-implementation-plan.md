# WP11 — ADE Engine Runtime Implementation Plan

> **Agent instruction:** Keep this work package plan current as you execute WP11. Update statuses on the checklist below and add new items whenever additional work emerges.

## Work Package Checklist
- [x] Runtime foundations defined and context/dataclass scaffolding in place
- [x] Config import + hook wiring implemented
- [x] Input ingestion + table detection pipeline operational
- [x] Column mapping, transforms, and validation flow implemented
- [x] Output composition writes normalized workbooks atomically
- [x] Run lifecycle orchestration + error handling completed
- [x] Testing strategy executed with unit/integration/CLI coverage

### Progress Notes
- Worker runtime now loads column modules declared in manifest metadata, aggregates detector scores, applies transforms, validates rows, and records issues in artifacts/events while preserving unmapped columns.
- Run lifecycle orchestration finalised with atomic output writes, hook dispatch, and comprehensive tests spanning CLI invocation and worker scenarios.

## Purpose
The `ade_engine` package currently ships as a scaffold that only exposes package metadata and a manifest inspection CLI. To run
real runs we need a fully functional engine that can stream spreadsheet rows through detectors, transforms, validators, and
hooks defined in a tenant's `ade_config` package and produce normalized Excel outputs together with structured audit logs. This
plan summarizes the expected runtime responsibilities, establishes design constraints extracted from existing documentation, and
breaks the implementation into incremental, testable milestones.

## Scope & Constraints
- **Frozen execution environment:** Runs must execute inside the build-specific virtual environment referenced by the backend so results remain reproducible and isolated from other tenants.【F:docs/developers/02-build-venv.md†L7-L38】【F:docs/developers/workpackages/wp6-runs-integration.md†L7-L24】
- **Run directory contract:** All reads and writes are confined to the run's `input/`, `output/`, and `logs/` folders, with artifact and event writers persisting into `artifact.json` and `events.ndjson` respectively.【F:docs/developers/README.md†L100-L116】
- **Five-pass pipeline fidelity:** The runtime must follow the documented detection → mapping → transform → validate → output sequence so tooling and documentation stay aligned.【F:docs/developers/README.md†L126-L165】
- **CLI compatibility:** Maintain the manifest inspection mode for `python -m ade_engine` while adding a worker entry point consumable by the runs service; flag-breaking changes in advance.【F:docs/ade_runs_api_spec.md†L298-L355】

## Source Material Reviewed
- Developer overview of build/run lifecycle and config layout.【F:docs/developers/README.md†L1-L196】
- Build system contract describing how venvs host `ade_engine` + `ade_config` and how workers launch the engine.【F:docs/developers/02-build-venv.md†L1-L129】【F:docs/developers/02-build-venv.md†L180-L219】
- Runs integration expectations for invoking the engine per-run.【F:docs/developers/workpackages/wp6-runs-integration.md†L1-L25】
- Runs API specification noting the CLI entry point and streaming requirements.【F:docs/ade_runs_api_spec.md†L298-L537】

## Current State Snapshot
- Package exposes `EngineMetadata`, `load_config_manifest`, and a CLI that prints engine metadata + config manifest.【F:apps/ade-engine/src/ade_engine/__init__.py†L1-L20】【F:apps/ade-engine/src/ade_engine/__main__.py†L1-L60】
- No runtime abstractions exist for file ingestion, run orchestration, detector execution, or artifact logging.
- Tests only cover placeholder behaviors; no integration coverage for actual spreadsheet processing.

## High-Level Architecture Targets
1. **Deterministic, replayable runs** — Engine executes entirely within the frozen venv, consuming only run-specific inputs and writing outputs under the run directory.【F:docs/developers/README.md†L143-L183】
2. **Five-pass pipeline** — Table detection, column mapping, optional transforms, optional validations, and output generation mirror the conceptual flow documented for runs.【F:docs/developers/README.md†L118-L176】
3. **Hookable lifecycle** — Support for `ade_config` hooks (`on_run_start`, `after_mapping`, `before_save`, `on_run_end`) with well-defined context objects and safe artifact logging APIs.【F:docs/developers/README.md†L176-L199】
4. **Streaming-friendly logging** — Emit structured events (NDJSON) and maintain a human-readable artifact narrative to satisfy the runs API contract.【F:docs/ade_runs_api_spec.md†L298-L537】
5. **CLI/worker entry points** — Maintain `python -m ade_engine` for manifest inspection while introducing a worker module (e.g., `ade_engine.worker`) that can be invoked with `run_id` as WP6 envisions.【F:docs/developers/workpackages/wp6-runs-integration.md†L11-L19】

## External Dependencies & Integration Points
- **Backend run service:** Accepts `run_id`, resolves the active build, and invokes `ade_engine.worker`; coordinate CLI argument names (`--run-id`, `--runs-dir`, `--config-id`) and exit codes with WP6 owners.【F:docs/developers/workpackages/wp6-runs-integration.md†L7-L24】
- **Config packages:** Expect detectors, hooks, and manifests laid out per the documented `ade_config` structure; loader should gracefully surface import errors to operators.【F:docs/developers/README.md†L167-L218】
- **Environment variables:** Respect overrides for document, run, and venv directories plus worker resource limits so ops teams can tune deployments without code changes.【F:docs/developers/02-build-venv.md†L237-L254】
- **Runs API streaming:** Align event payload cadence and content with the runs service expectations for inline streaming and safe-mode invocations.【F:docs/ade_runs_api_spec.md†L298-L355】

## Proposed Implementation Milestones

### 1. Runtime Foundations
- Define configuration/data directories helper (resolve `ADE_*` env vars, default paths). Reuse logic from backend if available.
- Model core dataclasses: `RunContext`, `TableContext`, `ArtifactWriter`, `EventEmitter`.
- Implement artifact + event appenders that enforce atomic writes inside `runs/<run_id>/`.
- Establish manifest loading + validation utilities (extend `load_config_manifest` with schema guardrails if schemas exist).
- Expand CLI arguments to accept `--run-id` and `--runs-dir` once worker path is ready; keep backward-compatible manifest mode.

### 2. Config Import & Hook Wiring
- Implement loader that imports `ade_config` modules (detectors, hooks) from the installed package.
- Provide safe wrappers around user-defined callables (exception capture → artifact note + failure propagation).
- Define hook dispatcher invoked at pipeline milestones with structured context.
- Consider caching module references to avoid repeated import per sheet.

### 3. Input Ingestion & Table Detection
- Add readers for `.xlsx` (streaming `openpyxl`) and `.csv` (stdlib) as described in developer guide.【F:docs/developers/README.md†L211-L219】
- Implement row detector voting mechanism to identify header/data regions (likely calling `row_detectors.header`/`data`).
- Build table segmentation logic that yields candidate tables with metadata (sheet name, row ranges, confidence scores).

### 4. Column Mapping, Transforms, and Validation
- Define interface for column detectors returning mapping candidates per field.
- Aggregate scores, pick winning mappings, and record rationale in artifact for auditability.
- Support optional transform + validator functions per field; log successes/failures with context.
- Allow detectors to request derived columns or flag rejects; ensure consistent data model for downstream passes.

### 5. Output Composition
- Implement workbook writer using `openpyxl` in write-only mode to produce normalized Excel output.
- Support additional sheets (e.g., summary, rejects) as required by business rules; integrate `before_save` hook for customizations.
- Ensure output writes are atomic: write to temp file then atomically rename into `runs/<run_id>/output/`.

### 6. Run Lifecycle & Error Handling
- Provide top-level `run_run(run_id, *, runs_dir, safe_mode=False)` orchestrator.
- Execute hooks in order: `on_run_start` → pipeline per input file → `after_mapping`/`before_save`/`on_run_end`.
- Capture exceptions, emit failure events, and write terminal status to artifact; return non-zero exit code from CLI when fatal.
- Support safe-mode short-circuit (no subprocess) for backend tests per runs API spec.【F:docs/ade_runs_api_spec.md†L528-L537】

### 7. Testing Strategy
- Unit tests for manifest loader, artifact/event writers, hook dispatchers, detector adapters.
- Integration tests using a minimal fixture `ade_config` to validate end-to-end processing of sample CSV/XLSX files.
- CLI tests for `python -m ade_engine` manifest mode and future worker command.
- Contract tests to ensure logs + outputs align with expected file names/structures.

## Definition of Done
- Checklist at the top of this document reflects completed milestones with links to code and tests.
- Worker CLI can process a sample run end-to-end, producing normalized output and populated logs inside the run directory when invoked from the ensured venv.【F:docs/developers/workpackages/wp6-runs-integration.md†L11-L19】
- Runs API safe-mode path can execute the engine inline without spawning a subprocess, streaming structured events that match the spec examples.【F:docs/ade_runs_api_spec.md†L298-L355】
- Test suite covers happy paths and representative failure modes (manifest import failure, detector exception, hook crash) with artifact/event assertions.
- Operational runbook documents configuration knobs (`ADE_*` env vars, logging levels) referenced throughout this plan for operators and QA.【F:docs/developers/02-build-venv.md†L237-L254】

## Risks & Mitigations
- **Complex detector behaviors:** User-defined detectors may yield inconsistent shapes or raise errors. Mitigation: wrap detector execution with schema validation and artifact logging so failures are observable without corrupting downstream passes.【F:docs/developers/README.md†L173-L218】
- **File size & memory pressure:** Large workbooks can exhaust memory if loaded eagerly. Mitigation: rely on streaming readers (`openpyxl` read-only mode, chunked CSV) and enforce worker resource ceilings specified via env vars.【F:docs/developers/02-build-venv.md†L237-L254】
- **Logging backpressure:** High-frequency event emission could overwhelm the runs API stream. Mitigation: batch or throttle low-severity events, but flush immediately on state transitions to honor streaming contract.【F:docs/ade_runs_api_spec.md†L298-L355】
- **Hook side effects:** Hooks run arbitrary code and may mutate shared state unsafely. Mitigation: provide immutable context snapshots and document that long-running hooks should emit progress via artifact notes instead of blocking the pipeline.【F:docs/developers/README.md†L187-L199】

## Open Questions & Follow-Ups
- Do JSON Schemas exist for manifests/artifacts to validate against (`specs/` directory)? Evaluate reuse.
- Determine concurrency requirements (single-thread vs. multi-file) and whether streaming events should flush during processing.
- Clarify expected artifact schema (fields, severity levels) from runs spec before implementing writer.
- Coordinate with backend to agree on CLI arguments (run metadata path, config env) ahead of WP6 integration.

## Next Steps
1. Socialize this plan with backend + frontend owners to confirm pipeline scope and logging expectations.
2. Create follow-up work packages or GitHub issues for each milestone, ordering them by dependency.
3. Begin with runtime foundations to unblock backend integration tests while more advanced pipeline logic is designed.

## Retrospective & Future Refinements
- The current worker orchestration stitches together multiple responsibilities (loading config modules, coordinating pipeline
  passes, managing artifacts/events) inside a single module. With more time, I would extract clearer submodules (e.g.,
  `pipeline/table_detection.py`, `pipeline/transforms.py`, `logging/artifacts.py`) to make targeted changes safer and
  to reduce test fixture complexity.
- Detector/transform/validator registration leans on imperative manifest parsing. A more declarative registry or plugin system
  could simplify loading and enable better static validation before the runtime starts processing rows.
- Artifact and event writers are tightly coupled to on-disk NDJSON/JSON formats. Introducing an interface layer now would make
  it easier to redirect logs to other sinks (streaming sockets, cloud storage) without rewriting the worker core later.

### Potential Follow-Up Tasks
- [x] Break the worker module into focused pipeline stages with dedicated unit tests for each stage. (Implemented via `ade_engine.pipeline` package and new unit suites.)
- [x] Design a manifest-driven plugin registry that validates callable signatures during startup. (Added `ColumnRegistry` with strict signature checks.)
- [x] Abstract artifact/event sinks behind a provider interface to support alternate destinations. (Introduced sink protocols and file-backed provider.)

## Architecture Hindsight
- With the benefit of the refactor, I would have started with a pipeline state machine that encodes each pass and transition explicitly. That structure would have prevented early coupling between mapping, normalization, and output concerns and made retries/resume logic easier to bolt on.
- The column registry currently relies on manifest metadata for validation; investing in a shared schema (`specs/config-manifest.v2.json`) and generating Pydantic models would reduce runtime checks and push feedback to build time.
- Artifact/event logging could share a structured logging adapter so both streams inherit consistent severity levels and contextual metadata without duplicating formatting code.

### Follow-Up Tasks for Future Iterations
- [x] Prototype a pipeline state machine abstraction (`ade_engine.pipeline.state`) and migrate worker orchestration to it once stable.
- [x] Introduce shared schema-derived models for manifest validation and registry configuration, ensuring build-time enforcement before runs execute.
- [x] Align artifact/event writers on a shared structured logger that forwards to existing sinks while supporting future transports (e.g., streams, cloud storage).

## Architecture Hindsight (Round 2)
- In retrospect, the manifest context and state machine could both live behind a thin service boundary that exposes `prepare_run()`, `run_pass(pass_name)`, and `finalize_run()`. That separation would make it easier to stub behaviors in tests and let future orchestrators (e.g., async workers) reuse the same primitives.
- The pipeline still mixes domain decisions (e.g., mapping arbitration rules) with I/O mechanics. A domain services layer—fed by pure functions—would let us unit test decisions without standing up file fixtures.
- Our logging stack now supports structured events, but severity routing and correlation IDs are still ad-hoc. A centralized telemetry service could consistently attach run/build identifiers, unlock log-level tuning, and tee events to external aggregators without changing pipeline code.

### New Follow-Up Ideas
- [x] Extract a `RunService` module that wraps manifest loading, state machine initialization, and sink creation so `worker.run_run` only coordinates high-level flow.
- [x] Carve out pure mapping/normalization helpers that accept in-memory table representations and return deterministic results, leaving file readers/writers to the I/O layer.
- [x] Introduce a telemetry configuration object that standardizes correlation IDs, severity thresholds, and output sinks for both artifact and event writers.

Completed this iteration by introducing the `RunService` facade, isolating table processing into pure helpers, and implementing a configurable telemetry layer that unifies correlation metadata and severity thresholds across artifact and event sinks.

## Remaining Frontend & Backend Integration Work
- [x] Update the runs service to execute the new worker entry point by supplying `--run-id`/`--runs-dir` arguments (or calling `run_run` directly) so platform runs drive actual runs instead of invoking the legacy manifest-printing CLI. Align the subprocess environment with the run directory layout and safe-mode semantics exposed by the runtime.【F:apps/ade-api/src/ade_api/features/runs/service.py†L332-L427】【F:apps/ade-engine/src/ade_engine/__main__.py†L12-L88】
- [x] Replace the placeholder runs router/service with an implementation that persists submissions, provisions run folders, and associates runs with run metadata/artifacts that the frontend can display.【F:apps/ade-api/src/ade_api/features/runs/router.py†L1-L120】【F:apps/ade-api/src/ade_api/features/runs/service.py†L1-L272】
- [x] Ensure the workspace UI flows continue end-to-end once the backend endpoints exist: the documents drawer currently posts to `/runs` and expects a `RunRecord`, and validation mode streams run events over NDJSON, so both APIs must emit the shapes the SPA consumes.【F:apps/ade-web/src/screens/Workspace/sections/Documents/index.tsx†L626-L704】【F:apps/ade-web/src/shared/runs/api.ts†L1-L24】

## Architecture Hindsight (Round 3)
- In hindsight, the runs service and engine runtime each grew their own abstractions for manifests, telemetry, and filesystem layout. Establishing a shared domain package (or OpenAPI/JSON schema source) that both layers consume would reduce duplication and ensure the backend and engine evolve together instead of drifting.
- The NDJSON streaming contract works, but the runs service still orchestrates subprocess management, log forwarding, and run completion status manually. A background task runner (e.g., powered by Dramatiq or a simple asyncio supervisor) could own those responsibilities and free the API thread pool from long-lived streams.
- Frontend validation mode currently reads raw event payloads and builds UI state on the fly. Providing a typed event schema (and version negotiation) would harden the client against backend/runtime changes and clarify the supported telemetry timeline.

### Follow-Up Opportunities
- [x] Define a shared manifest + telemetry schema package that the backend, engine, and SPA can import to eliminate drift in run context structures. (Originally implemented via the shared `ade-schemas` package; schemas are now bundled with `ade_engine`.)
- [x] Prototype an asynchronous run runner abstraction for the API that supervises engine subprocesses, streams NDJSON over Server-Sent Events, and reconciles run status updates. (Added the `EngineSubprocessRunner` supervisor with telemetry-aware streaming.)
- [x] Extend the SPA's runs client to consume versioned telemetry envelopes, adding regression tests that guard the NDJSON parsing contract end-to-end. (Workspace console now renders telemetry frames with dedicated Vitest coverage.)

## Architecture Hindsight (Round 4)
- The new async runner still leaves the API service responsible for low-level process management. Standing up a dedicated runs orchestrator (e.g., a worker queue or supervisor service) would decouple HTTP lifecycle concerns from long-running ADE executions and simplify retries or cancellation.
- Schema alignment between the backend and SPA improved once schemas were centralized, but the engine still owns bespoke Pydantic models. Consolidating all schema generation into a single package (with codegen for Python and TypeScript) would ensure versioned compatibility across every layer.
- Telemetry envelopes are now versioned, yet our persistence strategy remains file-system–centric. Introducing a telemetry bus abstraction (writing to disk, SSE, or external collectors) could support richer analytics without rewriting the pipeline.

### Follow-Up Tasks Under Consideration
- [x] Evaluate introducing a lightweight run supervisor (e.g., Dramatiq/Arq) so the API enqueues runs and receives callbacks instead of directly awaiting subprocess completion.
- [x] Investigate generating engine-side models from the shared schema definitions to remove duplicate validation logic and guarantee parity with API/SPA consumers.
- [x] Prototype a pluggable telemetry sink interface that can forward envelopes to alternate transports (websocket, message bus) while retaining the current filesystem sink as the default.

Implemented a request-scoped run supervisor that streams ADE subprocess output through background tasks, refit the engine pipeline to consume typed manifest models while preserving dictionary-based `field_meta` for user code, and introduced pluggable telemetry sinks with factory loading and env-configurable dispatch so events can fan out beyond the default filesystem logs.

## Architecture Hindsight (Round 5)
- Wiring the supervisor directly into the FastAPI service gives us observability, but it still forces long-lived Python workers to share lifecycle with the API process. A dedicated run orchestration tier (or async task queue) would let us scale ADE execution separately and provide clearer back-pressure controls.
- Typed manifest models now span backend and engine code, yet the SPA still consumes manually curated TypeScript helpers. Generating typed client contracts from the shared schemas would reduce drift and keep console tooling aligned with runtime capabilities.
- Telemetry envelopes cover console streaming, but we still lack a unified persistence/analytics story. Routing envelopes through an intermediate event bus would enable opt-in storage (e.g., database, warehouse) and unlock historical reporting without scraping filesystem logs.

### Follow-Up Tasks For Future Consideration
- [ ] Prototype a standalone run orchestration service (or queue-backed worker) that the API enqueues into while the supervisor subscribes to progress events instead of spawning subprocesses inline.
- [ ] Extend the bundled schema source to emit TypeScript declarations (or JSON Schema) that the SPA can import directly, replacing bespoke telemetry/mapping view models.
- [ ] Experiment with a telemetry event bus that fans out envelopes to durable stores (database, object storage) and live consumers simultaneously, keeping filesystem sinks as a compatibility layer.
