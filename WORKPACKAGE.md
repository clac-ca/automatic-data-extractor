# Note for agents: keep this workpackage updated as you go (check items off, add new ones if needed, and record decisions/risks).

## Objective
Design and scaffold the unified Environment / Validation / Run activity experience in the Config Builder workbench (apps/ade-web), aligning with the “activity timeline + preflight” concept.

## Checklist
- [x] Define shared activity model and reducer in `Workbench.tsx` (dedicated hook/state):
  - [x] Activity types (`build`, `validation`, `extraction`), status enum, metadata (digests, document/sheets, counts), logs, validation issues.
  - [x] Actions for start, log append, issue append, status updates, completion, selection.
- [x] Wire streams into the activity model:
  - [x] Build stream (`@shared/builds/api`) → activity start/update/complete with reuse/fresh metadata and errors.
  - [x] Validation (run stream + `useValidateConfigurationMutation`) → activity with incremental issue ingestion.
  - [x] Extraction run stream (`@shared/runs/api`) → activity with document/sheet metadata, outputs, errors.
- [x] Implement preflight helper in `Workbench.tsx`:
  - [x] Detect unsaved tabs, offer “Save all & continue” default.
  - [x] Detect stale/missing environment vs config digest; choose build+action flow per mode. (Digest-aware still TODO when backend provides digests.)
  - [x] Surface preflight UI (collapsible panel under CTAs) with checklist + primary action label.
- [ ] Refresh toolbar (`WorkbenchChrome`) CTAs and status chips:
  - [x] Environment/Validation/Extraction status chips and last run/build details (CTA menus still to refine).
- [x] Redesign bottom panel (`BottomPanel.tsx`) into Timeline / Issues / Console tabs:
  - [x] Timeline: list activities, status, metadata, selection, re-run/download outputs.
  - [x] Issues: filtered view of selected validation issues (file/line navigation still TODO).
  - [x] Console: logs scoped to selected activity with header actions stubbed (stop/re-run/download logs still TODO).
- [ ] Persist helpful “memory”:
  - [x] Last extraction inputs (document/sheets) per config (local storage or scoped storage).
  - [x] Last validation summary for toolbar chips (explorer badges still TODO).
  - [x] Auto-run-on-save preference (validation after save).
- [ ] Add surface indicators:
  - [x] ActivityBar badges for active/failing builds/runs.
  - [x] Explorer file badges for validation issues; click navigates/open file.
  - [x] Inspector shows selected activity metadata/run links.
- [ ] Update `RunExtractionDialog` to act as a two-step wizard with remembered defaults and quick “re-run last” path.
- [ ] Document new types/contracts in code comments or a short README snippet for future contributors.
- [ ] Add/adjust tests as feasible (hooks, reducers, component state) or leave notes for follow-up.
  - [x] Added reducer coverage for activity state start/append/complete.

## Notes
- Added `useWorkbenchActivities` hook to replace `activeStream`; build/validation/extraction streams now emit into the shared activity model and clear running flags on completion/error.
- Preflight panel added under toolbar for unsaved/build readiness; digest-based staleness still pending backend support.

## Open Questions / Decisions to confirm
- Should validations auto-restart on save during an in-flight run or wait until it completes?
- Enforce single build at a time, or queue with “wait” semantics?
- Required backend support for richer metadata (progress %, row counts, rule IDs) to render in UI?

## References
- Frontend: `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx`, `BottomPanel.tsx`, `ActivityBar.tsx`, `Explorer.tsx`, `Inspector.tsx`, `WorkbenchWindowContext.tsx`.
- APIs: `apps/ade-web/src/shared/builds/api.ts`, `src/shared/runs/api.ts`, `src/shared/configs/api.ts`, `src/shared/configs/hooks/useValidateConfiguration.ts`.
- Backend (if needed): `apps/ade-api/src/ade_api/features/builds/`, `features/configs/`, `features/runs/`.
