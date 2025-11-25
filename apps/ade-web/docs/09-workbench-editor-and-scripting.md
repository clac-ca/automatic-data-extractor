# 09 – Workbench editor and scripting

The **Config Builder workbench** is an IDE‑style surface for editing ADE config packages inside the browser.

This doc explains:

- What the workbench is responsible for (and what it is not).
- How the workbench window, layout, file tree, tabs, and URL state fit together.
- How build/validation consoles are wired.
- How the Monaco editor is configured and extended with **ADE scripting helpers**.

It assumes you’ve read:

- `01-domain-model-and-naming.md` – for terminology (`Configuration`, `Config version`, `Job`, etc.).
- `08-configurations-and-config-builder.md` – for the higher‑level configuration flows.

---

## 1. Responsibilities and high‑level architecture

The workbench has a clear, narrow purpose:

> **Edit one configuration’s files and run builds/validations for that configuration.**

It **does not**:

- Own configuration metadata (name, lifecycle, active version, etc.).
- Decide which configuration is active.
- Manage workspace‑level concerns (documents, jobs, members).

At a high level:

```text
ConfigBuilderScreen
  └─ WorkbenchWindowProvider
      ├─ WorkbenchChrome          # window controls & activity bar
      ├─ WorkbenchLayout          # panels & resize logic
      │   ├─ WorkbenchExplorer    # file tree
      │   ├─ WorkbenchEditorArea  # tabs + CodeEditor
      │   ├─ WorkbenchConsole     # logs + run/build summary
      │   └─ WorkbenchInspector   # file metadata / status
      └─ WorkbenchUrlState        # bridge to URL search params
````

Key design choices:

* **Single source of truth per concern:**

  * Open files, dirty state → `useWorkbenchFiles`.
  * Layout & window state → `WorkbenchWindow` context.
  * URL state → `useWorkbenchUrlState` + query params.
* **Config‑scoped persistence:** all preferences (tabs, console height, theme) are keyed by `(workspaceId, configId)`.

---

## 2. Window model

The workbench window behaves like an IDE window inside the workspace shell. It can be in one of three visual states:

* **Restored** – appears inline inside the Config Builder section.
* **Maximised** – consumes the entire viewport; shell is dimmed.
* **Docked (minimised)** – hidden from the main Config Builder content but still “open” in the background.

### 2.1 State and transitions

The window state is owned by a `WorkbenchWindow` context, exposed via a hook:

```ts
type WorkbenchWindowState = "restored" | "maximized" | "docked";

interface WorkbenchWindowContextValue {
  state: WorkbenchWindowState;
  setState: (next: WorkbenchWindowState) => void;
  close: () => void; // respects unsaved-changes guards
}
```

Transitions:

* `restored → maximized` when the user clicks “Maximize”.
* `maximized → restored` on “Restore” or when the user exits immersive mode.
* `restored → docked` when the user clicks “Minimize”.
* `docked → restored` when the user re‑opens the workbench from the Config Builder screen.

The `close()` method:

* Closes the workbench session for the current configuration.
* Uses navigation blockers (see `03-routing-navigation-and-url-state.md`) to guard against unsaved changes.
* After closing, the Config Builder screen remains, showing the configuration list or overview.

### 2.2 Invariants

* At most **one** workbench is active for a given configuration in a workspace.
* Workbench state is **scoped** to `(workspaceId, configId)`; switching configurations tears down the previous state.
* Window state itself is **not persisted** across reloads; the workbench always starts in `restored` mode to avoid surprising users. (Layout and console/theme preferences are persisted separately.)

---

## 3. Layout and panels

The workbench layout is meant to feel familiar to users of modern editors:

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

### 3.1 Activity bar

* Vertical bar on the far left.
* Mode icons (current: **Explorer**; future: Search, SCM, Extensions).
* A gear/menu icon at the bottom for workbench‑specific settings.

Currently, only the **Explorer** mode is implemented; others are reserved.

### 3.2 Panels

Each panel has a single responsibility:

* **Explorer panel** (`WorkbenchExplorer`)

  * Displays the config file tree.
  * Drives which file is opened when the user clicks a node.
  * Hosts context menus (open in new tab, copy path, rename, delete, etc.).

* **Editor area** (`WorkbenchEditorArea`)

  * Tab strip (pinned and regular tabs).
  * `CodeEditor` instance for the active file.
  * Responsible for wiring save shortcuts (`⌘S` / `Ctrl+S`).

* **Console panel** (`WorkbenchConsole`)

  * Shows streaming build and run logs.
  * Shows a run/build summary card at the end of streams.

* **Validation panel** (`ValidationPane`)

  * Displays structured validation issues.
  * Issues can be grouped by file and severity.

* **Inspector panel** (`WorkbenchInspector`)

  * File metadata (size, modifiedAt, contentType, ETag).
  * Load status (loading / ready / error).
  * Dirty state / last saved timestamp.

### 3.3 Resizing and layout preferences

Resizing is implemented via draggable splitters:

* Horizontal: editor area vs console/validation.
* Vertical: explorer vs editor vs inspector (optional).

Preferences:

* Stored as fractional widths/heights in a `(workspaceId, configId)`‑scoped structure (see `ConsolePanelPreferences` for console height in section 7).
* Minimum/maximum sizes are enforced to keep the editor usable (e.g. the console can’t take more than ~70% of vertical height, and the explorer can’t shrink to 0).

Auto‑collapse:

* On very short viewports, the console may auto‑collapse on load to preserve vertical space.
* A banner in the workbench explains that the console was closed automatically and can be reopened.

---

## 4. File tree representation

The workbench models a configuration’s file system as a tree of `WorkbenchFileNode` objects.

### 4.1 Types

```ts
export type WorkbenchFileKind = "file" | "folder";

