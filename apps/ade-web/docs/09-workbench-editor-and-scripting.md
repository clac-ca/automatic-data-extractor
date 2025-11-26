# 09 – Workbench editor and scripting

The **Configuration Builder workbench** is the dedicated editing surface for ADE configuration packages and for kicking off validation/test runs in the browser.

* “**Workbench**” = the whole editing window (panels, tabs, console, etc.).
* “**Editor**” = specifically the Monaco editor instance.

This doc is for people working on `ade-web` internals. It explains how the workbench is wired so that humans **and agents** can safely reason about it and extend it.

> Configuration lifecycle, manifests, and terminology (e.g. “run”) are defined in:
>
> * `01-domain-model-and-naming.md`
> * `07-documents-and-runs.md` (canonical `RunOptions`)
> * `08-configurations-and-config-builder.md`
> * `apps/ade-web/docs/04-data-layer-and-backend-contracts.md` and
>   `apps/ade-engine/docs/11-ade-event-model.md` (event schemas)

Workbench run actions always use the canonical **`RunOptions`** shape (camelCase:
`dryRun`, `validateOnly`, `forceRebuild`, `inputSheetNames`, optional `mode`) and then convert to backend snake_case fields.
Environment builds stay as backend `Build` entities but are triggered automatically when runs start if:

* the environment is missing or stale,
* the environment was built from outdated content, or
* the user explicitly requested `force_rebuild`.

Validation runs and test runs are always `Run` entities.

---

## 1. What the workbench is scoped to

A workbench session is always scoped to **exactly one configuration in one workspace**.

* **Session identity**

  ```ts
  type WorkbenchSessionKey = {
    workspaceId: string;
    configurationId: string;
  };
  ```

* In any given browser tab there is at most **one active workbench** for a given `(workspaceId, configurationId)`.

* Session‑scoped state includes (non‑persisted unless stated otherwise):

  * Window state (restored / maximized / docked).
  * Open tabs, pinning, and MRU order (persisted).
  * Console open/closed + height (persisted).
  * Editor theme preference (persisted).
  * URL state (shareable).

### 1.1 Entering and exiting the workbench

Typical entry flow:

1. User clicks **“Open in workbench”** (may be labelled “Open editor”) from the Configuration Builder screen.
2. The *current* URL is captured as the **return path** and stored under:

   ```text
   ade.ui.workspace.<workspaceId>.workbench.returnPath
   ```

On exit:

* The **close** action:

  * Checks for unsaved changes (see §1.3).
  * If the user is allowed to leave:

    * Navigates back to the stored return path, if it still exists.
    * Otherwise falls back to the Configuration Builder screen.
  * Clears the stored return path key.

This keeps the workbench feeling like a “modal workspace” on top of the existing navigation, not a separate app.

### 1.2 Window states

The workbench can appear in three **window states**:

```ts
type WorkbenchWindowState = "restored" | "maximized" | "docked";

interface WorkbenchWindowContextValue {
  state: WorkbenchWindowState;
  setState(next: WorkbenchWindowState): void;
  close(): void; // respects unsaved-change guards
}
```

* **Restored**

  * Workbench is embedded in the Configuration Builder section.
  * Workspace shell (top bar, left nav) is fully visible and usable.

* **Maximized**

  * Workbench covers the full viewport.
  * Workspace shell is visually dimmed and effectively disabled.
  * Body scroll is locked to prevent scroll bleed.

* **Docked**

  * Workbench UI is hidden.
  * A small “docked workbench” affordance appears on the Configuration Builder screen and brings it back to `restored`.

Window state is **session‑local only** and not persisted. On reload we always start in `restored` to avoid surprise full‑screen takeovers.

### 1.3 Unsaved changes and navigation blocking

The workbench uses a navigation blocker (e.g. `useNavigationBlocker`) to avoid accidental loss of edits.

* A **tab** is dirty if:

  ```ts
  const isDirty = tab.content !== tab.initialContent;
  ```

* A **session** is dirty if *any* tab is dirty.

While dirty:

* Any navigation that changes the **pathname** is intercepted:

  * Switching workspace sections.
  * Leaving the workspace.
  * Closing the workbench.
  * Browser back/forward to another page.

