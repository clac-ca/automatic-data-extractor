> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## What we are fundamentally doing

We are simplifying runs to a single-file contract: each run consumes exactly one input document and produces one normalized output file (plus logs/events). We will remove multi-file flexibility, plural fields/endpoints, and output listings, aiming for the simplest consistent API/engine/frontend shape that matches this constraint.

---

## Work Package Checklist

* [x] Refactor backend run models/schemas to single input/output and update OpenAPI — flattened to `input_document_id`/`input_sheet_name`, `RunOutput.output_path`, `RunLinks.output`; removed listing schemas/endpoints and regenerated OpenAPI/types.
* [x] Update engine types/pipeline/telemetry to emit single output path + processed file — core RunResult/summary/emitter/CLI now expose `output_path`/`processed_file`; tests adjusted.
* [x] Simplify API surface and CLI/output endpoints to a single output file — removed `/runs/{id}/outputs*`, added singular download, run.complete artifacts emit `output_path` + `processed_file`.
* [x] Align frontend types, run state, and event formatting to singular fields — removed outputs listing query, updated run session/console formatting/UI to single output link and regenerated TS types.
* [ ] Refresh tests/fixtures and regenerate artifacts (OpenAPI/types, SPA if needed) — OpenAPI/TS types regenerated; remaining test runs pending.
* [x] Update docs/templates/CLI help to single-file wording — engine docs and default on_run_end hook updated to `output_path` language.

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Refactor backend run models/schemas to single input/output and update OpenAPI — <commit>`

---

# Single-File Run Contract

## 1. Objective

**Goal:**
Enforce that every run consumes exactly one input document (one workbook/file) and produces one normalized output file (plus logs/summary), removing multi-file abstractions and plural naming. A single workbook can still contain multiple sheets; by default we process all visible sheets unless a single sheet is explicitly selected.

You will:

* Collapse backend run request/response shapes to singular input/output fields and links
* Rework engine runtime and telemetry to return one output path/processed file
* Update frontend flows and formatting to the new singular contract

The result should:

* Make the API/engine contract unambiguous: one input, one normalized output
* Simplify UI state and telemetry handling without plural edge cases

---

## 2. Context (What you are starting from)

Runs currently allow plural inputs/outputs: `input_documents` arrays, `input_sheet_names`, `RunOutput.output_count`, `output_paths`, and `/runs/{id}/outputs` listings. The engine returns `output_paths`/`processed_files` tuples, and the CLI emits arrays. Frontend state and event formatters expect plural fields and load output listings.

Current state snapshot:

* Backend schemas/models: `RunCreateOptions` still exposes `document_ids`, `input_sheet_names`, and `RunLinks.outputs`/`RunOutput.output_count` (apps/ade-api/src/ade_api/features/runs/schemas.py). The DB model stores `input_documents` JSON + `input_sheet_names` (apps/ade-api/src/ade_api/core/models/run.py). RunCompletedPayload artifacts and RunPathsSnapshot carry `output_paths`, and the router/service expose `/runs/{id}/outputs` listing + download.
* Engine runtime: core types and pipeline emit `output_paths`/`processed_files` (apps/ade-engine/src/ade_engine/core/*), CLI run JSON prints `output_paths`, and event emitter + summary builder include list fields; tests assert list behavior.
* Frontend: run resources surface `output_count`/`processed_files` and `links.outputs`; shared API calls `/runs/{id}/outputs`, and workbench console formatting reads `artifacts.output_paths` to render output lists.
* Templates/docs: default config hook (apps/ade-api/src/ade_api/templates/config_packages/default/src/ade_config/hooks/on_run_end.py) and engine docs reference plural `output_paths`.
* Constraints: runs/live artifacts stay under `data/workspaces/<ws>/runs/<run_id>/`; event log streaming and summary payload semantics must be preserved while switching to singular output links.

---

## 3. Target architecture / structure (ideal)

One input document per run, optional single sheet selection (default: process all sheets in the workbook); engine writes one normalized workbook to a fixed path (`output/normalized.xlsx`); API returns a single `output_path` (and download link) plus logs/events paths; telemetry uses singular fields; frontend stores and renders a single output link.

```text
automatic-data-extractor/
  apps/
    ade-api/src/ade_api/features/runs/    # singular run schemas/service/router
    ade-engine/src/ade_engine/core/       # singular RunResult, pipeline, summary builder
    ade-web/src/shared/runs/              # singular run API/types
    ade-web/src/screens/Workspace/        # workbench/documents consume single output
  apps/ade-api/src/ade_api/openapi.json   # regenerated OpenAPI with singular fields
  apps/ade-web/src/generated-types/       # regenerated TS types
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* Clarity: single-file contract, consistent naming (output_path, processed_file)
* Maintainability: fewer code paths, remove listing logic and plural accumulators
* Safety/compatibility: defensive path validation preserved; clear failure messages when input is missing

