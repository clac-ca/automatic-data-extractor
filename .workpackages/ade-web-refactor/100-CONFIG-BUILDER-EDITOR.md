# 100-CONFIG-BUILDER-EDITOR.md  
**ADE Web – Configuration Builder / Editor Specification**

---

## 0. Status & Relationship to Other Docs

This document **specializes** the main workpackage (`010-WORK-PACKAGE.md`) and UX specs (`030-UX-FLOWS.md`) for the **Config Builder / configuration editor**.

- It defines how the Config Builder should **look, feel, and behave**, with a clear “VS Code–like” mental model.
- It describes layout, components, state model, interactions, validation/streaming integration, and non-goals.
- Implementation should follow the constraints from:
  - Architecture: `020-ARCHITECTURE.md`
  - Design system: `040-DESIGN-SYSTEM.md`
  - Run streaming spec: `050-RUN-STREAMING-SPEC.md`
  - Navigation: `060-NAVIGATION.md`

If the Config Builder behavior differs from something said in `010` or `030`, this document is the **source of truth** for the Config Builder.

---

## 1. Purpose & Scope

The Config Builder is the **primary workspace for configuration authors**. It should:

- Feel familiar to developers (VS Code–like):
  - Explorer pane
  - Tabbed editor
  - Resizable panels
  - Inline errors & gutter markers
- Make it easy to:
  - Navigate complex configs (multiple entities/sections).
  - Edit configuration safely and confidently.
  - Run the config and debug errors using streaming telemetry.
- Integrate tightly with:
  - **Run streaming foundation** (`RunStreamProvider` / `useRunStream`).
  - **Validation summary** and per-table insights.
  - **Documents** and **Run Detail** screens via deep links.

### In-scope

- Visual layout and UX of Config Builder.
- Component breakdown and responsibilities.
- Interaction patterns (tabs, explorer, run panel).
- Validation and error surfacing behavior.
- Integration with run streaming and telemetry.

### Out-of-scope

- Backend config schema details.
- Advanced versioning/diffing between config versions (only lightly sketched as future).
- Workspace creation/switching (see `090-FUTURE-WORKSPACES.md`).

---

## 2. Personas & Core Tasks

### Persona A – Config Author / Engineer

- Comfortable with code-like tooling (VS Code, editors).
- Creates and edits ADE configurations:
  - Sources, mappings, validation rules, output schemas, etc.
- Needs to:
  - Navigate multi-file or multi-section configs quickly.
  - Run configs and understand where/why they fail.
  - Iterate rapidly (change → run → inspect → fix).

### Core Tasks

1. **Browse config structure**
   - View all “parts” of a configuration (sources, tables, mappings, validations).
2. **Edit configuration parts**
   - Change settings in structured forms or text-like editors.
3. **Validate and run**
   - Trigger run/validation and see feedback.
4. **Debug failures**
   - Jump from run/validation errors to the exact config element.
5. **Understand impact**
   - See which tables / outputs are produced and their validation status.

---

## 3. Layout & Overall Experience

The Config Builder should look and behave like a **lightweight VS Code tailored to ADE**.

### 3.1 Layout Regions

The screen is divided into three main regions:

```text
+-------------------------------------------------------------+
| AppShell Header (workspace, config name, primary actions)   |
+-------------------------------------------------------------+
| Explorer (left) |      Editor (center)      | Optional RHS  |
|                 |                            side panel*    |
+-------------------------------------------------------------+
|                Bottom Run Panel (full width)                |
+-------------------------------------------------------------+
```

**Explorer (left, 20–30% width)**

* Shows configuration structure:

  * High-level sections (e.g. “Sources”, “Mappings”, “Validation”, “Outputs”).
  * Nested items (tables, pipelines, etc.) as a tree.
* Behaves like VS Code’s file explorer:

  * Expand/collapse.
  * Highlight selected item.
  * Contextual actions (future).

**Editor (center, main area)**

* Multi-tab editor region.
* Each tab represents:

  * A config section (e.g. a specific table mapping).
  * “Raw config” view.
  * Other config-related views (e.g. validation rule group).
