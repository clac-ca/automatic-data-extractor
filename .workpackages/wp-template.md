> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Remove the Run tab from the workbench bottom panel UI.
* [x] Strip run-summary-specific state/fetching logic (stream snapshot, summary/telemetry fetches).
* [x] Update navigation pane types/docs to only allow Terminal/Problems panes.

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] {{CHECK_TASK_1_SUMMARY}} — {{SHORT_STATUS_OR_COMMIT_REF}}`

---

# Remove run summary tab

## 1. Objective

**Goal:**
Remove the unstable Run summary tab and its supporting logic so the workbench only shows Terminal and Problems panes without flashing content.

You will:

* Remove Run tab UI and pane wiring.
* Drop run-summary/telemetry fetching and live summary storage tied to the tab.
* Keep run status/output handling for console banner/download links.

The result should:

* Only Terminal and Problems panes remain selectable.
* No summary tab flashes or summary fetch side effects; console still reflects run status/output.

---

## 2. Context (What you are starting from)

Workbench bottom panel had three panes (Terminal, Run summary, Problems). Live `engine.run.summary` events were stored and fetched again to populate the Run tab, but the tab briefly flashed then disappeared. We need to simplify to Terminal + Problems while keeping run status/outputs intact.

---

## 3. Target architecture / structure (ideal)

Bottom panel exposes only Terminal and Problems tabs; URL pane param normalizes to those two values. Run stream remains for console/status but does not store or fetch run summaries/telemetry for UI.

> **Agent instruction:**
>
> * Keep this section in sync with reality.
> * If the design changes while coding, update this section and the file tree below.

```text
apps/ade-web/
  src/app/nav/urlState.ts              # pane enum now terminal|problems
  src/screens/.../workbench/components/BottomPanel.tsx
  src/screens/.../workbench/components/ConsoleTab.tsx
  src/screens/.../workbench/state/runStream.ts
  src/screens/.../workbench/state/useRunSessionModel.ts
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* Keep UI minimal and stable (no flashing/missing Run tab).
* Reduce state surface by removing unused summary/telemetry plumbing.
* Preserve run status/output info for console context.

### 4.2 Key components / modules

* BottomPanel — hosts tabs; now only Terminal/Problems.
* ConsoleTab — shows console lines and run status badge (no summary CTA).
* runStream/useRunSessionModel — manage stream state and latest run metadata without run summary storage/fetching.

### 4.3 Key flows / pipelines

* Stream handling — ingest events for status/console, but ignore run summary payloads beyond status/artifact data.
* Run completion — update latestRun for console/output download without summary/telemetry fetches.

### 4.4 Open questions / decisions

* Future redesign will determine new run insights surface and data needs.

> **Agent instruction:**
> If you answer a question or make a design decision, replace the placeholder with the final decision and (optionally) a brief rationale.

---

## 5. Implementation & notes for agents

* URL pane param normalizes unknown/legacy values to `terminal`.
* Run summary/telemetry fetching removed; output/log links still fetched via run resource.
* Tests not run here (pnpm unavailable); focus on runStream reducer/unit coverage if adding new tests.
