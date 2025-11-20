# ADE engine integration assessment

> Agents: review the checklist below before starting work, keep it current as you progress, and append any newly discovered tasks to this assessment work package.

## Current integration map
- **Configuration lifecycle surface.** Config records track only three statuses (draft/active/inactive) and the service exposes create/clone, validate, activate, and deactivate operations without a publish/freeze step for drafts, so new configs never become selectable versions until activation succeeds.【F:apps/ade-api/src/ade_api/features/configs/models.py†L17-L57】【F:apps/ade-api/src/ade_api/features/configs/service.py†L72-L189】
- **Run creation and engine invocation.** Run requests persist sheet selections, resolve the active config build, and enqueue an execution context before streaming events back to callers; the backend stages the selected document into the job directory and invokes `python -m ade_engine` inside the config's venv via `ADEProcessRunner`.【F:apps/ade-api/src/ade_api/features/runs/service.py†L170-L224】【F:apps/ade-api/src/ade_api/features/runs/service.py†L500-L548】
- **Input ingestion inside the engine.** The worker injects any worksheet overrides from `ADE_RUN_INPUT_SHEET(S)` into the job metadata, and the extractor raises when the job input folder is empty while iterating CSV/XLSX files and honoring the requested sheet list.【F:apps/ade-engine/src/ade_engine/job_service.py†L66-L110】【F:apps/ade-engine/src/ade_engine/pipeline/extract.py†L29-L53】
- **Workspace documents & worksheet discovery.** The documents service inspects XLSX uploads on demand (otherwise returning a single synthetic sheet) and the run dialogs rely on `/documents/{document_id}/sheets` to populate worksheet selectors.【F:apps/ade-api/src/ade_api/features/documents/service.py†L146-L189】【F:apps/ade-web/src/shared/documents.ts†L1-L18】
- **Workspace jobs piggyback on runs.** Job submissions copy the chosen document into a job-scoped `input/` folder, trigger a run, and later reconcile job status, artifacts, and outputs from the completed run records.【F:apps/ade-api/src/ade_api/features/jobs/service.py†L211-L276】【F:apps/ade-api/src/ade_api/features/jobs/service.py†L292-L320】

## Gaps and remaining work

### 1) Config lifecycle stops at drafts
New configs are created as drafts, but there is no publish/freeze path short of full activation. That leaves no way to promote draft content for testing or selection without making it the active version, and drafts never surface in the run pickers.
- [x] Add an explicit publish step that snapshots draft contents into a selectable version without forcing immediate activation; ensure version identifiers are persisted for downstream runs/jobs.
- [x] Extend the API and UI to list draft and published versions distinctly (e.g., promote, activate, deactivate) so operators can stage changes safely.
- [x] Gate activation on a published artifact to reduce drift between what was validated and what is running.

### 2) Document Run dialog hides drafts and defaults to “No configurations”
The Documents run drawer filters out any config lacking an `active_version`, so workspaces with only drafts see an empty picker and the informational “No configurations available” alert instead of being allowed to select drafts or override with an alternate build.【F:apps/ade-web/src/screens/Workspace/sections/Documents/index.tsx†L1391-L1419】【F:apps/ade-web/src/screens/Workspace/sections/Documents/index.tsx†L1640-L1679】
- [ ] Surface draft/published configs in the Documents run selector with clear labeling, defaulting to the active build when present but still enabling draft overrides.
- [ ] Persist the selected config and version (including drafts) in run preferences so repeat runs stay consistent.
- [ ] Ensure the backend accepts draft version identifiers and enforces guardrails (e.g., block stale drafts if a newer publish exists).

### 3) Advanced options fail to load worksheet metadata
Both Config Builder and Document run experiences depend on `/documents/{document_id}/sheets`; missing or unreadable files raise 404s, which bubble up as “Unable to load worksheet metadata” with no retry or fallback, leaving the advanced worksheet picker empty.【F:apps/ade-api/src/ade_api/features/documents/service.py†L146-L189】【F:apps/ade-web/src/screens/Workspace/sections/Documents/index.tsx†L1762-L1812】
- [x] Cache worksheet metadata at upload time and serve a persisted snapshot when live inspection fails, including for non-XLSX inputs.
- [x] Add graceful fallbacks in the frontend (e.g., show “All worksheets” with a retry control) and log the underlying error for diagnostics.
- [x] Emit clearer API errors that distinguish “file missing” vs. “workbook parse failure,” enabling UX-specific guidance.
- [x] Mirror the worksheet retry/fallback flow in the Config Builder run dialog so extraction can proceed even when metadata lookup fails.

### 4) Runs can be launched with no staged inputs
`RunCreateOptions` allows requests without `input_document_id`, but the engine raises “No input files found” when the job directory lacks staged files. The backend does not block these cases upfront, leading to noisy failed runs and confusing UX.【F:apps/ade-api/src/ade_api/features/runs/schemas.py†L40-L83】【F:apps/ade-engine/src/ade_engine/pipeline/extract.py†L29-L32】
- [x] Require `input_document_id` for extraction runs (while allowing `validate_only` mode), and reject missing inputs with an explicit 400 from the runs API.
- [x] Validate the referenced document exists before enqueuing the run so staging cannot fail later with a missing file.
- [ ] Update the Config Builder and job submission flows to enforce the chosen rule (e.g., disable the Run button until a document is selected/staged).

### 5) Run/job orchestration remains duplicated and prone to drift
Both `RunsService` and `JobsService` independently stage documents and manage lifecycle metadata (status, outputs, timestamps). Jobs pull status from the linked run after execution, defaulting to success when the run record cannot be read, which can mask failures and complicate reasoning about the source of truth.【F:apps/ade-api/src/ade_api/features/runs/service.py†L565-L585】【F:apps/ade-api/src/ade_api/features/jobs/service.py†L236-L276】【F:apps/ade-api/src/ade_api/features/jobs/service.py†L292-L320】
- [x] Consolidate document staging into a single helper shared by both services to avoid divergent behavior (e.g., last_run_at updates, naming, error handling).
- [ ] Make the run the authoritative lifecycle record and have jobs reference it instead of re-deriving status and timestamps; emit explicit run status events to update job rows.
  - [x] Reconcile job completion fields directly from the linked run and fail jobs when the run record is missing instead of optimistically marking success.
  - [x] Push run status updates into job records as events arrive (instead of waiting for finalize-only reconciliation).
- [x] Simplify artifact/output URI handling so both run and job download paths derive from one canonical layout, reducing duplicated relative-path math.
