# ADE Web – UX Flows & Interaction Design
> File: `.workpackages/ade-web-refactor/030-UX-FLOWS.md`

## 1. Purpose

This document defines the **user experience flows** for the new `ade-web`:

- How users **navigate** between key areas (Workspace, Documents, Run Detail, Config Builder).
- Exactly what happens when they **upload files**, **start runs**, **monitor progress**, **investigate failures**, and **download results**.
- How **Config Builder** and **Run Detail** fit into this story.

It is the UX companion to the main workpackage (`010-WORK-PACKAGE.md`) and the architecture doc (`020-ARCHITECTURE.md`).  
If you are unsure “what the UI should do” in a given situation, check or update this file.

---

## 2. Personas & Mindset

### 2.1 Config Author / Engineer

- Cares about **config correctness**, **schema mapping**, and **validation rules**.
- Spends most time in **Config Builder**.
- Needs:
  - Rich telemetry (phases, detailed logs, validation per table).
  - Ability to replay runs and debug failures.
  - Links from failures back to relevant config sections.

### 2.2 Document User / Analyst

- Primary home is the **Documents** pane.
- Cares about:
  - “Did my file process successfully?”
  - “Where do I download the normalized file?”
  - “What went wrong and where should I look?”
- Often non-technical. We should **avoid jargon** and make next steps obvious.

Both personas share the same **Run Detail** view for deeper investigation.

---

## 3. Global UX Principles

These apply across all screens:

