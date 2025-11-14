# WP11 — ADE Engine Runtime Implementation Plan

> **Agent instruction:** Keep this work package plan current as you execute WP11. Update statuses on the checklist below and add new items whenever additional work emerges.

## Work Package Checklist
- [x] Runtime foundations defined and context/dataclass scaffolding in place
- [x] Config import + hook wiring implemented
- [x] Input ingestion + table detection pipeline operational
- [x] Column mapping, transforms, and validation flow implemented
- [x] Output composition writes normalized workbooks atomically
- [x] Job lifecycle orchestration + error handling completed
- [x] Testing strategy executed with unit/integration/CLI coverage

### Progress Notes
- Worker runtime now loads column modules declared in manifest metadata, aggregates detector scores, applies transforms, validates rows, and records issues in artifacts/events while preserving unmapped columns.
- Job lifecycle orchestration finalised with atomic output writes, hook dispatch, and comprehensive tests spanning CLI invocation and worker scenarios.

## Purpose
The `ade_engine` package currently ships as a scaffold that only exposes package metadata and a manifest inspection CLI. To run
real jobs we need a fully functional engine that can stream spreadsheet rows through detectors, transforms, validators, and
hooks defined in a tenant's `ade_config` package and produce normalized Excel outputs together with structured audit logs. This
plan summarizes the expected runtime responsibilities, establishes design constraints extracted from existing documentation, and
breaks the implementation into incremental, testable milestones.

## Scope & Constraints
- **Frozen execution environment:** Jobs must execute inside the build-specific virtual environment referenced by the backend so results remain reproducible and isolated from other tenants.【F:docs/developers/02-build-venv.md†L7-L38】【F:docs/developers/workpackages/wp6-jobs-integration.md†L7-L24】
- **Job directory contract:** All reads and writes are confined to the job's `input/`, `output/`, and `logs/` folders, with artifact and event writers persisting into `artifact.json` and `events.ndjson` respectively.【F:docs/developers/README.md†L100-L116】
- **Five-pass pipeline fidelity:** The runtime must follow the documented detection → mapping → transform → validate → output sequence so tooling and documentation stay aligned.【F:docs/developers/README.md†L126-L165】
- **CLI compatibility:** Maintain the manifest inspection mode for `python -m ade_engine` while adding a worker entry point consumable by the runs service; flag-breaking changes in advance.【F:docs/ade_runs_api_spec.md†L298-L355】

## Source Material Reviewed
- Developer overview of build/run lifecycle and config layout.【F:docs/developers/README.md†L1-L196】
- Build system contract describing how venvs host `ade_engine` + `ade_config` and how workers launch the engine.【F:docs/developers/02-build-venv.md†L1-L129】【F:docs/developers/02-build-venv.md†L180-L219】
- Jobs integration expectations for invoking the engine per-job.【F:docs/developers/workpackages/wp6-jobs-integration.md†L1-L25】
- Runs API specification noting the CLI entry point and streaming requirements.【F:docs/ade_runs_api_spec.md†L298-L537】

## Current State Snapshot
- Package exposes `EngineMetadata`, `load_config_manifest`, and a CLI that prints engine metadata + config manifest.【F:packages/ade-engine/src/ade_engine/__init__.py†L1-L20】【F:packages/ade-engine/src/ade_engine/__main__.py†L1-L60】
- No runtime abstractions exist for file ingestion, job orchestration, detector execution, or artifact logging.
- Tests only cover placeholder behaviors; no integration coverage for actual spreadsheet processing.

## High-Level Architecture Targets
1. **Deterministic, replayable runs** — Engine executes entirely within the frozen venv, consuming only job-specific inputs and writing outputs under the job directory.【F:docs/developers/README.md†L143-L183】
2. **Five-pass pipeline** — Table detection, column mapping, optional transforms, optional validations, and output generation mirror the conceptual flow documented for jobs.【F:docs/developers/README.md†L118-L176】
3. **Hookable lifecycle** — Support for `ade_config` hooks (`on_job_start`, `after_mapping`, `before_save`, `on_job_end`) with well-defined context objects and safe artifact logging APIs.【F:docs/developers/README.md†L176-L199】
4. **Streaming-friendly logging** — Emit structured events (NDJSON) and maintain a human-readable artifact narrative to satisfy the runs API contract.【F:docs/ade_runs_api_spec.md†L298-L537】
5. **CLI/worker entry points** — Maintain `python -m ade_engine` for manifest inspection while introducing a worker module (e.g., `ade_engine.worker`) that can be invoked with `job_id` as WP6 envisions.【F:docs/developers/workpackages/wp6-jobs-integration.md†L11-L19】