* Uses structured form-based editors but keeps a “code editor” feel:

  * Monospace fonts for technical content.
  * Clear labels, indentation, and grouping.

**Bottom Run Panel (full width)**

* Tabbed area for:

  * Run summary.
  * Timeline.
  * Console (log output).
  * Validation summary.
* Shares components with **Run Detail** and **Documents**:

  * `RunConsole`, `RunTimeline`, `ValidationSummary`, `RunSummaryPanel`.

**Optional right-hand side panel** (future / v2):

* For inline previews or more detailed contextual tools (e.g., schema preview, column mapping palette).
* Not required for v1, but layout should allow future expansion.

### 3.2 Resizing & Responsiveness

* Explorer width is resizable via drag handle.
* Bottom Run Panel height is resizable, defaulting to ~25–35% of vertical space.
* On smaller screens:

  * Explorer can collapse to an icon-only bar or collapsible drawer.
  * Bottom Run Panel can collapse to tabs that overlay the editor when opened.

---

## 4. Core Components & Responsibilities

### 4.1 ConfigBuilderScreen

**File:** `screens/ConfigBuilder/ConfigBuilderScreen.tsx`

**Responsibilities:**

* Reads route: `{ workspaceId, configId }`.
* Fetches configuration metadata and summary (via `configsApi`).
* Provides page-level layout using `Page` and `PageHeader`.
* Composes:

  * `ConfigHeaderToolbar`
  * `ConfigExplorerPane`
  * `ConfigEditorTabs`
  * `ConfigRunPanel`

It **does not** manage streaming or run logic directly; it delegates that to `useWorkbenchRun` and `useRunStream`.

---

### 4.2 ConfigHeaderToolbar

**File:** `features/configs/components/ConfigHeaderToolbar.tsx`

**Contents:**

* Breadcrumb / config name.
* Primary actions:

  * “Run” main button.
  * Secondary: “Validate only” (optional).
* Auxiliary actions:

  * “View runs history” (navigates to filtered run list or Run Detail).
  * “Open documents” (if relevant).

**Behavior:**

* When “Run” is clicked:

  * Calls `useWorkbenchRun().runConfig()` which uses `createAndStreamRun`.
* Shows unsaved changes indicator (e.g., dot badge next to config name).

---

### 4.3 ConfigExplorerPane (VS Code–like tree)

**File:** `features/configs/components/ConfigExplorerPane.tsx`

**Purpose:**

* Provide tree-like navigation for the configuration structure.

**Structure (conceptual example):**

```text
Config Name
  • Overview
  • Sources
      - Source A
      - Source B
  • Tables
      - Table: customers
      - Table: orders
  • Validation
      - Rules: customers
      - Rules: orders
  • Outputs
      - Dataset: normalized_customers
      - Dataset: normalized_orders
  • Raw config
```

**Behavior:**

* Clicking an item:

  * Opens/activates corresponding editor tab via `ConfigEditorTabs`.
* Selection style:

  * Single highlighted item at a time.
* Context menu (optional v2):

  * “Add new…” operations, etc.

---

### 4.4 ConfigEditorTabs

**File:** `features/configs/components/ConfigEditorTabs.tsx`

**Purpose:**

* Manage multiple open editors.
* Render correct editor for selected config “entity”.

**Tab rules:**

* Each config explorer item can correspond to at most one open tab.
* Tabs show:

  * Label (e.g., “customers table”, “Source A”).
  * An icon for type (table, source, validation).
  * Dirty indicator (●) if unsaved changes.

**Supported editor types (v1):**

1. **Overview editor**

   * read-only or light editable metadata.
2. **Section editor** (e.g., Source, Table, Validation)

   * Structured, form-style editors:

     * Labeled inputs, dropdowns, toggles.
     * Grouped by logical sub-sections.
3. **Raw config editor**

   * Shows full config as text (JSON/YAML).
   * Monospace, syntax highlighting (if available).
   * Encouraged for advanced users.