* The user is shown a confirmation dialog:

  * If they confirm:

    * The blocker is temporarily disabled.
    * The attempted navigation is retried.
  * If they cancel:

    * Navigation is cancelled.
    * URL is restored to the previous location.

Navigation that only changes **search** (query params) or **hash** is allowed. This keeps URL‑encoded state responsive (e.g. switching console pane) without triggering spurious warnings.

---

## 2. Layout overview

The workbench mimics familiar IDE/editor layouts so new users can orient fast:

```text
+-------------------------------------------------------------+
| Activity |           Editor & Tabs                          |
|   Bar    |                                                 |
|         Explorer     Editor       Inspector                |
|         Panel        Area         Panel                    |
|                       |             |                      |
|                       |             |                      |
+-----------------------+-------------+----------------------+
|                       Console / Validation                 |
+-------------------------------------------------------------+
```

High‑level pieces:

1. **Activity bar** — left vertical mode switcher.
2. **Explorer** — configuration file tree.
3. **Editor & tabs** — Monaco editor + tab strip.
4. **Inspector** — metadata about the active file.
5. **Console / Validation** — bottom panel for run output and validation issues.

### 2.1 Activity bar

Leftmost vertical strip; picks the workbench “mode”:

* **Explorer** – configuration file tree (implemented).
* **Search** – reserved for in‑configuration search.
* **SCM** – reserved for source control.
* **Extensions** – reserved for extensibility.
* **Settings** (gear) – workbench preferences (e.g. theme).

Currently only **Explorer** is hooked up; others are placeholders but should be treated as reserved affordances.

### 2.2 Explorer panel

The Explorer shows the **configuration package file tree**:

* Renders `WorkbenchFileNode` trees (see §3).
* Highlights the active file.
* Marks open files (e.g. via dot, italics, or similar).
* Provides a right‑click `ContextMenu` that can include:

  * Open in new tab.
  * Copy path.
  * Create / rename / delete file/folder (if supported by backend).
  * Close related tabs.

Selecting a file:

1. Opens a tab if it isn’t open yet.
2. Activates that tab if it is.
3. Updates the URL `file` query parameter (see §5).

### 2.3 Editor and tab strip

The center pane hosts the Monaco editor and tab strip.

* **Tab strip**

  * Pinned tabs are grouped on the left.
  * Dirty tabs have a visual marker (e.g. dot, italic, or pilcrow).
  * Right‑click menu supports:

    * Close
    * Close others
    * Close to the right
    * Pin / unpin
  * Keyboard navigation uses **MRU** order for Ctrl+Tab / ⌘Tab (not visual left‑to‑right).

* **Editor**

  * Uses the shared `CodeEditor` component (see §8).
  * Binds ⌘S / Ctrl+S to the **save** action for the active tab.
  * Uses the resolved editor theme for the `(workspaceId, configurationId)` pair.
  * Applies language‑appropriate syntax highlighting (`language` from the tab/file).

### 2.4 Inspector (right sidebar)

The **Inspector** is an optional right sidebar that shows metadata for the current file:

* Path and display name.
* Size and last modified timestamp.
* Content type and ETag.
* Load state (loading / ready / error).
* Dirty vs saved.
* Last saved timestamp.

The inspector is **read‑only**: it never modifies file content.

### 2.5 Console / Validation panel (bottom)

The bottom panel can be toggled and resized. It has two logical tabs:

* **Console**

  * Shows streamed text logs for runs, including any environment build output.
  * Shows status of the last run (running, succeeded, failed).
  * Renders a **run summary** after completion, including where available:

    * Run ID.
    * Document and sheet names used.
    * Basic metrics (rows processed, warnings, errors).
    * Links to telemetry and logs.

* **Validation**

  * Shows structured validation issues when a run is executed in “validation mode” (`RunOptions.validateOnly: true`).

  * Issues are represented as:

    ```ts
    interface ValidationIssue {
      severity: "error" | "warning" | "info";
      message: string;
      file?: string;
      line?: number;
      column?: number;
      path?: string; // manifest/config path
    }
    ```

  * Issues can be grouped (e.g. by file, table, or severity).

  * Clicking an issue:

    * Opens the relevant file tab (if needed).
    * Activates it.
    * Optionally scrolls the editor to the line/column.

The panel itself supports:

* **Open/closed** state (collapsed vs visible).
* **Draggable height**, stored as a fraction of available vertical space (see §6).

On very short viewports, the panel may auto‑collapse. We show a one‑time hint explaining that behavior.

---

## 3. File tree model

The workbench maintains an in‑memory, typed representation of the configuration package.

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
* `kind: "folder"` nodes may have `children`; `kind: "file"` nodes do not.
* Editable files should populate `language`; folders can leave it undefined.

### 3.2 Constructing the tree from backend listing

The backend exposes a **flat listing**, conceptually:

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

`createWorkbenchTreeFromListing(listing: FileListingEntry[]): WorkbenchFileNode` should:

1. **Normalize paths**

   * Strip trailing slashes.
   * Collapse `.` segments and redundant separators.

2. **Ensure folder structure**

   * Ensure folder nodes exist for all `parent` paths.

3. **Create nodes**

   * For `kind === "dir"`: ensure a folder node exists.
   * For `kind === "file"`: create a file node with metadata.
   * Infer `language` from the filename extension, e.g.:

     * `.py` → `python`
     * `.json` → `json`
     * `.md` → `markdown`

4. **Sort children**

   * Folders before files.
   * Alphabetically by `name` (case‑insensitive) within each group.

Useful helpers:

```ts
extractName(path: string): string;  // basename
deriveParent(path: string): string; // parent or "" for root
findFileNode(root: WorkbenchFileNode, id: string): WorkbenchFileNode | undefined;
findFirstFile(root: WorkbenchFileNode): WorkbenchFileNode | undefined;
```

### 3.3 Tree operations

The tree structure itself is **pure**; it doesn’t call the backend. All side‑effects go through API modules.

Common operations:

* **File selection**

  * Find node by `id`.
  * Open/activate the corresponding tab.
  * Update URL `file` query parameter.

* **Refresh listing**

  * Fetch listing from backend.
  * Rebuild the tree.
  * Try to preserve:

    * Selected file.
    * Open tabs (see §4.3).

* **Create / rename / delete**

  * Call configuration file endpoints.
  * Then either:

    * Refresh listing, or
    * Apply an incremental patch to the tree.

---

## 4. Tabs, file content, and persistence

Tabs are the main editing unit: **one open file = one tab**.

### 4.1 Tab model

```ts
export type WorkbenchFileTabStatus = "loading" | "ready" | "error";

export interface WorkbenchFileTab {
  id: string;                   // file id / path
  name: string;                 // display label
  language?: string;
  initialContent: string;       // last saved content
  content: string;              // current editor content
  status: WorkbenchFileTabStatus;
  error?: string | null;        // load error
  etag?: string | null;         // concurrency token
  metadata?: WorkbenchFileMetadata | null;
  pinned?: boolean;
  saving?: boolean;
  saveError?: string | null;    // last save error, if any
  lastSavedAt?: string | null;  // ISO timestamp of last successful save
}
```

Dirty state is derived:

```ts
const isDirty = tab.content !== tab.initialContent;
```

### 4.2 `useWorkbenchFiles`: responsibilities

A dedicated hook (e.g. `useWorkbenchFiles`) manages tab state and IO:

* **Open file**

  * If tab already exists, just activate it.
  * Otherwise:

    * Add a new tab with `status: "loading"`.
    * Fetch content & metadata via `GET /files/{file_path}`.
    * On success:

      * Set `initialContent`, `content`, `etag`, `metadata`.
      * Set `status: "ready"`.
    * On failure:

      * Set `status: "error"` and an `error` message.

* **Edit content**

  * Hook `onChange` from the editor to update `content`.
  * Dirty state is recomputed from `content` and `initialContent`.

* **Save**

  * No‑op if the tab is not dirty.
  * Otherwise:

    * Send `content` to backend via `PUT /files/{file_path}`, using `etag` as a precondition when supported.
    * On success:

      * Set `initialContent = content`.
      * Update `etag`.
      * Update `metadata.modifiedAt` and `lastSavedAt`.
      * Clear `saveError`.
    * On concurrency conflict:

      * Do **not** overwrite server content.
      * Keep current `content`.
      * Set `saveError` with a clear conflict explanation.

