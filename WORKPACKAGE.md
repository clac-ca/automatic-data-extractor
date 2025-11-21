# Note for agents: keep this workpackage updated as you go (check items off, add new ones if needed, and record decisions/risks).

## Objective
Design and scaffold the unified Environment / Validation / Run activity experience in the Config Builder workbench (apps/ade-web), aligning with the “activity timeline + preflight” concept.

## Checklist
- [ ] Define shared activity model and reducer in `Workbench.tsx` (or a dedicated hook/context) to replace `activeStream`:
  - [ ] Activity types (`build`, `validation`, `extraction`), status enum, metadata (digests, document/sheets, counts), logs, validation issues.
  - [ ] Actions for start, log append, issue append, status updates, completion, selection.
- [ ] Wire streams into the activity model:
  - [ ] Build stream (`@shared/builds/api`) → activity start/update/complete with reuse/fresh metadata and errors.
  - [ ] Validation (run stream + `useValidateConfigurationMutation`) → activity with incremental issue ingestion.
  - [ ] Extraction run stream (`@shared/runs/api`) → activity with document/sheet metadata, outputs, errors.
- [ ] Implement preflight helper in `Workbench.tsx`:
  - [ ] Detect unsaved tabs, offer “Save all & continue” default.
  - [ ] Detect stale/missing environment vs config digest; choose build+action flow per mode.
  - [ ] Surface preflight UI (collapsible panel under CTAs) with checklist + primary action label.
- [ ] Refresh toolbar (`WorkbenchChrome`) CTAs and status chips:
  - [ ] Environment button/menu (build/rebuild/auto-build toggle, last build details).
  - [ ] Validation button/chip (last run summary, re-run last).
  - [ ] Extraction button/dropdown (re-run last, select different document).
- [ ] Redesign bottom panel (`BottomPanel.tsx`) into Timeline / Issues / Console tabs:
  - [ ] Timeline: list activities, status, metadata, actions (select, re-run, download outputs).
  - [ ] Issues: filtered view of selected validation issues with file/line navigation to `EditorArea`.
  - [ ] Console: logs scoped to selected activity with header actions (stop/re-run/download logs).
- [ ] Persist helpful “memory”:
  - [ ] Last extraction inputs (document/sheets) per config (local storage or scoped storage).
  - [ ] Last validation summary for chips and explorer badges.
  - [ ] Auto-run-on-save preference.
- [ ] Add surface indicators:
  - [ ] ActivityBar badges for active/failing builds/runs.
  - [ ] Explorer file badges for validation issues; click navigates/open file.
  - [ ] Inspector shows selected activity metadata/run links.
- [ ] Update `RunExtractionDialog` to act as a two-step wizard with remembered defaults and quick “re-run last” path.
- [ ] Document new types/contracts in code comments or a short README snippet for future contributors.
- [ ] Add/adjust tests as feasible (hooks, reducers, component state) or leave notes for follow-up.

## Open Questions / Decisions to confirm
- Should validations auto-restart on save during an in-flight run or wait until it completes?
- Enforce single build at a time, or queue with “wait” semantics?
- Required backend support for richer metadata (progress %, row counts, rule IDs) to render in UI?

## References
- Frontend: `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx`, `BottomPanel.tsx`, `ActivityBar.tsx`, `Explorer.tsx`, `Inspector.tsx`, `WorkbenchWindowContext.tsx`.
- APIs: `apps/ade-web/src/shared/builds/api.ts`, `src/shared/runs/api.ts`, `src/shared/configs/api.ts`, `src/shared/configs/hooks/useValidateConfiguration.ts`.
- Backend (if needed): `apps/ade-api/src/ade_api/features/builds/`, `features/configs/`, `features/runs/`.