export interface WorkbenchFileMetadata {
  size?: number | null;
  modifiedAt?: string | null; // ISO timestamp
  contentType?: string | null;
  etag?: string | null;
}

export interface WorkbenchFileNode {
  id: string;          // canonical path, e.g. "ade_config/detectors/membership.py"
  name: string;        // display name, e.g. "membership.py"
  kind: WorkbenchFileKind;
  language?: string;   // editor language id, e.g. "python", "json", "markdown"
  children?: WorkbenchFileNode[];
  metadata?: WorkbenchFileMetadata | null;
}
```

Invariants:

* `id` is always a canonical path (no trailing slash, `/` separator).
* For `kind: "folder"`, `children` is always an array (possibly empty).
* For `kind: "file"`, `children` is omitted.

### 4.2 Building the tree from backend listing

The backend exposes a **flat listing** (e.g. `FileListing`) with entries like:

```ts
interface FileListingEntry {
  path: string;        // "ade_config/detectors/membership.py"
  name: string;        // "membership.py"
  parent: string;      // "ade_config/detectors"
  kind: "file" | "dir";
  depth: number;
  size?: number;
  mtime?: string;      // ISO timestamp
  content_type?: string;
  etag?: string;
}
```

`createWorkbenchTreeFromListing(listing: FileListingEntry[]): WorkbenchFileNode`:

1. Normalises all `path`/`parent` values (trim trailing slashes).
2. Derives a **root** path from the listing (`root`/`prefix` if provided, or the common ancestor).
3. Ensures intermediate folders exist (`ensureFolder(path)`).
4. Inserts folder nodes first, then file nodes.
5. Infers `language` based on file extension (`.py` → `python`, `.json` → `json`, etc.).
6. Sorts children via `compareNodes`:

   * Folders before files.
   * Alphabetical order within each group.

Common helpers:

* `extractName(path: string): string` – basename after final `/`.
* `deriveParent(path: string): string` – parent path or `""` for root.
* `findFileNode(root, id)` – depth‑first search by `id` for lookups.
* `findFirstFile(root)` – “first” file node in tree order (used to open an initial file).

---

## 5. Tabs, file content, and persistence

The workbench uses tabs to represent open files. Each tab tracks its own content state.

### 5.1 Tab model

```ts
export type WorkbenchFileTabStatus =
  | "loading"
  | "ready"
  | "error";