* **Close tabs**

  * Close single tab, all others, to the right, etc.
  * If any tab to be closed is dirty, prompt first (reusing the unsaved‑changes logic).

* **Pin / unpin**

  * Toggle `pinned`.
  * Tab strip groups pinned tabs to the left.

* **MRU tracking**

  * Maintain an MRU list of tab IDs.
  * When a tab becomes active, move its ID to the front.
  * Keyboard shortcuts (Ctrl+Tab / ⌘Tab) iterate through MRU order, not physical order.

### 4.3 Tab persistence

We persist **which tabs** are open and their pinning/MRU metadata, but **not** file contents (authoritative source of truth is the configuration package).

Persisted shape:

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

Hydration on load:

1. Read the snapshot (if any).
2. Filter out files that no longer exist in the current file tree.
3. For each remaining file:

   * Create a tab object (content will be loaded lazily).
   * Apply `pinned` flags as stored.
4. Restore `activeTabId` if still valid.
5. Restore MRU order for keyboard shortcuts.

Any tab change (open/close, pin/unpin, active tab change) writes a fresh snapshot to local storage.

---

## 5. Workbench URL state

URL query parameters encode **shareable view state**—the bits we want to survive refresh, deep linking, and copy‑pasting.

### 5.1 Search state model

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

`readConfigBuilderSearch(source)` returns a **normalized** snapshot:

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

Responsibilities:

* Parse the search string / `URLSearchParams`.
* Map invalid or unknown values back to defaults.
* Support legacy `path` → `file` mapping for backwards compatibility.
* Record which keys were explicitly present under `present.*`.

### 5.3 Writing to the URL

`mergeConfigBuilderSearch(currentParams, patch)`:

1. Reads the current state via `readConfigBuilderSearch`.
2. Merges:

   * Hard defaults,
   * Current state,
   * Given `patch`.
3. Produces new `URLSearchParams` by:

   * Removing all builder‑related keys (`tab`, `pane`, `console`, `view`, `file`, `path`).
   * Writing new keys **only when they differ from defaults**.
   * Omitting `file` when empty.

This keeps URLs stable and short, while still encoding meaningful view state.

### 5.4 `useWorkbenchUrlState`

A small hook wraps `useSearchParams` and the helpers:

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

Behavior:

* `fileId` is derived from the `file` query parameter.

* `setFileId`, `setPane`, `setConsole`:

  * No‑op when the value is unchanged.
  * Use `mergeConfigBuilderSearch` to compute new params.
  * Call `setSearchParams(next, { replace: true })` to avoid polluting history.

* `consoleExplicit` is `true` when the URL explicitly contains a `console` key (`present.console`):

  * When **true**, the URL’s `console` state overrides any persisted preferences for the initial state.
  * When **false**, stored console preferences determine initial open/closed state (see §6).

---

## 6. Console panel preferences

The console panel has its own local preferences, separate from URL state.

### 6.1 Preference model

```ts
interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number;              // 0–1 of vertical space
  readonly state: ConfigBuilderConsole;   // "open" | "closed"
}
```

Storage key:

```text
ade.ui.workspace.<workspaceId>.configuration.<configurationId>.console
```

Hydration:

1. Read stored preferences (if any).
2. If `version` mismatch → ignore; use defaults.
3. If `consoleExplicit` from URL is `true`:

   * Override `state` with the URL value.
4. Else, keep stored `state`.

User actions:

* **Resize**

  * On drag, update `fraction` and persist.

* **Open/close**

  * On toggle, update `state` and persist.

Rule of thumb:

* **URL**: what we want to share or deep link.
* **Preferences**: what the user wants to see “by default” when there’s no explicit URL.

---

## 7. Runs, streams, and environment readiness

The workbench wires run actions to stream events into the console/validation panel. There is no separate “build” button; environment readiness is handled as part of run startup.

### 7.1 RunOptions and environment behavior

All workbench run actions use the canonical `RunOptions` shape (see `07-documents-and-runs.md`) in camelCase and convert to backend snake_case. Fields include:

* `dryRun`
* `validateOnly`
* `forceRebuild`
* `inputSheetNames`
* Optional `mode` (e.g. `"validation"`)

Environment builds remain `Build` entities on the backend, but are triggered automatically at run start if:

* the environment is missing,
* stale,
* built from outdated content, or
* `force_rebuild: true` is set (e.g. user chooses **Force build and test**).

### 7.2 Test runs

The **Test** split button in the workbench:

1. Opens a dialog where the user selects:

   * A document.
   * Optional sheet names.
2. On confirm:

   * Builds a `RunOptions` object.
   * Sends a run request to the backend (camelCase → snake_case).
   * Starts streaming events to the **Console**.
   * Includes `force_rebuild: true` if the user selected that option.

The console shows:

* Streaming log lines.
* Current run status.
* Summary information once the run completes.

### 7.3 Validation runs

The **Validation run** action executes a run with:

* `RunOptions.validateOnly: true`
* Typically also `mode: "validation"`

While the run is active:

* Console shows streamed events.

On completion:

* Structured validation issues are extracted and shown in the **Validation** tab as `ValidationIssue` objects (see §2.5).
* The tab and console both reflect success/failure.

### 7.4 Stream errors

Error handling is intentionally explicit:

* Stream setup failures (connection errors, protocol mismatches, etc.) → inline message in the **Console**.
* Validation extraction failures → show a top‑level error in the **Validation** tab, plus any partial issues if available.

Low‑level event schemas are documented in:

* `apps/ade-web/docs/04-data-layer-and-backend-contracts.md` (see the run streaming section)
* `apps/ade-engine/docs/11-ade-event-model.md` (canonical event model)

---

## 8. Editor and theme handling

The workbench uses a shared Monaco wrapper component plus per‑configuration theme preferences.

### 8.1 `CodeEditor` component

`CodeEditor` lives under `src/ui` and wraps the Monaco editor. Its props:

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

* `value`/`onChange` are wired to the active `WorkbenchFileTab`.
* `path` is set to `tab.id` so Monaco keeps per‑file state (undo stack, markers).
* `onSaveShortcut` calls the workbench’s save handler.
* `theme` is the resolved `EditorThemeId` from preferences (see below).

### 8.2 Theme preference

The editor theme is separate from any global app theme.

Types:

```ts
export type EditorThemePreference = "system" | "light" | "dark";
export type EditorThemeId = "ade-dark" | "vs-light";
```

Hook:

```ts
useEditorThemePreference(workspaceId, configurationId);
```

* Storage key:

  ```text
  ade.ui.workspace.<workspaceId>.configuration.<configurationId>.editor-theme
  ```

* Returns:

  * `preference: EditorThemePreference`
  * `setPreference(next: EditorThemePreference)`
  * `resolvedTheme: EditorThemeId`

Resolution rules:

* `"light"` → `vs-light`
* `"dark"` → `ade-dark`
* `"system"` → choose based on `prefers-color-scheme`:

  * dark → `ade-dark`
  * light → `vs-light`

Monaco configuration:

* `ade-dark` is a custom registered theme.
* `vs-light` is the default light theme.

---

## 9. ADE scripting helpers

The workbench extends Monaco with **ADE‑aware scripting helpers** for Python code in configuration packages. These helpers are **guidance** (hover, completion, snippets), not hard validation.

### 9.1 Goals

Helpers are designed to:

* Make the right **entrypoint signatures** easy to discover and reuse.
* Provide **inline documentation** (hover, parameter hints) where authors actually write scripts.
* Keep helpers **decoupled** from backend implementation details — the contract is “what configuration authors should write,” not how the engine executes it.

### 9.2 Scope detection (which helpers apply where)

Helpers are activated based on the file’s path in the configuration package.

Examples:

* `ade_config/row_detectors/*.py` → row detector helpers.
* `ade_config/column_detectors/*.py` → column‑level helpers:

  * column detectors
  * transforms
  * validators
* `ade_config/hooks/*.py` → run hooks.

`registerAdeScriptHelpers(monaco)`:

* Registers providers for language `"python"`.
* Uses `model.uri.path` (or equivalent) to infer category (row detector, column, hook, etc.).
* Attaches hover, completion, and signature help providers based on that category.

### 9.3 Function specification model