---

### 4.5 Editor Behavior & “VS Code Feel”

#### 4.5.1 Editor Look

* Monospace fonts for technical fields or raw config.
* Clean whitespace, no cramped forms.
* Use `PageHeader`-like labels for sections within the editor:

  * “Connection details”, “Column mappings”, etc.

#### 4.5.2 Unsaved Changes & Saving

* Each tab tracks its own dirty state.
* Global save model:

  * **Option A (recommended):** Explicit “Save” with autosave optional later.
  * **Option B:** Autosave after debounce (e.g., 1–2 seconds idle).
* On unsaved exit:

  * If user navigates away or closes tab:

    * Prompt with “Discard changes?” unless autosaved.
* `ConfigHeaderToolbar` shows overall “Unsaved changes” status if any tab is dirty.

#### 4.5.3 Keyboard Shortcuts (v1)

At minimum:

* `Ctrl/Cmd + S` → Save config.
* `Ctrl/Cmd + F` → Find in current tab (editor scope).
* `Esc` → Close dialogs/modals.
* Optionally:

  * `Ctrl/Cmd + Enter` → Run config (same as clicking “Run”).

Full command palette (Ctrl/Cmd+Shift+P) can be v2.

---

## 5. Validation & Error Surfacing

Validation happens at two levels:

1. **Static config validation** (client-side + server-side).
2. **Run-time validation** (from streaming events and summaries).

### 5.1 Static Validation (While Editing)

* Editors use schema-based validation (if available).
* Validation errors show:

  * Inline message below field.
  * Gutter markers in raw editor (if enabled).
* Aggregated view:

  * Config-level validation panel (e.g., “Validation” tab) that lists all issues.

When the user clicks an item in the validation list:

* Focus the corresponding editor/tab.
* Scroll to problematic field or highlight relevant line.

### 5.2 Run-time Validation (Run Panel)

Run-related validation errors come from:

* `validation.summary` in run events.
* Error events with config references (if provided).

Behavior:

* Run Panel’s “Validation” tab:

  * Lists per-table/per-rule failures (like in Run Detail).
* Clicking a validation item:

  * If we can map it to a specific config:

    * Opens relevant tab in `ConfigEditorTabs`.
    * Focuses the field/section that caused the issue.

Mapping logic should be centralized, e.g. in `features/configs/validationMapping.ts`.

---

## 6. Run Panel Integration & Streaming

### 6.1 useWorkbenchRun Hook

**File:** `features/configs/hooks/useWorkbenchRun.ts`

Responsible for:

* Starting runs and validation for the current config.
* Tracking the “current run” metadata.
* Wiring Config Builder to the run streaming foundation.

API (example):

```ts
interface WorkbenchRunApi {
  currentRunId: string | null;
  currentRunStatus: RunStatus | null;
  runConfig: (options?: RunOptions) => Promise<void>;
  validateConfig: () => Promise<void>;
  attachToRun: (runId: string) => void;
}
```

Internally uses:

* `createAndStreamRun` (for new runs).
* `attachToRun` (for existing runs).
* `useRunStream(currentRunId)` to derive status, console lines, timelines, validation.

### 6.2 ConfigRunPanel

**File:** `features/configs/components/ConfigRunPanel.tsx`

Layout:

* Tabbed interface (using `Tabs` from design system):

  * Run
  * Console
  * Validation
  * (Optional) Outputs

Content:

* **Run tab:**

  * `RunSummaryPanel` with status, duration, key metrics.
  * `RunTimeline`.
* **Console tab:**

  * Full `RunConsole`.
* **Validation tab:**

  * `ValidationSummary` with per-table cards.
  * Links into Config Editor on click.
* **Outputs tab (optional, v1.5):**

  * Summary of what outputs the config produced (linking to Documents).

Behavior:

* Panel uses `useRunStream(currentRunId)` (when a run is active).
* Panel is visible even when no run is active:

  * Shows empty state: “No recent runs. Run your config to see results.”

---

