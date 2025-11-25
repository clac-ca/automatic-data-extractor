# 09 – Workbench editor and scripting

The **Config Builder workbench** is the dedicated editing window used to edit ADE configuration packages and run environment builds, validation runs, and test runs directly from the browser. Use “workbench” for the whole window and “editor” only for the Monaco instance.

This document covers the internal architecture of the workbench in `ade-web`:

- How a workbench **session** is scoped.
- **Window states** and navigation safety.
- The **layout**: activity bar, explorer, editor, console, validation, inspector.
- The **file tree** model and how it’s built from backend listings.
- The **tab** model, loading/saving, and persistence.
- How **URL state** and local storage interact.
- The **console** and **validation** panels and their data flow.
- The Monaco‑based **CodeEditor** and **theme** preference.
- ADE‑specific **scripting helpers** for detectors, transforms, validators, and hooks.

Workbench run actions use the canonical `RunOptions` shape
(`dryRun`/`validateOnly`/`inputSheetNames` with optional `mode`) in camelCase
and convert those to backend snake_case fields. Environment builds are separate
`Build` entities; validation runs and test runs are always `Run` entities.

Configuration lifecycles and manifest details live in `08-configurations-and-config-builder.md`. Core naming (e.g. “run”) is defined in `01-domain-model-and-naming.md`.

---

## 1. Workbench session and identity

A workbench session is always scoped to a **single configuration in a single workspace**.

- **Session key**: `(workspaceId, configurationId)`
- At any given time, in a browser tab, there is at most **one active workbench** for that `(workspaceId, configurationId)`.
- Session‑scoped state includes:
  - Window state (restored / maximized / docked).
  - Open tabs and MRU order.
  - Console open/closed state and height.
  - Editor theme preference.

### 1.1 Entering and exiting the workbench

Typical entry:

- User clicks “Open in workbench” (UI label may read “Open editor”) from the Config Builder screen.
- Current URL is captured as the **return path** and stored under:

  ```text
  ade.ui.workspace.<workspaceId>.workbench.returnPath
````

On exit:

* The workbench close action:

  * Checks for unsaved changes (see §2.3).
  * If allowed, navigates back to the stored return path (if any), otherwise falls back to the Config Builder screen.
  * Clears the stored return path.

### 1.2 Window states

The workbench supports three window states:

* **Restored**

  * Embedded inside the Config Builder section.
  * Workspace shell (top bar, left nav) is visible and interactive.

* **Maximized**

  * Workbench overlays the full viewport.
  * Workspace shell is visually dimmed and effectively disabled.
  * Body scroll is locked while maximized.

* **Docked (minimized)**

  * Workbench UI is hidden.
  * A “docked workbench” affordance in the Config Builder screen re‑opens it.

Conceptually:

```ts
type WorkbenchWindowState = "restored" | "maximized" | "docked";