export interface WorkbenchFileTab {
  id: string;              // file id/path
  name: string;            // display name
  language?: string;
  initialContent: string;  // last saved content
  content: string;         // current editor content
  status: WorkbenchFileTabStatus;
  error?: string | null;   // load or save error
  etag?: string | null;    // for concurrency checks
  metadata?: WorkbenchFileMetadata | null;
  pinned?: boolean;
  saving?: boolean;
  saveError?: string | null;
  lastSavedAt?: string | null; // ISO timestamp
}
```

Dirty state is computed as `content !== initialContent`.

### 5.2 `useWorkbenchFiles` responsibilities

`useWorkbenchFiles` is the source of truth for open tabs and active file:

* Open/close tabs:

  * `openFile(fileId)`.
  * `closeTab(tabId)`, `closeOthers(tabId)`, `closeToTheRight(tabId)`, `closeAll()`.

* Active tab:

  * `activeTabId`, `setActiveTab(tabId)`.

* MRU order:

  * Maintains a list of recently used tab IDs for `Ctrl+Tab` / `⌘Tab` behaviour.

* Lazy loading:

  * When a file is opened:

    * Tab is created with `status: "loading"`.
    * Content is fetched from backend.
    * On success, `initialContent` and `content` set, `status: "ready"`.
    * On error, `status: "error"`, `error` populated.

* Saving:

  * `saveActiveFile()` or `saveFile(fileId)`:

    * Sends current `content` with `etag` to backend.
    * Handles concurrency (`412 Precondition Failed` or equivalent).
    * On success, updates `initialContent`, `etag`, `lastSavedAt`, and clears `saving`/errors.

### 5.3 Tabs persistence

To provide a “return where I left off” experience, the workbench persists **which files are open and pinned**, not the content itself.

```ts
export interface PersistedWorkbenchTabs {
  readonly openTabs: readonly (string | { id: string; pinned?: boolean })[];
  readonly activeTabId?: string | null;
  readonly mru?: readonly string[];
}
```

Storage:

* Key: `ade.ui.workspace.<workspaceId>.config.<configId>.tabs`.
* `openTabs` is a list of file IDs or objects (`{ id, pinned }`).
* On load:

  * The persisted list is filtered against the current file tree (missing files are dropped).
  * The first valid tab becomes active if `activeTabId` is missing or invalid.

This design keeps persistence **compact and robust** across file tree changes (e.g. if files are renamed or removed).

---

## 6. Workbench URL state

The workbench encodes part of its state in the URL, so views are linkable and restorable via browser navigation.

### 6.1 State model

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
  readonly file?: string; // file id/path
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

### 6.2 Reading search params

`readConfigBuilderSearch(source)`:

* Accepts a raw search string or `URLSearchParams`.

* Normalises values:

  * Invalid values fall back to defaults.
  * Legacy keys (e.g. `path`) are mapped to `file`.

* Returns:

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

The `present` flags indicate which keys were explicitly in the URL versus implied by defaults.

### 6.3 Merging state into the URL

`mergeConfigBuilderSearch(current, patch)`:

1. Reads existing state (`ConfigBuilderSearchSnapshot`).
2. Merges defaults, existing state, and `patch`.
3. Produces a new `URLSearchParams` where:

   * All builder‑related keys (`tab`, `pane`, `console`, `view`, `file`, legacy `path`) are cleared first.
   * Only non‑default values are written back.
   * `file` is omitted if empty.

Result:

* URLs stay **clean** (no redundant `tab=editor&pane=console&console=closed&view=editor`).
* Only meaningful differences from defaults are encoded.

### 6.4 `useWorkbenchUrlState` hook

`useWorkbenchUrlState` is the bridge between the workbench and `useSearchParams()`:

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

Behaviours:

* `consoleExplicit` is `true` if the URL explicitly sets the console state.

* When hydrating:

  * If `consoleExplicit` is `true`, URL state wins.
  * Otherwise, persisted `ConsolePanelPreferences` (see below) may override the default.

* Setter functions:

  * Guard against no‑ops.
  * Compute new search params via `mergeConfigBuilderSearch`.
  * Call `setSearchParams(next, { replace: true })` to avoid polluting browser history.

---

## 7. Console and validation pipeline

The bottom panel of the workbench surfaces build and run activity.

### 7.1 Console panel

The console is a generic **log stream viewer**:

* It subscribes to NDJSON event streams (build events, run events) via `shared/ndjson` helpers.
* It renders log messages in chronological order.
* It shows a **Run summary** card when the stream completes, including:

  * Build/run status.
  * Start/end timestamps and duration.
  * Document name and selected worksheets (for runs).
  * Links to outputs (artifact, telemetry, log files).

The console is **append‑only** per stream; new builds/runs create a new stream and new log entries.

### 7.2 Validation panel

The Validation panel displays structured issues from a `validate_only` run or configuration validation request:

* Each issue has:

  ```ts
  interface ValidationIssue {
    severity: "error" | "warning" | "info";
    message: string;
    file?: string;
    line?: number;
    column?: number;
    path?: string; // path within manifest or config object
  }
  ```

* Issues can be grouped by file or category.

* Clicking an issue can:

  * Focus the associated file in the explorer.
  * Open the file in a tab (if not already).
  * Optionally scroll the editor to the relevant line (if provided).

### 7.3 Console preferences

Console open/closed state and height are stored as:

```ts
interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number; // 0–1 portion of vertical height
  readonly state: ConfigBuilderConsole; // "open" | "closed"
}
```

Storage:

* Key: `ade.ui.workspace.<workspaceId>.config.<configId>.console`.

On load:

* If there is an explicit `console` value in URL (`consoleExplicit`), obey that.
* Otherwise:

  * Use persisted `state` and `fraction` if available.
  * Fallback to default console closed and default height.

---

## 8. Editor and theme

The editor is a thin wrapper around Monaco with ADE‑specific configuration.

### 8.1 `CodeEditor` component

`CodeEditor` is a reusable UI component that encapsulates Monaco setup:

```ts
export interface CodeEditorProps {
  language: string;            // "python", "json", "markdown", etc.
  path?: string;               // used by Monaco for model identity
  value: string;
  onChange: (value: string) => void;
  theme: EditorThemeId;        // "ade-dark" | "vs-light"
  readOnly?: boolean;
  onSaveShortcut?: () => void; // called for ⌘S / Ctrl+S
}