1. **Clear location & context**
   - Page titles include workspace + entity name (e.g., “Documents – Workspace A”, “Run #123 for `sales.csv`”).
   - Status badges and timestamps are always visible near the top.

2. **One obvious next step**
   - After upload → “Start run”.
   - During run → “View run progress”.
   - After success → “Download normalized file”.
   - After failure → “Review errors”.

3. **Shared visual language**
   - Status colors and badges are consistent across Documents, Run Detail, and Config Builder.
   - Shared components for console, timelines, and validation summaries.

4. **Error-first debugging**
   - Failures clearly highlighted with human-friendly messages.
   - “Jump to first error” is one click away.
   - Validation issues link to relevant console events and, where possible, to config sections.

5. **No dead-ends**
   - Every view has a clear path back (Documents ⇄ Run Detail ⇄ Config Builder).

---

## 4. Navigation & Mental Model

### 4.1 Top-Level Areas

- **Workspace Home**
  - Orientation.
  - Shortcuts into Documents, Config Builder, and recent runs.

- **Documents**
  - Manage input files, start runs, monitor per-document history, and download outputs.

- **Run Detail**
  - Deep inspection and replay of a specific run.

- **Config Builder**
  - Authoring and testing of configs.

### 4.2 Typical Journeys

1. **Document-first journey (Analyst)**
   - Workspace Home → Documents → Upload file → Start run → Monitor → Download normalized file.

2. **Config-first journey (Engineer)**
   - Workspace Home → Config Builder → Edit config → Start run → Inspect logs → Fix config → Re-run → Share Run Detail link.

3. **Debug journey**
   - Documents or Config Builder → Failed run → Run Detail → Identify failing phase / table → (Optionally) Open Config Builder or share link.

---

## 5. Documents UX – Upload → Run → Review → Download

The Documents area is **the main experience we were missing**. It should feel like a guided, end-to-end flow.

### 5.1 Documents Screen Layout

**Left column: Document list**

- Table listing:
  - Document name
  - Status badge (see states below)
  - Last run result (OK / Warnings / Failed / Never run)
  - Last updated (relative “2h ago” + tooltip with exact time)
- Row interactions:
  - Click row → select document and open details in right panel.
  - Optional overflow menu for advanced actions (rename, delete, etc. — future).

**Right panel: Document detail**

- When no document selected:
  - Friendly empty state:
    - “Select a document from the list, or upload a new one to get started.”
- When a document is selected:
  - Header: document name + status badge + primary action (“Start run” or “View latest run”).
  - Tabs:
    - **Overview**
    - **Runs**
    - **Outputs**
    - (Optional later: **Validation**)

### 5.2 Document States

We define a **small, consistent set of states** for documents:

- **Never run**
  - Document uploaded, no completed or active runs.
- **Processing**
  - A run is currently in progress for this document.
- **Completed (success)**
  - Last run finished without errors (or with benign warnings only).
- **Completed (warnings)**
  - Last run completed but produced warnings.
- **Failed**
  - Last run failed or produced blocking errors.

These are reflected via a badge in both the **document list** and **document header**.

### 5.3 Flow: First-Time User – Upload and Run

1. **User lands on Documents screen with no documents**
   - Main state:
     - Empty table.
     - Prominent **“Upload document”** primary button.
     - Dropzone area with hint: “Drop files here or click to upload”.

2. **User uploads file(s)**
   - As soon as a file is selected/dropped:
     - A temporary “uploading row” appears in the document list with spinner.
   - On success:
     - Row transitions to normal state with status “Never run”.
     - The newly uploaded document becomes selected automatically.
     - Right panel shows:
       - Document name.
       - “This document has not been processed yet.” helper text.
       - Primary action: **“Start first run”**.
   - On upload error:
     - Row shows status “Upload failed”.
     - Clear message: “We couldn’t upload this file. Try again or contact support.”  
       (No mysterious error codes.)

3. **User clicks “Start first run”**
   - If there is a single default config:
     - Trigger run creation directly.
   - If multiple configs available:
     - Show small inline selector:
       - “Choose configuration to run”
       - Combo box of config names.
     - After selection, user clicks “Start run”.
   - UI feedback:
     - Primary action enters loading state.
     - Status badge in header changes to “Processing”.
     - Left list row animates to “Processing” and shows a small progress indicator.

### 5.4 Flow: Run in Progress (Document Context)

Once the run starts:

- **Document list**
  - Row status: “Processing” (blue badge).
  - A subtle progress indicator below name or in a dedicated column.
  - Tooltip: “Currently in phase: Normalizing columns” (if available).

- **Document detail – Overview tab**
  - Displays a **“Live run”** card at top:
    - Status line:
      - “Running – Normalizing columns (phase 2 of 4)”
    - Elapsed time (e.g., “1m 23s”).
    - Phase progress bar or small set of steps.
    - Last ~10 console lines in a compact view.
    - Link: “View full run logs” → navigates to Run Detail for this run.

- **Interactions during run**
  - User may navigate away (to another document / screen).  
    - Run continues server-side; when they return:
      - The app uses `useRunStream` to reattach and show current status.
  - Live card should gracefully handle reconnections:
    - If stream temporarily disconnects, display a subtle “Reconnecting…” label.

### 5.5 Flow: Run Completes Successfully

When the run finishes successfully:

- **Document list**
  - Row status: “Completed”.
  - Last run result: “OK” or “Completed (warnings)” depending on validation summary.

- **Document detail – Overview tab**
  - Live run card transitions to a **result card**:
    - Headline: “Run completed successfully”.
    - Subtext: “Processed 125,084 rows in 45s”.
    - If warnings:
      - “Completed with 3 warnings” and a small “View validation details” link.
    - Primary action: **“Review outputs”** (switches to Outputs tab).
    - Secondary action: “View run details” (navigates to Run Detail).

- **Outputs tab**
  - Sections:
    1. **Original file**
       - “Original uploaded file”
       - Download button.
    2. **Normalized outputs**
       - One row per format (e.g., “Normalized CSV”, “Normalized Parquet”).
       - Each row has:
         - Format, size, ready indicator.
         - “Download” button.
    3. **Logs**
       - “Run logs (text)” + “Run events (NDJSON)”.
       - “Download” buttons.
    4. **Validation report** (if provided)
       - “Validation report (HTML/JSON)”.
       - “Download” button.

  - Visual clarity: group sections with headings and spacing so users don’t confuse original vs normalized outputs.

### 5.6 Flow: Run Fails

When the run fails:

- **Document list**
  - Row status: “Failed” (red).
  - Last run result: “Failed at Normalizing”.

- **Document detail – Overview tab**
  - Result card:
    - Headline: “Run failed during Normalizing”.
    - A one-line explanation derived from event context (if available).
    - Primary action: **“Review errors”** (navigates to Run Detail).
    - Secondary action: “View outputs” (if partial outputs exist and are safe to expose).

- **Runs tab**
  - The failed run appears at top of the run history list with red status and short reason (“Failed at Validate schema”).

- **Validation / Issues (if present)**
  - Show a clear summary:
    - “3 tables with errors, 2 with warnings”.
  - Provide quick filters:
    - “Show error tables only”.

### 5.7 Flow: Downloading & Coming Back Later

Use case: user runs something, leaves, returns days later to get the normalized file.

1. User opens Documents.
2. Finds document in the list.
3. Sees status “Completed” or “Failed”.
4. Clicks document row.
5. In the right panel:
   - If completed:
     - Clear “Download normalized…” call-to-action in Overview.
     - Outputs tab shows the full list, as described above.
   - If failed:
     - Prominent “Review errors” button leading to Run Detail.
     - Outputs tab still available but may show limited outputs.

Goal: user never has to “hunt” for the right download—they should see it in either the Overview CTA or Outputs tab.

---

## 6. Run Detail UX – Inspect, Replay, Debug

Run Detail is the **shared deep-inspection view** for all runs.

### 6.1 Entry Points

- From Documents:
  - Runs tab → “Open run details”.
  - Overview: result card → “View run details”.
- From Config Builder:
  - Run panel → “View full run details”.
- From links:
  - Pasted URL containing `runId` (and optionally `sequence`).

### 6.2 Layout & Content

**Header**

- Title: “Run #1234 · `sales.csv`” or “Run #1234 · Config `Orders to Warehouse`”.
- Status pill.
- Summary line:
  - “Started 3m ago · Duration 01:23 · 3 tables, 2 errors, 1 warning”.
- Actions:
  - “Download normalized outputs”.
  - “Download logs”.
  - “Copy link to this run”.

**Body**

We use a **two-column layout** on desktop:

- **Left/main column**
  - **RunTimeline**
    - Horizontal or vertical timeline of phases:
      - Build phases, then run phases.
      - Each shows name, duration, and color-coded status.
  - Tabs:
    - **Console** – `RunConsole` with filters and full log.
    - **Validation** – per-table cards with severity and row counts.
- **Right/side column**
  - **RunSummaryPanel**
    - High-level status.
    - Key metrics.
    - Document/Config links.
  - **Downloads**
    - Same outputs as Documents → Outputs tab, but scoped to this run.
  - Quick navigation links back to:
    - The associated document.
    - The associated config.

### 6.3 Console Behavior

`RunConsole` is shared across contexts:

- Shows log lines with:
  - Timestamp.
  - Level (INFO/WARN/ERROR).
  - Origin (build/run).
  - Message.
- Filters:
  - Text search (free text).
  - Level filter (INFO/WARN/ERROR).
  - Origin filter (build/run).
  - Phase filter (if available).
- Controls:
  - “Follow tail” (for live runs).
  - “Freeze” (stop auto-scroll to inspect a particular area).
- **Error-first mode**:
  - If run failed, console automatically scrolls to the first `ERROR` event and highlights it.
  - A small banner at top of console:
    - “Jump to first error” button (if user moved away).
    - “Back to live tail” button (if run is still running and user is off the tail).

### 6.4 Replay & Deep Links

- Sequence slider:
  - Appears above console and timeline.
  - When user drags it:
    - We replay event history up to that sequence.
    - Console and timeline reflect the historical state at that point.
- Controls:
  - “Play from beginning” button that animates through events.
  - “Jump to first error”.
  - “Back to final state” (for completed runs) or “Back to live” (for running).
- Deep link behavior:
  - When user clicks “Copy link to this error”:
    - We generate a URL with `?sequence=<errorSequence>`.
  - Opening that URL:
    - Automatically replays up to that sequence.
    - Centers console on that log line and highlights it.

Goal: make it trivial to **share a specific moment** in a run between teammates.

---

## 7. Config Builder UX – Authoring & Run Feedback

Config Builder is the environment for building and testing configs.

### 7.1 Layout

- **Left sidebar**
  - Config list / tree (e.g., files, sections, or steps).
- **Center**
  - Editor area (forms, code editor, or config views).
- **Bottom or right panel**
  - Run panel with tabs:
    - Run overview (phases + high-level status).
    - Console.
    - Validation.

This uses the same design system primitives as other screens.

### 7.2 Flows

**Editing**

- Users edit config fields and see validation feedback inline (e.g., missing required fields).

**Starting a run**

- Primary CTA near the top or bottom: “Run config”.
- On click:
  - `useWorkbenchRun` calls `createAndStreamRun`.
  - Run panel becomes visible (if collapsed).
  - Run panel status changes to “Running”.

**Run panel**

- **Run tab**
  - RunTimeline (phases).
  - Summary card (“Processing 3 document tables…”).
- **Console tab**
  - Full `RunConsole` using shared implementation.
- **Validation tab**
  - Table cards with error/warning counts.
  - Potential link back to specific config inputs (future).

**Failure flow**

- If run fails:
  - A message near the editor:
    - “Run failed during {{phase}}. See errors below.”
  - “Go to first error” button toggles console and scrolls to first error.
  - Optionally, show targeted hints:
    - “Column `customer_id` missing in input” → highlight mapping section.

**Run Detail hand-off**

- From run panel:
  - “Open full run details” link opens Run Detail screen.
  - Config author can share link with others (analysts, teammates).

---

## 8. Workspace Home UX

Workspace Home is a **lightweight launchpad**.

### 8.1 Content

- Header: “Workspace: {{name}}”.
- Panels:
  - **Documents quick start**
    - “Upload documents & run normalization”.
    - Button: “Go to Documents”.
    - Show top N documents (name, last run status).
  - **Config Builder**
    - “Manage and test configurations”.
    - Button: “Go to Configs”.
    - Top N configs.
  - **Recent runs**
    - List of last N runs (status, duration, source: config vs document).
    - Link to Run Detail.

The goal is not depth, but **orientation**.

---

## 9. Accessibility & State Feedback

### 9.1 Keyboard & Focus

- List rows (Documents, Runs) are keyboard-focusable and clickable.
- Tabs are keyboard-navigable (arrow-keys, Home/End).
- Modal dialogs (e.g., config selectors) trap focus correctly.

### 9.2 Screen Readers

- Status changes announce via aria-live regions:
  - Example: “Run completed successfully” or “Run failed during Normalizing”.
- Upload zone has appropriate “button” and “drop area” semantics.

### 9.3 Loading & Empty States

- Use skeletons for:
  - Document list loading.
  - Run Detail logs & timeline initial load.
- Avoid blank panels; always show some explanatory text when empty.

---

## 10. How to Use & Update This Document

- If you implement a new flow (e.g., different document state or download type), **update this doc** first.
- If UX behavior diverges from what’s written here (for a good reason), adjust this doc and reference the change in the workpackage checklist.
- Keep flows user-centered (what they see, feel, and can do), not implementation-focused.