interface WorkbenchWindowContextValue {
  state: WorkbenchWindowState;
  setState(next: WorkbenchWindowState): void;
  close(): void; // respects unsaved-change guards
}
```

Window state is **session‑local** only (not persisted). On reload we always start in `restored` to avoid surprising full‑screen states.

### 1.3 Unsaved changes and navigation blockers

The workbench uses `useNavigationBlocker` to guard unsaved changes:

* A tab is **dirty** if `content !== initialContent`.
* A session is **dirty** if any tab is dirty.
* While dirty:

  * Any navigation that changes the **pathname** (different page) is intercepted.
  * The user sees a confirmation dialog (“You have unsaved changes …”).
  * If they confirm:

    * The blocker is temporarily disabled.
    * The navigation is retried.
  * If they cancel:

    * The navigation is cancelled.
    * The URL is restored to the previous location.

Navigation that only changes **search** or **hash** (e.g. switching console pane) is allowed so URL state updates remain smooth.

The same blocker protects:

* Closing the workbench window.
* Switching workspace sections via the left nav.
* Browser back/forward.

---

## 2. Layout and panels

The workbench uses a familiar editor layout so it’s easy to orient yourself:

```text
+-------------------------------------------------------------+
| Activity |            Editor & Tabs                         |
|   Bar    |                                                 |
|         Explorer     Editor       Inspector                |
|         Panel        Area         Panel                    |
|                       |             |                      |
|                       |             |                      |
+-----------------------+-------------+----------------------+
|                        Console / Validation                |
+-------------------------------------------------------------+
```

### 2.1 Activity bar

Leftmost vertical bar that selects the **mode**:

* **Explorer** – file tree. (Implemented.)
* **Search** – reserved for future in‑configuration search.
* **SCM** – reserved for future source control features.
* **Extensions** – reserved for future extensibility.
* **Settings** (gear) – workbench‑level preferences.

Currently, only **Explorer** is active; the others are placeholders.

### 2.2 Explorer panel

Left sidebar that shows the **configuration file tree**:

* Renders `WorkbenchFileNode` trees (see §3).
* Highlights the currently active file.
* Marks open files (e.g. with a dot or italic label).
* Provides a right‑click `ContextMenu` for:

  * Opening files in new tabs.
  * Copying paths.
  * Creating/renaming/deleting files or folders (where backend supports it).
  * Closing related tabs.

Selecting a file:

* Opens a tab if not already open.
* Activates that tab.
* Updates the URL `file` query parameter (see §5).

### 2.3 Editor area

Center panel that hosts the tab strip and Monaco editor.

* **Tab strip:**

  * Pinned tabs appear on the left.
  * Dirty tabs show a visual marker (e.g. dot, italic).
  * Right‑click menu supports close / close others / close to right / pin / unpin.
  * Keyboard navigation integrates with MRU (Ctrl+Tab / ⌘Tab).

* **Editor:**

  * Uses the shared `CodeEditor` (see §7).
  * Binds ⌘S / Ctrl+S to save the active file.
  * Uses the resolved editor theme for `(workspaceId, configurationId)`.
  * Displays language‑appropriate syntax highlighting (`language` from tab/file metadata).

### 2.4 Console and validation panel (bottom)

Bottom strip toggles between:

* **Console tab**

  * Shows streaming logs from builds and runs in plain text.
  * Highlights run status (succeeded/failed).
  * Shows a **Run summary** card when runs complete:

    * Run ID.
    * Selected document + sheet names.
    * High‑level metrics (rows processed, warnings, errors) when available.
    * Links to outputs (artifact, telemetry, logs).

* **Validation tab**

  * Shows structured validation issues from a validation run (`RunOptions.validateOnly`):

    ```ts
    interface ValidationIssue {
      severity: "error" | "warning" | "info";
      message: string;
      file?: string;
      line?: number;
      column?: number;
      path?: string; // manifest/configuration path
    }
    ```
  * Issues can be grouped by file / table / severity.
  * Clicking an issue:

    * Focuses the relevant file.
    * Opens it in a tab.
    * Optionally scrolls the editor to the reported line.

The bottom panel supports:

* Open/closed state (collapsed vs visible).
* Draggable height, persisted as a fraction of the vertical space (see §6).

On very short viewports, the panel may auto‑collapse and show a one‑time banner explaining why.

### 2.5 Inspector panel

Optional right sidebar that shows metadata for the **active file**:

* Path and display name.
* Size and last modified timestamp.
* Content type and ETag.
* Load state (loading / ready / error).
* Dirty vs saved status.
* Last saved timestamp.

The inspector never edits content; it’s purely informational.

---

## 3. File tree model

The workbench file tree is a typed, in‑memory representation of the configuration package.

### 3.1 Data model

```ts
export type WorkbenchFileKind = "file" | "folder";

export interface WorkbenchFileMetadata {
  size?: number | null;
  modifiedAt?: string | null;   // ISO 8601
  contentType?: string | null;
  etag?: string | null;
}