export interface CodeEditorHandle {
  focus(): void;
  revealLine(lineNumber: number): void;
}
```

Key behaviours:

* Lazy‑loads Monaco via `React.Suspense` to reduce initial bundle size.
* Wires platform‑appropriate save shortcut to `onSaveShortcut`.
* Accepts a `path` so Monaco can reuse models across re‑mounts.

### 8.2 Theme preference

Editor theme is controlled by:

```ts
export type EditorThemePreference = "system" | "light" | "dark";
export type EditorThemeId = "ade-dark" | "vs-light";
```

`useEditorThemePreference`:

* Reads stored preference from:

  * `ade.ui.workspace.<workspaceId>.config.<configId>.editor-theme`.

* If preference is `"system"`:

  * Uses `prefers-color-scheme: dark` media query to pick `ade-dark` or `vs-light`.

* Exposes:

  * `preference: EditorThemePreference`.
  * `resolvedTheme: EditorThemeId`.
  * `setPreference(next: EditorThemePreference)`.

Monaco themes:

* `ade-dark` is a custom dark theme tuned for ADE.
* `vs-light` is the default light theme.

---

## 9. ADE scripting helpers

To make it easier to write correct detectors, transforms, validators, and hooks, the workbench augments Monaco with **ADE scripting helpers**.

### 9.1 Scope‑aware helpers

`registerAdeScriptHelpers(monaco)` inspects the editor model’s virtual path (`path` prop) to decide which helpers to enable:

* `ade_config/row_detectors/*.py` → row detector helpers.
* `ade_config/column_detectors/*.py` → column detector helpers.
* `ade_config/hooks/*.py` → hook helpers.

Features:

* **Hover** – show canonical function signatures and short docstrings for ADE entrypoints.
* **Completion** – suggest ADE entrypoints and common patterns as snippets.
* **Signature help** – show parameter names and types when typing inside function calls.

These helpers are implemented as Monaco language features (hover providers, completion providers, signature help providers) registered for the `"python"` language.

### 9.2 Shared function specs

The expected script entrypoints are described via a shared `AdeFunctionSpec` structure (TypeScript) and mirrored as Python signatures.

The helpers do not execute or validate code; they just provide **editor assistance**.

#### Row detectors (`row_detectors/*.py`)

Typical entrypoint:

```python
def detect_*(
    *,
    job,
    state,
    row_index: int,
    row_values: list,
    logger,
    **_,
) -> dict:
    ...
```

* Purpose: score a row (e.g. header vs data) via numeric deltas.
* Helpers surface:

  * Meaning of `job` and `state`.
  * Expected keys in the returned dict (e.g. `{"score": float, "reason": str}`).

#### Column detectors / transforms / validators (`column_detectors/*.py`)

Detector:

```python
def detect_*(
    *,
    job,
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

Transform:

```python
def transform(
    *,
    job,
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

Validator:

```python
def validate(
    *,
    job,
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

Helpers provide:

* Parameter descriptions (e.g. what `field_meta` and `column_values_sample` contain).
* Expected return shapes.

#### Hooks (`hooks/*.py`)

Common hooks:

```python
def on_job_start(
    *,
    job_id: str,
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

def on_job_end(
    *,
    artifact: dict | None = None,
    logger=None,
    **_,
) -> None:
    ...
```

Helpers:

* Remind users of hook names and when in the pipeline they are called.
* Provide descriptions of `manifest`, `env`, and `artifact`.

### 9.3 Extensibility

The helpers are intentionally data‑driven:

* Adding new entrypoints or parameters should be done by updating the `AdeFunctionSpec` registry, not by hard‑coding in multiple places.
* The Monaco integration reads from that registry and does not need to know about ADE internals.

---

## 10. Extensibility guidelines

When extending the workbench, keep these principles in mind:

* **Single responsibility per component:**

  * New panels (e.g. a test runner) should live alongside console/validation, not inside the editor or explorer.

* **URL and persistence separation:**

  * Use URL state for **shareable** aspects (which file is active, which pane is selected).
  * Use localStorage for **personal preferences** (tab list, layout sizes, theme).

* **Config‑scoped state:**

  * Any persistent preference must be keyed by `(workspaceId, configId)`.

* **Non‑intrusive features:**

  * New Monaco features should be opt‑in and safely ignore files that don’t match their scope.

If a change affects any of the invariants outlined in this doc (window states, file tree contracts, tab persistence, URL keys), update this file alongside the implementation to keep ADE Web predictable for both humans and AI agents.