## External Dependencies & Integration Points
- **Backend job service:** Accepts `job_id`, resolves the active build, and invokes `ade_engine.worker`; coordinate CLI argument names (`--job-id`, `--jobs-dir`, `--config-id`) and exit codes with WP6 owners.【F:docs/developers/workpackages/wp6-jobs-integration.md†L7-L24】
- **Config packages:** Expect detectors, hooks, and manifests laid out per the documented `ade_config` structure; loader should gracefully surface import errors to operators.【F:docs/developers/README.md†L167-L218】
- **Environment variables:** Respect overrides for document, job, and venv directories plus worker resource limits so ops teams can tune deployments without code changes.【F:docs/developers/02-build-venv.md†L237-L254】
- **Runs API streaming:** Align event payload cadence and content with the runs service expectations for inline streaming and safe-mode invocations.【F:docs/ade_runs_api_spec.md†L298-L355】

## Proposed Implementation Milestones

### 1. Runtime Foundations
- Define configuration/data directories helper (resolve `ADE_*` env vars, default paths). Reuse logic from backend if available.
- Model core dataclasses: `JobContext`, `TableContext`, `ArtifactWriter`, `EventLogger`.
- Implement artifact + event appenders that enforce atomic writes inside `jobs/<job_id>/`.
- Establish manifest loading + validation utilities (extend `load_config_manifest` with schema guardrails if schemas exist).
- Expand CLI arguments to accept `--job-id` and `--jobs-dir` once worker path is ready; keep backward-compatible manifest mode.

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
- Ensure output writes are atomic: write to temp file then atomically rename into `jobs/<job_id>/output/`.

### 6. Job Lifecycle & Error Handling
- Provide top-level `run_job(job_id, *, jobs_dir, safe_mode=False)` orchestrator.
- Execute hooks in order: `on_job_start` → pipeline per input file → `after_mapping`/`before_save`/`on_job_end`.
- Capture exceptions, emit failure events, and write terminal status to artifact; return non-zero exit code from CLI when fatal.
- Support safe-mode short-circuit (no subprocess) for backend tests per runs API spec.【F:docs/ade_runs_api_spec.md†L528-L537】

### 7. Testing Strategy
- Unit tests for manifest loader, artifact/event writers, hook dispatchers, detector adapters.
- Integration tests using a minimal fixture `ade_config` to validate end-to-end processing of sample CSV/XLSX files.
- CLI tests for `python -m ade_engine` manifest mode and future worker command.
- Contract tests to ensure logs + outputs align with expected file names/structures.

## Definition of Done
- Checklist at the top of this document reflects completed milestones with links to code and tests.
- Worker CLI can process a sample job end-to-end, producing normalized output and populated logs inside the job directory when invoked from the ensured venv.【F:docs/developers/workpackages/wp6-jobs-integration.md†L11-L19】
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
- Coordinate with backend to agree on CLI arguments (job metadata path, config env) ahead of WP6 integration.

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
- [x] Introduce shared schema-derived models for manifest validation and registry configuration, ensuring build-time enforcement before jobs execute.
- [x] Align artifact/event writers on a shared structured logger that forwards to existing sinks while supporting future transports (e.g., streams, cloud storage).

## Architecture Hindsight (Round 2)
- In retrospect, the manifest context and state machine could both live behind a thin service boundary that exposes `prepare_job()`, `run_pass(pass_name)`, and `finalize_job()`. That separation would make it easier to stub behaviors in tests and let future orchestrators (e.g., async workers) reuse the same primitives.
- The pipeline still mixes domain decisions (e.g., mapping arbitration rules) with I/O mechanics. A domain services layer—fed by pure functions—would let us unit test decisions without standing up file fixtures.
- Our logging stack now supports structured events, but severity routing and correlation IDs are still ad-hoc. A centralized telemetry service could consistently attach job/build identifiers, unlock log-level tuning, and tee events to external aggregators without changing pipeline code.

### New Follow-Up Ideas
- [x] Extract a `JobService` module that wraps manifest loading, state machine initialization, and sink creation so `worker.run_job` only coordinates high-level flow.
- [x] Carve out pure mapping/normalization helpers that accept in-memory table representations and return deterministic results, leaving file readers/writers to the I/O layer.
- [x] Introduce a telemetry configuration object that standardizes correlation IDs, severity thresholds, and output sinks for both artifact and event writers.

Completed this iteration by introducing the `JobService` facade, isolating table processing into pure helpers, and implementing a configurable telemetry layer that unifies correlation metadata and severity thresholds across artifact and event sinks.