export interface WorkbenchFileNode {
  id: string;                   // canonical path, e.g. "ade_config/detectors/membership.py"
  name: string;                 // basename, e.g. "membership.py"
  kind: WorkbenchFileKind;
  language?: string;            // "python" | "json" | "markdown" | ...
  children?: WorkbenchFileNode[];
  metadata?: WorkbenchFileMetadata | null;
}
```

**Invariants:**

* `id` is a canonical, slash‑separated path relative to the configuration root.
* `name === basename(id)`.
* Folders (`kind: "folder"`) may have `children`; files do not.
* `language` is present for editable files; folders can leave it undefined.

### 3.2 Constructing the tree from backend listing

The backend returns a flat listing, conceptually:

```ts
interface FileListingEntry {
  path: string;        // "ade_config/detectors/membership.py"
  name: string;        // "membership.py"
  parent: string;      // "ade_config/detectors"
  kind: "file" | "dir";
  depth: number;
  size?: number;
  mtime?: string;
  content_type?: string;
  etag?: string;
}
```

`createWorkbenchTreeFromListing(listing: FileListingEntry[]): WorkbenchFileNode`:

1. **Normalise paths**

   * Remove trailing slashes.
   * Collapse any `.` segments.
2. **Ensure folder structure**

   * Build folders for any `parent` path that appears.
3. **Create nodes**

   * For each entry:

     * If `kind === "dir"`, ensure a folder node exists.
     * If `kind === "file"`, create a file node with metadata.
   * Infer `language` from extension (e.g. `.py` → `python`, `.json` → `json`, `.md` → `markdown`).
4. **Sort children**

   * Folders before files.
   * Alphabetically by `name` (case‑insensitive) within each group.

Helper utilities:

* `extractName(path: string): string` – basename.
* `deriveParent(path: string): string` – parent path or `""` for root.
* `findFileNode(root, id)` – depth‑first search by `id`.
* `findFirstFile(root)` – first file in folder‑first traversal (used as an initial selection fallback).

### 3.3 Tree operations

The tree itself is **pure** (no side effects). Operations go through APIs and then rebuild or patch the tree:

* **Select file** → find node, open tab, update URL.
* **Refresh listing** → fetch listing, rebuild tree, try to preserve:

  * Selected file.
  * Open tabs (see §4.3).
* **Create / rename / delete** → call appropriate configuration file endpoints, then refresh or incrementally update the tree.

---

## 4. Tabs, file content, and persistence

Tabs are the primary unit of editing. Each open file has one tab instance.

### 4.1 Tab model

```ts
export type WorkbenchFileTabStatus = "loading" | "ready" | "error";

export interface WorkbenchFileTab {
  id: string;                   // file id / path
  name: string;                 // display name
  language?: string;
  initialContent: string;       // last saved content
  content: string;              // current editor content
  status: WorkbenchFileTabStatus;
  error?: string | null;        // load error
  etag?: string | null;         // concurrency token from backend
  metadata?: WorkbenchFileMetadata | null;
  pinned?: boolean;
  saving?: boolean;
  saveError?: string | null;    // last save error
  lastSavedAt?: string | null;  // ISO timestamp of last successful save
}
```

Dirty state:

```ts
const isDirty = tab.content !== tab.initialContent;
```

### 4.2 `useWorkbenchFiles` responsibilities

A dedicated hook manages tab state and IO for file content:

* **Open file**

  * If tab exists, activate it.
  * If not:

    * Add tab with `status: "loading"`.
    * Fetch content & metadata from backend (`GET /files/{file_path}`).
    * On success:

      * Set `initialContent`, `content`, `etag`, `metadata`, `status: "ready"`.
    * On failure:

      * Set `status: "error"` and `error` message.

* **Edit content**

  * Bound to editor’s `onChange`.
  * Updates `content`.
  * Dirty state is recomputed from `content` vs `initialContent`.

* **Save**

  * No‑op if not dirty.
  * Otherwise:

    * Send `content` to backend (`PUT /files/{file_path}`) with `etag` as precondition if supported.
    * On success:

      * Update `initialContent` to current `content`.
      * Update `etag`, `metadata.modifiedAt`, `lastSavedAt`.
      * Clear `saveError`.
    * On concurrency conflict:

      * Keep content.
      * Set `saveError` with a clear conflict message.
      * Do **not** blindly overwrite.

* **Close tabs**

  * Single tab, others, to right, all.
  * Prompt if any to‑be‑closed tab is dirty.

* **Pin / unpin**

  * Toggle `pinned`.
  * Tab strip keeps pinned tabs grouped on the left.

* **MRU tracking**

  * Maintain MRU order (e.g. array of tab IDs).
  * When a tab becomes active, move its ID to front.
  * Keyboard shortcuts (Ctrl+Tab / ⌘Tab) follow MRU order, not visual order.

### 4.3 Tab persistence

We persist tab **identity**, not content, to allow seamless reloads without storing code outside the configuration package.

```ts
interface PersistedWorkbenchTabs {
  readonly openTabs: readonly (string | { id: string; pinned?: boolean })[];
  readonly activeTabId?: string | null;
  readonly mru?: readonly string[];
}
```

Storage key:

```text
ade.ui.workspace.<workspaceId>.configuration.<configurationId>.tabs
```

Hydration algorithm:

1. Read persisted snapshot (if any).
2. Filter out files not present in the current file tree.
3. For each remaining file:

   * Open a tab (lazy load content).
   * Reapply `pinned` flags.
4. Restore `activeTabId` if that file still exists.
5. Restore MRU order for shortcuts.

On any tab add/remove/pin/unpin:

* Write a fresh snapshot to local storage.

---

## 5. Workbench URL state

The URL encodes **shareable view state** for the workbench: which file is open, which bottom pane is visible, etc.

### 5.1 State model

```ts
export type ConfigBuilderTab = "editor";
export type ConfigBuilderPane = "console" | "validation";
export type ConfigBuilderConsole = "open" | "closed";
export type ConfigBuilderView = "editor" | "split" | "zen";