## 7. Navigation & Deep Links (Config Builder + Runs)

### 7.1 Entering Config Builder

Route shape (from `060-NAVIGATION.md`):

```ts
{ name: 'configBuilder', params: { workspaceId, configId } }
```

URL example:

* `/workspaces/:workspaceId/configs/:configId`

### 7.2 Linking to Run Detail

From Config Builder:

* Run Panel provides “View full run details” link.
* This navigates to:

```ts
{ name: 'runDetail', params: { workspaceId, runId } }
```

Run Detail uses the shared run streaming foundation and the same components (`RunConsole`, `RunTimeline`, etc.).

### 7.3 Linking from Run Detail Back to Config

Run Detail can provide:

* “Open config” link:

  * If `run` payload includes `configId`, we navigate back to `configBuilder`.

---

## 8. Implementation Plan (Config Builder)

### Phase 1 – Shell & Explorer

* Implement `ConfigBuilderScreen` with:

  * `Page` + `PageHeader`.
  * `ConfigHeaderToolbar`.
  * `ConfigExplorerPane` (static tree with stub data).
  * Empty `ConfigEditorTabs`.
  * Stubbed `ConfigRunPanel`.

### Phase 2 – Editor Tabs & Basic Editing

* Wire `ConfigExplorerPane` clicks to `ConfigEditorTabs`.
* Implement:

  * Overview editor.
  * A generic section editor (using forms).
  * Raw config editor (if schema available).
* Implement unsaved changes tracking and `Ctrl/Cmd+S` save.

### Phase 3 – Run Integration

* Implement `useWorkbenchRun` and integrate with header “Run” button.
* Implement `ConfigRunPanel` using `useRunStream`.
* Add empty state when no run exists.

### Phase 4 – Validation & Error Mapping

* Hook validation (static + run-time).
* Implement “Validation” tab in run panel and config-level validation view.
* Map validation errors to editor locations.

### Phase 5 – Polish & Keyboard

* Add keyboard shortcuts (`Ctrl/Cmd+S`, `Ctrl/Cmd+F`, `Ctrl/Cmd+Enter`).
* Refine resizing, focus management, and transitions.
* Ensure design system consistency:

  * Spacing, typography, status colors.

---

## 9. Non-Goals & Future Enhancements

### Non-goals (for this phase)

* Full code-editor-level features (multi-cursor, advanced refactors).
* Rich diffing between config versions.
* Command palette or global search across all configs.
* Schema inference wizard and guided config generation.

### Future ideas

* Side-by-side diff when comparing two config versions or drafts.
* Inline “test mapping” tools (given a sample row, see how mapping transforms it).
* Command palette (`Ctrl/Cmd+Shift+P`) with quick actions (“Run config”, “Open raw config”, “Jump to validations”).
* Workspaces-specific config defaults or templates.

---

## 10. Definition of Done (Config Builder / Editor)

The Config Builder/editor is considered **done for this workpackage** when:

1. **Layout & components**

   * Explorer, Editor tabs, and Run Panel are implemented with resizable layout.
2. **Editing**

   * Users can open sections of a config from the Explorer and edit via structured editors and/or raw view.
   * Save flows work (toolbar + `Ctrl/Cmd+S`).
3. **Run integration**

   * Users can run the current config.
   * Run Panel shows live status, timeline, console, and validation (for active/historical runs).
4. **Error surfacing**

   * Validation errors (static + run-time) are visible and actionable.
   * Clicking a validation issue opens the relevant editor section.
5. **VS Code–like feel**

   * Tree-like explorer.
   * Tabbed editor.
   * Monospace technical areas.
   * Resizable bottom run panel.
   * Keyboard shortcuts for save/find/run.
6. **Consistency**

   * Config Builder uses the shared design system and streaming components.
   * Behavior aligns with the high-level UX in `030-UX-FLOWS.md` and run behavior in `050-RUN-STREAMING-SPEC.md`.

When these are met, the Config Builder is ready to serve as the primary, VS Code–inspired configuration workspace for ADE.