Helper metadata is captured via simple spec structures, conceptually:

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
  returns?: string;         // description of return value
  examples?: string[];      // sample code snippets
}
```

These specs drive:

* **Hover**: show signature + description on definitions and usages.
* **Completion items**: snippet templates for common entrypoints.
* **Signature help**: parameter info while author types calls.

### 9.4 Row detectors

For files under `ade_config/row_detectors/*.py`, helpers expect detector entrypoints like:

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

Key parameters (documented via helpers):

* `run` — run context (ids, environment, manifest).
* `state` — mutable state shared across the run.
* `row_index` — current row index (0‑based or documented accordingly).
* `row_values` — raw values for the current row.
* `logger` — run‑scoped logger.
* `**_` — catch‑all for unused keyword arguments.

Helpers:

* Provide completions for patterns like `detect_header_row`.
* Show parameter descriptions on hover.
* Offer signature help when using supporting utilities.

### 9.5 Column detectors, transforms, validators

In `ade_config/column_detectors/*.py`, helpers support three main entrypoints.

**Column detector:**

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

Helpers clarify:

* What `field_meta` contains.
* How `column_values_sample` differs from `column_values`.
* What shape `row` and `table` have.
* Expected return shapes:

  * detectors → e.g. classification/score dicts.
  * transforms → possibly modified dict or `None`.
  * validators → list of issue dicts.

They also provide:

* Snippet completions with parameters in the correct order.
* Hover documentation explaining when and how each entrypoint is invoked.

### 9.6 Run hooks

For files under `ade_config/hooks/*.py`, helpers cover **run lifecycle hooks**, including (but not limited to):

```python
def on_run_start(
    *,
    run_id: str,
    manifest: dict,
    env: dict | None = None,
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
    logger=None,
    **_,
):
    ...

def on_run_end(
    *,
    tables=None,
    logger=None,
    **_,
) -> None:
    ...
```

Helpers explain:

* **When** each hook fires in the run lifecycle.
* **What** `manifest`, `env`, `table`, and `workbook` look like at that moment.
* How return values are interpreted (e.g. whether a hook is allowed to mutate or replace a structure).

Typical UX:

* Skeleton implementations with TODOs are offered as snippet completions.
* Hover shows lifecycle timing (e.g. “Called once at the start of a run”).

### 9.7 Extending helper coverage

To add support for new script types or entrypoints:

1. Add one or more `AdeFunctionSpec` definitions describing:

   * Function name.
   * `kind`.
   * Parameters (names, types, descriptions).
   * Return description.
   * Example snippets.
2. Extend path‑based detection to recognize new folders or naming schemes (e.g. `ade_config/table_detectors/*.py`).
3. Hook the new specs into the existing Monaco providers (hover, completion, signature help).

The goal is to keep the **metadata declarative and centralized**; the Monaco integration should remain thin glue.

---

## 10. Evolution guidelines

When extending or refactoring the workbench, keep these principles in mind:

* **Stable state shapes**

  Types like:

  * `WorkbenchFileNode`
  * `WorkbenchFileTab`
  * `ConfigBuilderSearchState`
  * `ConsolePanelPreferences`

  are effectively **architectural contracts**. If they change, update:

  1. The type definitions.
  2. This document.
  3. Any persistence/versioning logic.

* **Separation of concerns**

  * Layout components (Explorer, Editor, Console, Inspector) should not talk directly to the backend.
  * All IO goes through:

    * API modules (REST clients, streaming helpers).
    * State hooks (`useWorkbenchFiles`, run streaming hooks, etc.).

* **URL vs preferences**

  * Use **URL query parameters** for state that impacts navigation and deep linking:

    * `file`, `pane`, `console`, `view`.
  * Use **local storage** for per‑user, per‑configuration preferences:

    * Open tabs, pinning, MRU.
    * Panel sizes.
    * Editor theme.
    * Console open/closed default.

* **Navigation safety**

  * Any feature that can create unsaved edits must participate in navigation blocking.
  * Only block when the **page** changes (pathname); let query/hash changes pass to keep things snappy.

* **Scripting surface as contract**

  * Treat documented ADE entrypoints and parameters as a public contract for configuration authors.
  * When contracts change:

    * Update scripting helper specs.
    * Update backend acceptance.
    * Update this doc in the same change.

This document is the **source of truth** for the workbench editor and scripting architecture. If implementation diverges, fix both the code and this file so that future maintainers (and agents) never have to guess how the workbench is supposed to behave.