export interface ConfigBuilderSearchState {
  readonly tab: ConfigBuilderTab;
  readonly pane: ConfigBuilderPane;
  readonly console: ConfigBuilderConsole;
  readonly view: ConfigBuilderView;
  readonly file?: string;             // file id/path
}
```

Defaults:

```ts
export const DEFAULT_CONFIG_BUILDER_SEARCH: ConfigBuilderSearchState = {
  tab: "editor",
  pane: "console",
  console: "closed",
  view: "editor",
};
```

### 5.2 Reading from the URL

`readConfigBuilderSearch(source)` returns:

```ts
export interface ConfigBuilderSearchSnapshot
  extends ConfigBuilderSearchState {
  readonly present: {
    readonly tab: boolean;
    readonly pane: boolean;
    readonly console: boolean;
    readonly view: boolean;
    readonly file: boolean;
  };
}
```

It:

* Parses the search string or `URLSearchParams`.
* Normalises invalid values back to defaults.
* Maps legacy `path` to `file` if needed.
* Records which keys were explicitly present (`present.*`).

### 5.3 Writing to the URL

`mergeConfigBuilderSearch(currentParams, patch)`:

1. Reads current state via `readConfigBuilderSearch`.
2. Merges defaults, current state, and the `patch`.
3. Produces new `URLSearchParams` by:

   * Clearing all builder‑related keys (`tab`, `pane`, `console`, `view`, `file`, `path`).
   * Writing only keys whose values differ from defaults.
   * Omitting `file` if empty.

This keeps URLs compact and stable while still letting users bookmark meaningful differences.

### 5.4 `useWorkbenchUrlState`

A small abstraction wraps `useSearchParams` and the helpers:

```ts
interface WorkbenchUrlState {
  readonly fileId?: string;
  readonly pane: ConfigBuilderPane;
  readonly console: ConfigBuilderConsole;
  readonly consoleExplicit: boolean;
  readonly setFileId: (fileId: string | undefined) => void;
  readonly setPane: (pane: ConfigBuilderPane) => void;
  readonly setConsole: (console: ConfigBuilderConsole) => void;
}
```

Behaviour:

* `fileId` comes from `file` in the query string.

* `setFileId` / `setPane` / `setConsole`:

  * No‑op if the value wouldn’t change.
  * Use `mergeConfigBuilderSearch` to produce new params.
  * Call `setSearchParams(next, { replace: true })` to avoid history spam.

* `consoleExplicit`:

  * True if the URL explicitly includes a `console` key (`present.console`).
  * When true, URL `console` state overrides persisted console preferences (see §6).
  * When false, local preferences decide initial open/closed state.

---

## 6. Console state and persistence

The console panel has its own persisted preferences, independent of URL state.

### 6.1 ConsolePanelPreferences

```ts
interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number;              // 0–1 of available vertical space
  readonly state: ConfigBuilderConsole;   // "open" | "closed"
}
```

Storage key:

```text
ade.ui.workspace.<workspaceId>.configuration.<configurationId>.console
```

Hydration:

1. Read stored preferences (if any).
2. If `version` mismatches, ignore and use defaults.
3. If `consoleExplicit` from URL is true:

   * Override `state` with URL value.
4. Otherwise, use stored `state`.

Resize:

* When user drags the panel splitter, update `fraction` and write preferences.

Open/close:

* When toggling console, update `state` and write preferences.

The **URL** determines shareable state; local storage retains a user’s personal layout.

---

## 7. Build and run streams

The workbench console and validation views consume streaming events from the backend.

### 7.1 Build streams

The **Build environment** button starts a build and streams events into the console.

Conceptually:

```ts
streamBuild(workspaceId, configurationId, options, signal);
```

* Uses NDJSON to deliver events (status updates, log lines).
* Normal behaviour:

  * “Build / reuse environment” reuses container when possible.
  * “Force rebuild now” triggers a full rebuild.
  * “Force rebuild after current build” queues a rebuild.

The console:

* Renders events in arrival order.
* On completion, shows a **build summary** with status and any backend‑provided message.

Keyboard shortcuts (wired in workbench chrome):

* ⌘B / Ctrl+B → default build behaviour.
* ⇧⌘B / Ctrl+Shift+B → force rebuild.

### 7.2 Run streams (validation and test modes)

The **Run extraction** button in the workbench:

* Opens a dialog that lets the user choose a document and optionally sheet names.
* On confirm, starts a run (using the current configuration) with `RunOptions`
  (camelCase → snake_case) and streams events into the console.

Validation runs:

* The **Validation run** action triggers a run with `RunOptions.validateOnly:
  true` (often `mode: "validation"`).
* While running:

  * Console shows streamed events.
* On completion:

  * Structured issues are extracted and displayed in the Validation tab.

Error handling:

* Stream setup failures → inline message in console.
* Validation errors → top‑level error in Validation tab plus any partial issues.

---

## 8. Editor and theme

The workbench uses a shared Monaco wrapper component and per‑configuration theme preferences.

### 8.1 CodeEditor

`CodeEditor` lives in `src/ui` and wraps Monaco:

```ts
interface CodeEditorProps {
  value: string;
  language?: string;
  path?: string;                 // used as Monaco model id
  theme: EditorThemeId;          // "ade-dark" | "vs-light"
  readOnly?: boolean;
  onChange?: (value: string) => void;
  onSaveShortcut?: () => void;   // ⌘S / Ctrl+S
}
```

Imperative handle:

```ts
interface CodeEditorHandle {
  focus(): void;
  revealLine(lineNumber: number): void;
}
```

Workbench integration:

* Binds `value`/`onChange` to the active `WorkbenchFileTab`.
* Uses `path = tab.id` so Monaco can keep per‑file state.
* Binds `onSaveShortcut` to the workbench’s save routine.
* Uses the resolved `EditorThemeId` from preferences (see below).

### 8.2 Theme preference

Editor theme is controlled separately from any global app theme.

Types:

```ts
export type EditorThemePreference = "system" | "light" | "dark";
export type EditorThemeId = "ade-dark" | "vs-light";
```

Hook:

* `useEditorThemePreference(workspaceId, configurationId)`:

  * Storage key:

    ```text
    ade.ui.workspace.<workspaceId>.configuration.<configurationId>.editor-theme
    ```

  * Returns:

    * `preference: EditorThemePreference`
    * `setPreference(next: EditorThemePreference)`
    * `resolvedTheme: EditorThemeId`

* Resolution rules:

  * `"light"` → `vs-light`.
  * `"dark"` → `ade-dark`.
  * `"system"` → `ade-dark` or `vs-light` based on `prefers-color-scheme`.

Monaco setup:

* `ade-dark` is a custom dark theme registered once.
* `vs-light` is reused as the light theme.

---

## 9. ADE scripting helpers

To make configuration editing safer and more discoverable, the workbench augments Monaco with ADE‑aware helpers.

### 9.1 Goals

* Make the correct **entrypoint signatures** easy to use.
* Provide **inline documentation** (hover, signature help) where scripts are written.
* Avoid hard coupling to backend implementation; helpers are guidance, not validation.

### 9.2 Scope detection

Helpers are activated based on the virtual path of the file being edited:

* `ade_config/row_detectors/*.py` → row detector helpers.
* `ade_config/column_detectors/*.py` → column‑level helpers (detectors, transforms, validators).
* `ade_config/hooks/*.py` → run hooks.

`registerAdeScriptHelpers(monaco)`:

* Registers providers for the `python` language.
* Uses `model.uri.path` (or similar) to determine category.
* Injects hover, completion, and signature help based on that category.

### 9.3 Function specification model

Helper metadata is described with a simple specification structure, conceptually:

```ts
interface AdeParamSpec {
  name: string;
  type: string;
  description?: string;
  optional?: boolean;
}

interface AdeFunctionSpec {
  name: string;
  kind: "row-detector" | "column-detector" | "transform" | "validator" | "hook";
  description?: string;
  params: AdeParamSpec[];
  returns?: string;         // description of returned value
  examples?: string[];      // sample snippets
}
```

This drives:

* **Hover** – show signature and description on function definitions and usages.
* **Completion** – snippet completions for common entrypoints.
* **Signature help** – parameter hints while typing calls.

### 9.4 Row detectors

In `row_detectors/*.py`, helpers expect row detector functions of the form:

```python
def detect_*(
    *,
    run,
    state,
    row_index: int,
    row_values: list,
    logger,
    **_,
) -> dict:
    ...
```

Key ideas:

* Keyword‑only parameters for clarity.
* `run`: run context (ids, environment, manifest).
* `state`: mutable state shared across the run.
* `row_index` / `row_values`: current row.
* `logger`: run‑scoped logger.

Helpers provide:

* Hover with human explanations of each parameter.
* Completions like `detect_header_row` with template bodies.
* Signature help when calling helper utilities from within detectors.

### 9.5 Column detectors, transforms, validators

In `column_detectors/*.py`, helpers support three primary entrypoints.

**Detector:**

```python
def detect_*(
    *,
    run,
    state,
    field_name: str,
    field_meta: dict,
    header: str | None,
    column_values_sample: list,
    column_values: tuple,
    table: dict,
    column_index: int,
    logger,
    **_,
) -> dict:
    ...
```

**Transform:**

```python
def transform(
    *,
    run,
    state,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    logger,
    **_,
) -> dict | None:
    ...
```

**Validator:**

```python
def validate(
    *,
    run,
    state,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_meta: dict | None,
    logger,
    **_,
) -> list[dict]:
    ...
```

Helpers:

* Explain what `field_meta`, `column_values_sample`, `row`, etc. contain.
* Describe expected return values (e.g. score dicts, normalized values, validation issue objects).
* Provide snippets with correctly ordered parameters.

### 9.6 Run hooks

In `hooks/*.py`, helpers focus on **run‑level** hooks.

Typical signatures:

```python
def on_run_start(
    *,
    run_id: str,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    logger=None,
    **_,
) -> None:
    ...

def after_mapping(
    *,
    table: dict,
    manifest: dict,
    env: dict | None = None,
    logger=None,
    **_,
) -> dict:
    ...

def before_save(
    *,
    workbook,
    artifact: dict | None = None,
    logger=None,
    **_,
):
    ...

def on_run_end(
    *,
    artifact: dict | None = None,
    logger=None,
    **_,
) -> None:
    ...
```

Helpers:

* Describe **when** each hook is called in the run lifecycle.
* Clarify shapes of `manifest`, `env`, `artifact`.
* Provide skeleton hook implementations with appropriate TODOs.

### 9.7 Extending helpers

To add support for new script categories or entrypoints:

1. Add new `AdeFunctionSpec` definitions describing names, parameters, returns, and examples.
2. Extend the path‑based scope detection to cover new folders (e.g. `table_detectors/`).
3. Register additional Monaco providers if new language features are needed.

The intent is to keep helper metadata central and declarative; the Monaco integration should not need to know ADE internals.

---

## 10. Evolution guidelines

When evolving the workbench, keep these principles in mind:

* **Stable state shapes**
  Types like `WorkbenchFileNode`, `WorkbenchFileTab`, `ConfigBuilderSearchState`, and `ConsolePanelPreferences` are part of the architecture. Changes should be deliberate, versioned, and reflected in this doc.

* **Separation of concerns**

  * Layout components (Explorer, Editor, Console, Inspector) should not call the backend directly.
  * All IO should flow through API modules and state hooks (`useWorkbenchFiles`, streaming helpers).

* **URL vs preferences**

  * Use query parameters for state that affects navigation and deep linking (`file`, `pane`, `console`).
  * Use local storage for user preferences (which tabs are open, MRU order, panel sizes, editor theme).

* **Navigation safety**

  * Any feature that can produce unsaved edits should participate in navigation blocking.
  * Only block true page changes; let query/hash changes proceed.

* **Scripting surface as contract**

  * Treat the documented ADE entrypoints and parameters as a public contract for configuration authors.
  * Update helper specs and this doc together when those contracts change.

This document is the source of truth for the workbench editor and scripting architecture. If implementation diverges, update the implementation *and* this file together so future developers and agents can reason about `ade-web` without guesswork.