### 4.2 Key components / modules

* Runs API/service (schemas, router, service paths) — enforce single input/output and links
* Engine core (RunRequest/RunResult, pipeline runner, summary builder, event emitter) — emit singular output/processed file
* Frontend run consumers (shared API, workbench/documents UI) — align state/rendering to singular output link

### 4.3 Key flows / pipelines

* Run creation → execution → completion: accept one `input_document_id`, stage one file, invoke engine, emit single `run.complete` artifacts with `output_path` and events path (workbook may contain multiple sheets; optional single-sheet selection is honored)
* Engine pipeline: process one input file (all visible sheets unless a sheet is specified), write one workbook at fixed path, emit telemetry/summary with singular fields
* Frontend display: render one output download link (from `output_path` or link), no output listing fetch

### 4.4 Open questions / decisions

* Fixed output filename/path? **Decision:** Yes, write to `output/normalized.xlsx` under the run directory and surface as `output_path`.
* Keep single `input_sheet_name` plus optional list? **Decision:** Support a single optional `input_sheet_name`; drop `input_sheet_names` array.
* Keep `/runs/{id}/outputs` listing? **Decision:** Remove listing; expose direct download link via `RunLinks.output` and `output_path`.

> **Agent instruction:**
> If you answer a question or make a design decision, replace the placeholder with the final decision and (optionally) a brief rationale.

---

## 5. Implementation & notes for agents

* Update DB model/migration to drop `input_documents` and plural sheet/output fields; adjust repository filters accordingly and ensure RunLinks/RunOutput expose `output_path` + download link instead of counts/lists.
* Collapse RunPathsSnapshot + RunCompletedPayload to `output_path`/`processed_file`; drop `/runs/{id}/outputs` listing in router/service and replace with a single download resolver with path traversal guards.
* Adjust CLI JSON payload keys and any consumers/tests to surface a single output path/processed file.
* Regenerate OpenAPI (`ade openapi-types`) and, if needed, rebuild SPA (`ade build`); update engine docs and template hooks to match single-output wording.
* Update frontend tests/fixtures and remove output listing query logic; ensure event formatter uses singular artifact fields.
* Keep path validation to prevent traversal when resolving the single output download.

---

## Stages / Execution Plan

- [x] Discovery — reviewed current codepaths; context section notes remaining plural fields/endpoints across backend/engine/frontend/docs.

- [x] Backend contract — schemas/router/service/migrations now singular (input/output fields, single output link, listing removed, OpenAPI regenerated).
  - [x] Update run DB model/migration: remove `input_documents`, collapse sheet fields to `input_sheet_name`.
  - [x] Simplify run schemas/resources to singular `input_document_id`, `input_sheet_name`, `output_path`, `processed_file`; adjust links to a single `output`.
  - [x] Modify run service/router to stage one file, resolve a fixed output path, drop output listings, and regenerate OpenAPI.

- [x] Engine runtime — RunResult/output_paths + CLI/event payloads converted to singular fields.
  - [x] Change `RunResult`/telemetry to singular fields, adjust CLI JSON output, and pipeline runner return types.
  - [x] Update summary builder and event emitter payloads to accept `output_path`/`processed_file`.
  - [x] Fix engine tests and sample hooks to new shapes.

- [x] Frontend alignment — shared API + workbench consume single output link.
  - [x] Regenerate TS types; update shared run API to new links/fields (no listing call).
  - [x] Simplify workbench and documents UI state/rendering to a single output link; update console formatter to singular artifact fields.
  - [ ] Adjust frontend tests/fixtures to match singular contract.

- [x] Docs & templates — engine docs and default config hooks reference `output_path`.
  - [x] Rewrite engine docs/README snippets to single `output_path` + download link.
  - [x] Update config template hooks (on_run_end) and CLI help/examples to the new contract.

- [ ] Finalization
  - [ ] Run targeted backend/engine/frontend tests.
  - [x] Re-run `ade openapi-types`; `ade build` still pending if static assets are needed.
