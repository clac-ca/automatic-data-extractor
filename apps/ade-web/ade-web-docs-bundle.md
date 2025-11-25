# Logical module layout (source -> sections below):
# - apps/ade-web/README.md - ADE Web
# - apps/ade-web/docs/01-domain-model-and-naming.md - 01-domain-model-and-naming
# - apps/ade-web/docs/02-architecture-and-project-structure.md - 02-architecture-and-project-structure
# - apps/ade-web/docs/03-routing-navigation-and-url-state.md - 03-routing-navigation-and-url-state
# - apps/ade-web/docs/04-data-layer-and-backend-contracts.md - 04-data-layer-and-backend-contracts
# - apps/ade-web/docs/05-auth-session-rbac-and-safe-mode.md - 05-auth-session-rbac-and-safe-mode
# - apps/ade-web/docs/06-workspace-layout-and-sections.md - 06-workspace-layout-and-sections
# - apps/ade-web/docs/07-documents-runs-and-runs.md - 07-documents-runs-and-runs
# - apps/ade-web/docs/08-configurations-and-config-builder.md - 08-configurations-and-config-builder
# - apps/ade-web/docs/09-workbench-editor-and-scripting.md - 09-workbench-editor-and-scripting
# - apps/ade-web/docs/10-ui-components-a11y-and-testing.md - 10-ui-components-a11y-and-testing

# apps/ade-web/README.md
```markdown
# ADE Web

ADE Web is the browser‑based front‑end for the **Automatic Data Extractor (ADE)** platform.

It serves two main personas:

- **Workspace owners / engineers** – design and evolve config packages (Python packages) that describe how documents are processed; manage safe mode; and administer workspaces, SSO, roles, and members.
- **End users / analysts / operators** – upload documents, run extractions, monitor progress, inspect logs and telemetry, and download structured outputs.

This document describes **what** ADE Web does and the behaviour it expects from any compatible backend. It is intentionally **backend‑agnostic** and should be treated as the product‑level specification for ADE Web and its contracts with the backend.

---

## High‑level UX & layout

ADE Web has two major layers:

1. **Workspace directory** – where users discover and create workspaces.
2. **Workspace shell** – where users operate inside a specific workspace.

Both layers share common patterns:

- A **top bar** with brand/context, search, and profile menu.
- A main content area that adapts to desktop and mobile.
- A consistent approach to **navigation**, **URL state**, **safe mode banners**, and **notifications**.

The top bar is composed via `GlobalTopBar`, which:

- Accepts **brand** (logo/name), **leading** (contextual breadcrumbs), **actions** (primary buttons), and **trailing** (profile) slots.
- Optionally renders a unified **search field** powered by `GlobalSearchField` (see below).
- Supports **secondaryContent** below the main row for context, filters, or breadcrumbs.

### Workspace directory layout (`/workspaces`)

The **Workspace directory** is the primary entry point after sign‑in:

- Header:
  - Brand “Workspace directory”.
  - Subtitle such as “Automatic Data Extractor”.
- A **workspace search box**:
  - Filters by workspace name/slug.
  - Supports keyboard focus via a global shortcut (`⌘K` / `Ctrl+K`).
  - Enter can jump directly to the best match.
- **Actions** (permission‑gated):
  - “Create workspace” is shown only if the user has `Workspaces.Create`.

Main content:

- **Empty states**:
  - If the user can create workspaces but has none: a CTA to create the first workspace.
  - If the user cannot create workspaces: a message explaining they need to be added to a workspace.
- **Workspace cards** when there are workspaces:
  - Name and slug.
  - Whether the workspace is marked as the user’s **default**.
  - A compact summary of the user’s roles/permissions in that workspace.
  - Click opens the workspace shell (default section, typically Documents).

A right‑hand panel can provide:

- **Guidance** on how to structure workspaces (per client, per environment, etc.).
- A **short checklist** for new deployments (invite admins, configure roles, review configs before production).

### Workspace shell layout (`/workspaces/:workspaceId/...`)

Inside a workspace, ADE Web uses a reusable **workspace shell**:

- **Left navigation (desktop)**:
  - Workspace avatar/initials and name.
  - “Switch workspace” affordance.
  - Primary sections:
    - Documents
    - Runs
    - Config Builder
    - Settings
  - Collapse/expand state is persisted **per workspace** (each workspace remembers nav compactness).

- **Top bar**:
  - Workspace name and optional environment label (e.g. “Production”, “Staging”).
  - Context‑aware **search** (via `GlobalSearchField`):
    - On **Documents**, it acts as a document‑scoped search.
    - Elsewhere, it can search within the workspace (sections, configs, runs).
  - A profile dropdown (`ProfileDropdown`) with user display name/email and actions like “Sign out”.

- **Mobile navigation**:
  - The left nav becomes a slide‑in panel:
    - Opens via a menu button.
    - Locks body scroll while open.
    - Closes on navigation, tapping outside, or pressing Esc.

- **Safe mode banner**:
  - When safe mode is active, a persistent banner appears within the workspace shell explaining that runs/builds are paused.

- **Notifications**:
  - Toasts for success/error messages.
  - Banners for cross‑cutting issues like safe mode, connectivity, or workbench layout warnings.

Certain routes (especially the **Config Builder** workbench) can temporarily hide parts of the shell in favour of an immersive, IDE‑like layout.

---

## Core concepts

### Workspaces

A **workspace** is the primary unit of organisation and isolation:

- Owns **documents**, **runs/runs**, **config packages**, and **membership/roles**.
- Has a human‑readable **name** and a stable **slug/ID** that appear in the UI and URLs.
- Has **settings** (name, slug, environment labels, safe mode, etc.).
- Is governed by **workspace‑scoped RBAC**.

Users sign in, land on the **Workspace directory**, and then select (or create) a workspace before they can work with documents or configs.

---

### Documents

A **document** is any input file processed by ADE, e.g.:

- Spreadsheets: `.xls`, `.xlsx`, `.xlsm`, `.xlsb`
- CSV/TSV files: `.csv`, `.tsv`
- PDFs and other semi‑structured formats.

Per workspace:

- Documents are **uploaded into** and **owned by** that workspace.
- Each document includes:
  - A unique **ID**.
  - **Name** (often the original filename).
  - **Content type** and **size** (used to show “Excel spreadsheet • 2.3 MB”).
  - **Status**:
    - `uploaded` – file is stored but not yet processed.
    - `processing` – currently being processed by a run.
    - `processed` – last run completed successfully.
    - `failed` – last run ended in error.
    - `archived` – kept for history, not actively used.
  - **Timestamps** (created/uploaded at).
  - **Uploader** (user who uploaded the file).
  - **Last run summary** (`last_run`):
    - Status (`succeeded`, `failed`, `running`, etc.),
    - A short message (if provided),
    - When it last ran.

Documents are treated as **immutable inputs**:

- Re‑uploading a revised file results in a **new document**.
- Runs always refer to the original uploaded file by ID.

Multi‑sheet spreadsheets can expose **worksheet metadata**:

- ADE Web calls a document‑sheets endpoint to learn about sheets:
  - `name`, index, and whether a sheet is “active”.
- Run dialogs (including the Config Builder **Run extraction** dialog) can offer sheet‑level selection.

---

### Runs (runs)

A **run** (or **run**) is a single execution of ADE against a set of inputs with a particular config version.

Key ideas:

- Runs are **workspace‑scoped** and usually tied to at least one document.
- Each run includes:
  - **Status**: `queued`, `running`, `succeeded`, `failed`, `cancelled`.
  - **Timestamps**:
    - Queued / created,
    - Started,
    - Completed / cancelled.
  - **Initiator** (user who triggered it, or system).
  - **Config version** used.
  - References to **input documents** (display names and counts).
  - Links to **outputs**:
    - An overall artifact (e.g. zipped outputs),
    - A list of named output files,
    - Logs/telemetry streams or downloads.
  - Optional **summary** and **error message**.

Run options (as supported by the backend) include:

- `dry_run` – exercise the pipeline without emitting final outputs.
- `validate_only` – run validators and checks, but not full extraction.
- `input_sheet_names` – when provided, only these spreadsheet worksheets are processed.

For a given document:

- ADE Web can remember **per‑document run preferences**:
  - Preferred config,
  - Preferred config version,
  - Preferred subset of sheet names.
- These preferences are stored in local, workspace‑scoped storage and reapplied the next time you run that document.

The backend exposes **streaming NDJSON APIs** for run events:

- ADE Web uses these for:
  - Live status updates,
  - Logs,
  - Telemetry summaries (rows processed, warnings, etc.).
- The same streams can be replayed to show historical run details.
- The Config Builder workbench reuses this to show build/run events inside its **Console**.

---

### Config packages & versions

A **config package** is a Python package that tells ADE how to:

- Interpret specific document formats,
- Validate incoming data,
- Transform them into structured outputs.

Per workspace:

- There may be **one or many** config packages (e.g., per client, per pipeline).
- Each package has **config versions** (immutable snapshots).
- Exactly **one version is active** for “normal” runs at any time.

#### Version lifecycle

Product‑level lifecycle:

- **Draft**
  - Fully editable.
  - Can be built, validated, and used for **test** runs.
- **Active**
  - Exactly one active version per workspace.
  - Read‑only in the UI.
  - Used by default for new runs unless another version is explicitly selected.
- **Inactive**
  - Older or retired versions.
  - Not used for new runs.
  - Kept for history, audit, and rollback.

Backends may add internal states (e.g. “published”, “archived”), but ADE Web presents the lifecycle as **Draft → Active → Inactive**.

Typical flows:

1. Clone the **active** version (or a known‑good inactive one) into a new **draft**.
2. Edit code, config files, and manifest in the Config Builder.
3. Run builds/validations and test runs against sample documents.
4. When satisfied, **activate** the draft:
   - It becomes **Active**.
   - The previous active version becomes **Inactive**.
5. Monitor early runs and adjust via new drafts as needed.

---

### Manifest & schema

Each config version exposes a structured **manifest** describing expected outputs and per‑table behaviour.

For columns:

- `key` – stable identifier.
- `label` – human‑friendly display name.
- `path` – where the value comes from in extracted data.
- `ordinal` – sorting/order.
- `required` – whether the column must be present.
- `enabled` – whether it appears in outputs.
- `depends_on` – optional column dependencies.

Table‑level options:

- `transform` – script used to transform raw rows.
- `validators` – scripts for table‑level or row‑level validation.

ADE Web:

- Parses the manifest into a structured model.
- Surfaces it in the Config Builder for:
  - Reordering columns,
  - Toggling enabled/required flags,
  - Linking transform/validator scripts.
- Sends **patches** to the backend, preserving unknown fields so the backend schema can evolve without breaking the UI.

---

### Safe mode

ADE includes a **safe mode** kill switch for engine execution.

When **safe mode is enabled**:

- Engine‑invoking actions are blocked, including:
  - New runs,
  - Draft builds/validations,
  - Test runs,
  - Activations.
- Read‑only operations continue to work:
  - Viewing documents,
  - Inspecting old runs,
  - Downloading existing artifacts.

Behaviour:

- Safe mode is primarily **system‑wide**; optionally it can be extended with workspace scope.
- The backend exposes a **status endpoint** with:
  - `enabled: boolean`,
  - A human‑readable `detail` message.
- ADE Web periodically checks this status and:
  - Shows a banner with the detail message when enabled.
  - Disables “Run”, “Run extraction”, “Build”, “Test run”, and “Activate” buttons.
  - Uses clear tooltips (e.g. “Safe mode is enabled: …”) instead of silent failures.

Management:

- System safe mode is controlled via Settings and requires a permission like `System.Settings.ReadWrite`.
- The UI:
  - Shows current state (enabled/disabled) and detail.
  - Lets authorised users update the message.
  - Provides a single toggle to enable/disable safe mode.

---

### Roles & permissions

ADE Web is designed around **RBAC** (role‑based access control):

- Users hold **roles** per workspace (e.g. Owner, Maintainer, Reviewer, Viewer).
- Roles aggregate **permissions** (e.g. `Workspace.Members.ReadWrite`, `Workspace.Roles.ReadWrite`).

Permissions govern actions such as:

- Creating/deleting **workspaces**.
- Managing **workspace members**.
- Creating/updating **workspace roles**.
- Toggling **safe mode**.
- Editing and activating **config versions**.
- Running **runs** and **test runs**.
- Viewing **logs** and **telemetry**.

Backend responsibilities:

- Encode permissions in the session / workspace membership.
- Enforce permissions server‑side on all operations.

Frontend responsibilities:

- Read permissions from session and workspace membership.
- Hide or disable UI controls the user cannot use.
- Use permission keys as hints (e.g. show members tab only if the user can see the membership list).

---

## Routes & navigation model

ADE Web is a **single‑page React app** with a lightweight custom navigation layer built on `window.history`.

### Top‑level routes (`App.tsx` / `ScreenSwitch`)

`App` composes:

- `NavProvider` – custom navigation context.
- `AppProviders` – React Query provider and dev tools.
- `ScreenSwitch` – top‑level route switch based on the current pathname.

Pathnames are **normalised** to avoid trailing‑slash variants (`/foo/` → `/foo`):

- `/` – Home / entry strategy (decides whether to send the user to login, setup, or the app).
- `/login` – Sign‑in and auth provider selection.
- `/auth/callback` – Auth provider callback handler.
- `/setup` – First‑run setup flow.
- `/logout` – Logout screen.
- `/workspaces` – Workspace directory.
- `/workspaces/new` – Create workspace.
- `/workspaces/:workspaceId/...` – Workspace shell; internal section is resolved by the workspace screen.
- Any other path – “Not found” screen.

Inside `/workspaces/:workspaceId`, the first path segment after the workspace ID selects the section:

- `/documents` – Documents list and document run UI.
- `/runs` – Runs ledger (workspace‑wide run history).
- `/config-builder` – Config overview and Config Builder workbench.
- `/settings` – Workspace settings (tabs controlled by `view` query param).
- `/overview` – Optional overview/summary surface.

Unknown section paths inside a workspace show a **workspace‑local “Section not found”** state rather than a global 404.

### Custom navigation layer (`NavProvider`, `Link`, `NavLink`)

Navigation is handled by a small system instead of a third‑party router.

Core types:

```ts
type LocationLike = { pathname: string; search: string; hash: string };

type NavigationIntent = {
  readonly to: string;
  readonly location: LocationLike;
  readonly kind: "push" | "replace" | "pop";
};

type NavigationBlocker = (intent: NavigationIntent) => boolean;
````

**Provider:**

* `NavProvider` owns `location` state derived from `window.location`.
* Listens to `popstate` for back/forward navigations:

  * Builds a `NavigationIntent` with `kind: "pop"`.
  * Runs all registered blockers.
  * If any returns `false`:

    * Restores the previous URL via `pushState`.
    * Does not update internal state.
  * Otherwise updates `location`.

**Programmatic navigation:**

* `useNavigate()` returns `navigate(to, { replace? })`:

  * Resolves `to` via `new URL(to, window.location.origin)`.
  * Builds `NavigationIntent` with `kind` `"push"` or `"replace"`.
  * Runs blockers; cancels if any returns `false`.
  * Calls `pushState`/`replaceState` and manually dispatches `PopStateEvent` so all navigation flows share the same code path.

**Hooks:**

* `useLocation()` – read the current location.
* `useNavigate()` – trigger SPA navigation.
* `useNavigationBlocker(blocker, when)` – register/unregister a navigation blocker while `when` is true.

Typical usage:

* Editors (especially Config Builder) use blockers to guard against losing unsaved changes.
* Blockers usually:

  * Allow navigation if the pathname is unchanged (query/hash only).
  * Optionally consult custom bypass flags (e.g. “Save then navigate” flows).

### SPA links (`Link`, `NavLink`)

`Link` wraps `<a>`:

* Always sets `href={to}` for semantics and right‑click / copy‑link behaviour.
* Intercepts **unmodified** left‑clicks:

  * Calls any `onClick`.
  * If not prevented and no modifier keys are pressed:

    * `preventDefault()`.
    * Calls `navigate(to, { replace })`.
* For modified clicks (`metaKey`, `ctrlKey`, `shiftKey`, `altKey`):

  * Does **not** intercept; lets the browser open new tabs/windows.

`NavLink` builds on `Link` and tracks active state:

```ts
const isActive = end
  ? pathname === to
  : pathname === to || pathname.startsWith(`${to}/`);
```

* `className` and `children` can be static values or render functions receiving `{ isActive }`.
* Enables active styling and variant rendering for nav items.

---

## URL state & search parameters

ADE Web encodes important UI state in the URL so views can be shared and restored on refresh. Utilities live in `urlState.ts`.

### Basic helpers

* `toURLSearchParams(init)` – builds `URLSearchParams` from:

  * String, array, `URLSearchParams`, or a record of keys to values/arrays.
* `getParam(search, key)` – read a single query param from a raw search string.
* `setParams(url, patch)` – patch query params on a `URL` and return `path + search + hash`.

### Hook: `useSearchParams`

`useSearchParams()` is the standard way to work with query parameters:

```ts
const [params, setSearchParams] = useSearchParams();
// params: URLSearchParams
// setSearchParams: (init: SearchParamsInit | (prev) => SearchParamsInit, options?: { replace?: boolean }) => void
```

* Reads the current search string from `useLocation()`.
* `setSearchParams`:

  * Resolves `init` (value or function of previous `URLSearchParams`).
  * Calls `toURLSearchParams`.
  * Builds a URL preserving `pathname` and `hash`.
  * Calls `navigate(target, { replace })` under the hood.

### Search params overrides

`SearchParamsOverrideProvider` allows nested subtrees to **override** how `useSearchParams` behaves:

```ts
interface SearchParamsOverrideValue {
  readonly params: URLSearchParams;
  readonly setSearchParams: (init: SetSearchParamsInit, options?: SetSearchParamsOptions) => void;
}
```

* Inside the provider, `useSearchParams()` returns the override value.
* Useful for:

  * Dialogs or embedded panels that want “local” query state.
  * Legacy flows that need to fake query changes without touching the browser address bar.

Most sections use the real URL search parameters directly; overrides are reserved for advanced cases.

---

## Config Builder – workbench model

The **Config Builder** is an IDE‑like workbench for editing config packages, backed by a file tree from the backend and a tabbed Monaco editor.

### Workbench window states

The workbench is hosted by a `WorkbenchWindow` context and route:

* **Restored** – editor appears inline inside the Config Builder section.
* **Maximized** – editor takes over the viewport:

  * A dim overlay covers the workspace shell.
  * Page scroll is locked while maximized.
  * The underlying section shows an “Immersive focus active” notice.
* **Minimized/docked** – editor is hidden from the main Config Builder content:

  * The section shows “Workbench docked”.
  * A dock (elsewhere in the workspace layout) can restore it.

Window controls in the workbench chrome:

* **Minimize** – dock the workbench.
* **Maximize / Restore** – toggle immersive focus.
* **Close** – close the workbench session for the current config.

Unsaved‑changes guards still apply when closing or navigating away.

### File tree representation (`WorkbenchFileNode`)

Internally, the workbench models a config package as a tree:

```ts
export type WorkbenchFileKind = "file" | "folder";

export interface WorkbenchFileMetadata {
  size?: number | null;
  modifiedAt?: string | null;
  contentType?: string | null;
  etag?: string | null;
}

export interface WorkbenchFileNode {
  id: string;          // canonical path, e.g. "ade_config/detectors/membership.py"
  name: string;        // display name, e.g. "membership.py"
  kind: WorkbenchFileKind;
  language?: string;   // editor language id (e.g. "python", "json")
  children?: WorkbenchFileNode[];
  metadata?: WorkbenchFileMetadata | null;
}
```

Typical tree root:

* A folder such as `ade_config` with children:

  * `manifest.json`,
  * `config.env`,
  * `header.py`,
  * `detectors`/`hooks`/`tests` folders.

For local development and empty configs, the app can use:

* `DEFAULT_FILE_TREE` – in‑memory sample package tree.
* `DEFAULT_FILE_CONTENT` – map of file IDs to initial content strings.

### Building the tree from backend listing

The backend exposes a flat file listing (e.g. `FileListing`) with entries:

* `path`, `name`, `parent`, `kind` (`"file"` or `"dir"`), `depth`,
* `size`, `mtime`, `content_type`, `etag`.

`createWorkbenchTreeFromListing(listing)`:

* Derives a root ID (from `root`, `prefix` or first entry’s parent).
* Normalises paths (`canonicalizePath` trims trailing slashes).
* Ensures intermediate folders exist (`ensureFolder`).
* Builds a `WorkbenchFileNode` tree:

  * Folders: metadata set from listing; added as children of parent.
  * Files:

    * `language` inferred from extension (`python`, `json`, `markdown`, etc.).
    * Metadata set from listing.
* Sorts children via `compareNodes`:

  * Folders before files, alphabetical within each group.

Helpers:

* `extractName(path)` – basename.
* `deriveParent(path)` – parent path or `""`.
* `findFileNode(root, id)` – depth‑first search.
* `findFirstFile(root)` – first file node (folder‑first traversal).

### Workbench layout & panels

The workbench layout mirrors modern editors:

* **Activity Bar** (left):

  * `explorer` – Config file tree.
  * `search` – reserved for future search.
  * `scm` – reserved for source control.
  * `extensions` – reserved for extensions.
  * A gear button opens a settings menu.

* **Explorer** (optional left panel):

  * Displays the config file tree.
  * Highlights the active file and marks open files.
  * Context menus for folders and files (expand/collapse, copy path, close tabs, etc.) via `ContextMenu`.

* **Editor area** (center):

  * Tab strip for open files (pinned and regular).
  * Drag‑and‑drop tab reordering.
  * Code editor (`CodeEditor` / Monaco) with syntax highlighting and `⌘S` / `Ctrl+S` wired to save.

* **Bottom panel**:

  * **Console** tab – streaming build/run logs and a **Run summary** card.
  * **Validation** tab – structured validation messages with severity and path.

* **Inspector** (right panel):

  * Shows metadata and editor status for the active file:

    * Size, modified time, content type, ETag.
    * Load status (loading/ready/error) and dirty flag.

Panel layout is fully resizable:

* Panel widths and console height use draggable handles.
* Minimum and maximum sizes (px) protect editor readability.
* Console open/closed state and height are persisted per workspace+config.

On very small vertical screens, the console may auto‑collapse; the UI shows a banner explaining that the console was closed to preserve editor space.

### ADE script helpers & script API

To make ADE config editing more discoverable, the Monaco editor is augmented with ADE‑specific helpers via `registerAdeScriptHelpers`:

* **Scope‑aware**: helpers only activate in ADE config files:

  * `row_detectors/…` → row detectors.
  * `column_detectors/…` → column detectors / transforms / validators.
  * `hooks/…` → run hooks.
* **Features**:

  * **Hover**:

    * Shows the canonical signature and documentation for known functions.
  * **Completion**:

    * Offers snippet completions (triggered via typing or `Ctrl+Space`) for common entrypoints.
  * **Signature help**:

    * Shows parameter lists when typing inside function calls.

The shared script API is expressed as `AdeFunctionSpec` records. Conceptually important entrypoints:

* **Row detectors** (`row_detectors/*.py`):

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

  Used to score rows (e.g. header vs data) via small numeric deltas.

* **Column detectors / transforms / validators** (`column_detectors/*.py`):

  ```python
  # Detector
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

  # Transform
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

  # Validator
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

* **Hooks** (`hooks/*.py`):

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

The editor helpers do **not** enforce backend behaviour but act as a convenient, discoverable reference for the expected function shapes.

### Workbench tabs, content, and persistence

Tabs are represented as:

```ts
export type WorkbenchFileTabStatus = "loading" | "ready" | "error";

export interface WorkbenchFileTab {
  id: string;
  name: string;
  language?: string;
  initialContent: string;
  content: string;
  status: WorkbenchFileTabStatus;
  error?: string | null;
  etag?: string | null;
  metadata?: WorkbenchFileMetadata | null;
  pinned?: boolean;
  saving?: boolean;
  saveError?: string | null;
  lastSavedAt?: string | null;
}
```

The `useWorkbenchFiles` hook manages:

* List of open tabs.
* Active tab and MRU order (for `Ctrl+Tab` / `⌘Tab`‑style switching).
* Lazy content loading via `loadFile(fileId)`.
* Dirty tracking (`content !== initialContent`).
* Saving state and concurrency errors (ETag‑based).
* Pinning/unpinning tabs (pinned tabs stay on the left).
* Close/close others/close to the right/close all.

Persistence:

```ts
interface PersistedWorkbenchTabs {
  readonly openTabs: readonly (string | { id: string; pinned?: boolean })[];
  readonly activeTabId?: string | null;
  readonly mru?: readonly string[];
}
```

* Implemented via scoped storage (`localStorage`).
* Keyed by workspace ID and config ID:

  * Example: `ade.ui.workspace.<workspaceId>.config.<configId>.tabs`.
* Hydrated on load and filtered against the current tree.

### Editor theme preference

The editor honours user theme preference:

```ts
export type EditorThemePreference = "system" | "light" | "dark";
export type EditorThemeId = "ade-dark" | "vs-light";
```

* `useEditorThemePreference`:

  * Storage key: `ade.ui.workspace.<workspaceId>.config.<configId>.editor-theme`.
  * Watches `prefers-color-scheme: dark`.
  * Resolves `EditorThemeId` from preference + system dark/light.

A custom Monaco theme (`ade-dark`) is defined, adjusting editor background, cursor, gutter, and selection colours.

### Console state & persistence

Console open/closed state and height are persisted as:

```ts
interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number;
  readonly state: ConfigBuilderConsole; // "open" | "closed"
}
```

* Key: `ade.ui.workspace.<workspaceId>.config.<configId>.console`.
* On load:

  * Uses stored `fraction` if available.
  * Otherwise uses a default pixel height converted into a fraction of container height.
* The workbench may override initial open/closed state from persisted value if the URL query explicitly sets console state.

### Build & validation pipeline

The **workbench chrome** includes a **Build environment** split button (implemented via `SplitButton`):

* Default click:

  * Starts `streamBuild(workspaceId, configId, { force, wait }, signal)`.
  * Prints build events into the **Console**.
  * Detects and highlights environment reuse (e.g. “Environment reused; nothing to rebuild.”).
* Menu options:

  * “Build / reuse environment” – normal behaviour.
  * “Force rebuild now” – run a full rebuild immediately.
  * “Force rebuild after current build” – queue a forced rebuild.
* Keyboard shortcuts:

  * `⌘B` / `Ctrl+B` – default build.
  * `⇧⌘B` / `Ctrl+Shift+B` – force rebuild.

**Validation:**

* “Run validation” button starts a `validate_only` run.
* While validation is running:

  * Status is `running`; results are streamed into the console.
* On completion:

  * Issues are mapped into the **Validation** tab as structured messages.
  * `lastRunAt` is updated.
* On error:

  * Status becomes `error` with a human‑readable message.

### Running extraction from the workbench

The **Run extraction** button opens a modal **Run extraction dialog**:

* Fetches recent documents for the workspace (e.g. top 50 by `-created_at`).
* Lets the user select:

  * A document (required).
  * Optional worksheets (for spreadsheet inputs).
* Worksheet metadata:

  * Loaded via a document‑sheets endpoint.
  * If unavailable:

    * Shows a warning.
    * Provides a fallback “Use all worksheets”.
* On confirmation:

  * Calls `startRunStream` with:

    * `input_document_id`,
    * Optional `input_sheet_names`.
  * Closes the dialog and streams output into the console.

On run completion:

* The console shows a **Run summary** card with:

  * Run ID and status.
  * Document name and worksheets used.
  * Download links for:

    * Artifact (combined outputs),
    * Log / telemetry file,
    * Individual output files.

---

## Workbench URL state

Config Builder’s layout and file selection are encoded in query parameters.

Types:

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
  readonly file?: string;
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

### Reading builder state: `readConfigBuilderSearch`

`readConfigBuilderSearch(source)`:

* Accepts `URLSearchParams` or a raw search string.
* Normalises values:

  * `console` → `"open"` | `"closed"` (fallback: `"closed"`).
  * `pane` → `"console"` | `"validation"` (legacy `"problems"` → `"validation"`).
  * `view` → `"editor" | "split" | "zen"` (invalid → `"editor"`).
  * `file` from `file` or legacy `path`.
* Returns:

```ts
export interface ConfigBuilderSearchSnapshot extends ConfigBuilderSearchState {
  readonly present: {
    readonly tab: boolean;
    readonly pane: boolean;
    readonly console: boolean;
    readonly view: boolean;
    readonly file: boolean;
  };
}
```

* `present` flags indicate which keys were explicitly set vs inherited default.

### Merging builder state: `mergeConfigBuilderSearch`

`mergeConfigBuilderSearch(current, patch)`:

* Reads current state from `current`.
* Merges:

  * Global defaults,
  * Existing state,
  * `patch`.
* Returns a new `URLSearchParams` where:

  * All builder‑related keys (`tab`, `pane`, `console`, `view`, `file`, `path`) are wiped first.
  * Only **non‑default** values are written back.
  * `file` is omitted if empty.

Result: URLs stay clean; only state that differs from defaults is encoded.

### Workbench URL hook: `useWorkbenchUrlState`

The workbench consumes URL state via `useWorkbenchUrlState`, which combines `useSearchParams` and the helpers above:

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

* Derived from `readConfigBuilderSearch(params)`.
* `set*` methods:

  * Guard against no‑ops.
  * Use `mergeConfigBuilderSearch` to compute new query.
  * Call `setSearchParams(next, { replace: true })` to avoid history spam.
* `consoleExplicit`:

  * True when the URL explicitly sets console state.
  * Used to decide whether to respect persisted console state or defer to the URL.

### Other notable search params

Outside Config Builder, some important query parameters:

* **Documents**

  * `q` – free‑text search (document name, source, etc.).
  * `status` – comma‑separated list of document statuses.
  * `sort` – sort order (e.g. `-created_at`, `-last_run_at`).
  * `view` – view preset (`mine`, `team`, `attention`, `recent`).
* **Settings**

  * `view` – active settings tab (`general`, `members`, `roles`).
* **Auth flows**

  * `redirectTo` – desired post‑login path.

    * Must be a safe, same‑origin relative path.
    * Backend and frontend both validate it to avoid open redirects.

---

## Workspace Settings

The **Settings** section holds workspace‑specific configuration and is **tabbed**:

* `view=general` – name, slug, environment label, possibly default workspace toggle.
* `view=members` – list of members, invites, roles per member.
* `view=roles` – role definitions and permissions.
* Safe mode controls live in Settings and are permission‑gated.

Behaviour:

* Uses `useSearchParams` to:

  * Read the `view` parameter.
  * Normalise invalid values back to `general`.
  * Keep tab selection in sync with the URL via `setSearchParams({ view }, { replace: true })`.
* Tabs lazily mount their content to avoid unnecessary data fetching.

### Workbench return path

For smooth flow between operational views and config editing, the workbench can remember where to return after editing:

```ts
export function getWorkbenchReturnPathStorageKey(workspaceId: string) {
  return `ade.ui.workspace.${workspaceId}.workbench.returnPath`;
}
```

Pattern:

1. When navigating **into** the workbench from a section (e.g. Documents/Runs/Settings), store the current URL.
2. When closing or exiting the workbench, navigate back to the stored path and clear it.

This keeps “back to where I was” behaviour predictable.

---

## Workspace shell sections (behaviour overview)

High‑level behaviours of the main workspace sections:

* **Documents**

  * List and filter documents.
  * Upload new documents (`⌘U` / `Ctrl+U`).
  * Trigger runs against a selected config version.
  * Show per‑document last run status and quick actions.

* **Runs**

  * Workspace‑wide ledger of runs.
  * Filter by status, config, date range, and initiator.
  * Link through to:

    * Logs (via NDJSON replay),
    * Telemetry summaries,
    * Output artifacts.

* **Config Builder**

  * Config list:

    * Shows configurations, IDs, status, active version.
    * “Open editor” opens the workbench for a given config.
  * Workbench:

    * IDE‑style editing surface as described above.

* **Settings**

  * General workspace metadata.
  * Members and roles management.
  * Safe mode and other admin‑level controls.

---

## Notifications & keyboard shortcuts

ADE Web uses a unified notification system:

* **Toasts**:

  * Short‑lived, contextual messages (saves, minor errors).
* **Banners**:

  * Cross‑cutting issues: safe mode, connectivity, console auto‑collapse, environment reuse, concurrency errors, etc.

Workbench‑specific banner scopes are used so messages (e.g. around console collapse or build reuse) can be dismissed or persisted independently.

Keyboard shortcuts (non‑exhaustive):

* **Global**

  * `⌘K` / `Ctrl+K` – open workspace/global search.
  * `⌘U` / `Ctrl+U` – document upload (where implemented).
* **Workbench**

  * `⌘S` / `Ctrl+S` – save active editor file.
  * `⌘B` / `Ctrl+B` – build/reuse environment.
  * `⇧⌘B` / `Ctrl+Shift+B` – force rebuild.
  * `⌘W` / `Ctrl+W` – close active editor tab.
  * `⌘Tab` / `Ctrl+Tab` – recent‑tab forward (within workbench).
  * `⇧⌘Tab` / `Shift+Ctrl+Tab` – recent‑tab backward.
  * `Ctrl+PageUp/PageDown` – cycle tabs by visual order.

Shortcuts are implemented carefully to avoid interfering with browser defaults and only apply when the editor has focus and the target element is not an input/textarea/content‑editable.

---

## Backend expectations (high‑level contracts)

ADE Web is backend‑agnostic but assumes certain HTTP APIs and behaviours.

At a high level, the backend must provide:

* **Auth & session**

  * Login/logout endpoints.
  * Auth callback handling (`/auth/callback`).
  * Session endpoint exposing:

    * User identity (id, name, email),
    * Global/system permissions,
    * Workspace membership and roles.

* **Workspaces**

  * List workspaces for current user (with roles and default flag).
  * Create workspace (name, slug, owner).
  * Update workspace settings (name, slug, environment labels).
  * Delete/archive workspace (optional).
  * Default workspace management.

* **Users & invitations**

  * Directory search (for picking workspace owners and members).
  * Invite users to workspace (email‑based).
  * Accept/decline invitations.

* **Roles & permissions**

  * CRUD for roles at workspace scope.
  * Membership management (assign/remove roles for users).
  * Permission model encoded as strings understood by the frontend.

* **Documents**

  * Upload endpoint per workspace.
  * Paginated list with filters (status, search query, sort).
  * Download endpoint for raw document.
  * Optional document sheets metadata (`name`, index, `is_active`).

* **Runs / runs**

  * Create run (document + config version + options).
  * NDJSON streaming endpoint for run events:

    * Status changes, logs, telemetry envelopes.
  * List runs (filterable by status, document, config, date).
  * Run outputs:

    * Listing of output files (path, byte size).
    * Artifact download (combined outputs, typically zip).
    * Telemetry download.

* **Configs & Config Builder**

  * List configs per workspace (with ID, display name, status, active version).
  * Read single config by ID.
  * File listing for a config version (flat listing consumable by `createWorkbenchTreeFromListing`).
  * File content endpoints:

    * Read (`GET`) with metadata (`size`, `mtime`, `content_type`, `etag`, `encoding`).
    * Write (`PUT`/`PATCH`) with:

      * `etag` preconditions (for concurrency),
      * `create` and `parents` flags where applicable.
    * Optional rename/delete endpoints.
  * Validation endpoint:

    * Accepts current config snapshot.
    * Returns structured validation issues for display in the Validation tab.
  * Build endpoint:

    * NDJSON streaming (`streamBuild`) with `force` and `wait` options.
    * Emits a final `build.completed` event with `status`, `summary`, `error_message`.
    * Implements environment reuse detection so ADE Web can hint whether a rebuild actually happened.

* **Safe mode**

  * Global and optional workspace‑scoped status endpoint.
  * Mutations to toggle safe mode and update message (permission‑gated).

* **Security**

  * All operations must enforce:

    * Authentication,
    * Authorisation (permissions/roles),
    * Tenant isolation across workspaces.
  * `redirectTo` query parameters must be validated as same‑origin, relative paths to avoid open redirects.
  * CORS and CSRF protections compatible with browser‑based SPA usage.

As long as these contracts are honoured, ADE Web can be re‑used with different backend implementations without changing the user experience described here.

---

## Front‑end architecture & tooling

### Entry point (`main.tsx`)

The app is mounted in `React.StrictMode`:

```tsx
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

`App` composes:

* `NavProvider` (history & location),
* `AppProviders` (React Query & devtools),
* `ScreenSwitch` (top‑level route selection).

### React Query configuration (`AppProviders.tsx`)

Global React Query settings:

```ts
new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});
```

* Single `QueryClient` created via `useState` (stable per app instance).
* `ReactQueryDevtools` included in development (`import.meta.env.DEV`).

### Build tooling (Vite)

`apps/ade-web/vite.config.ts`:

* Plugins:

  * `@tailwindcss/vite` – Tailwind integration.
  * `@vitejs/plugin-react` – React Fast Refresh and JSX.
  * `vite-tsconfig-paths` – aligns TS path aliases with Vite resolve.

Aliases:

* `@app` → `src/app`
* `@screens` → `src/screens`
* `@ui` → `src/ui`
* `@shared` → `src/shared`
* `@schema` → `src/schema`
* `@generated-types` → `src/generated-types`
* `@test` → `src/test`

Dev server:

* Port:

  * `DEV_FRONTEND_PORT` env var, default `8000`.
* Host:

  * `DEV_FRONTEND_HOST` env var, default `0.0.0.0`.
* Proxy:

  * `/api` → `http://localhost:${DEV_BACKEND_PORT || 8000}`.

This allows:

* Frontend and backend to run on separate ports in development.
* Avoiding CORS issues by proxying API calls through the dev server.

### Testing (Vitest)

`apps/ade-web/vitest.config.ts`:

* Mirrors Vite aliases (`@app`, `@screens`, `@shared`, `@ui`, etc.).
* Test configuration:

```ts
test: {
  environment: "jsdom",
  setupFiles: "./src/test/setup.ts",
  globals: true,
  coverage: {
    provider: "v8",
  },
},
esbuild: {
  jsx: "automatic",
},
```

This enables:

* Browser‑like DOM APIs for component tests.
* A single global setup for test environment (mocks, polyfills).
* Fast TS + JSX transforms using ESBuild.

---

## UI component library

ADE Web ships with a small, composable UI component library under `src/ui`, built on Tailwind CSS. It is intentionally light‑weight and application‑specific.

Key building blocks:

* **Buttons**

  * `Button`:

    * Variants: `"primary" | "secondary" | "ghost" | "danger"`.
    * Sizes: `"sm" | "md" | "lg"`.
    * `isLoading` prop shows an inline spinner and disables the button.
  * `SplitButton`:

    * Primary action + secondary menu toggle, used for Build environment control.
    * Exposes click handlers for primary action and menu opening, plus an optional context‑menu hook.

* **Forms**

  * `Input` and `TextArea`:

    * Shared base styles.
    * `invalid` prop toggles error styling and `aria-invalid`.
  * `Select`:

    * Standard select with matching styling.
  * `FormField`:

    * Wraps a single control with label, hint, and error text.
    * Automatically wires `id`, `aria-describedby`, and `aria-invalid` to the child control when possible.

* **Feedback**

  * `Alert`:

    * `tone: "info" | "success" | "warning" | "danger"`.
    * Optional `heading` and `icon`.
    * Used for inline, persistent messages and section‑level alerts.
  * Global notifications (toasts/banners) are composed at a higher layer using these primitives.

* **Identity**

  * `Avatar`:

    * Derives initials from `name` or `email`.
    * Sizes: `"sm" | "md" | "lg"`.
  * `ProfileDropdown`:

    * Shows current user and email.
    * Renders a menu of actions plus a dedicated “Sign out” button with loading state.
    * Handles outside clicks, Escape key, and focus management.

* **Navigation**

  * `TabsRoot`, `TabsList`, `TabsTrigger`, `TabsContent`:

    * Accessible tab system with ARIA roles.
    * Arrow‑key navigation (`Left/Right`, `Home/End`).
    * Manages tab focus separately from selection.
  * `ContextMenu`:

    * Portal‑based right‑click menu.
    * Positions itself within the viewport.
    * Supports keyboard navigation (Arrow keys, Enter, Esc).
    * Accepts items with labels, icons, shortcuts, and danger/disabled states.

* **Search**

  * `GlobalSearchField`:

    * Controlled or uncontrolled input with:

      * Optional **scope label** (e.g. “Within workspace”),
      * Global shortcut (`⌘K` / `Ctrl+K` by default).
    * Supports:

      * Suggestions list with keyboard navigation (`↑/↓`, Enter, Esc),
      * Loading state,
      * Custom suggestion rendering,
      * Optional filter chips at the bottom of the dropdown,
      * Empty‑state content.
  * `GlobalTopBar` embeds a `GlobalSearchField` into the global header with responsive layout.

* **Code editor**

  * `CodeEditor`:

    * Lazy‑loads Monaco editor via `React.Suspense`.
    * Exposes a `CodeEditorHandle` (focus + revealLine).
    * Accepts `language`, `path`, `theme`, `readOnly`, and `onSaveShortcut`.
    * Used primarily in the Config Builder workbench.

These components ensure consistent layout, accessibility, and styling across ADE Web while keeping the app’s structure relatively simple.

---

## Summary

ADE Web is the operational and configuration console for Automatic Data Extractor:

* **Analysts** use it to upload documents, run extractions, inspect runs, and download outputs.
* **Workspace owners / engineers** use it to evolve Python‑based config packages, validate and test changes, and safely roll out new versions using the Config Builder workbench.
* **Admins** use it to manage workspaces, members, roles, SSO hints, and safe mode.

This README captures:

* The **conceptual model** (workspaces, documents, runs, configs, safe mode, roles),
* The **navigation and URL‑state conventions** (custom history, SPA links, search params, deep linking),
* The **Config Builder workbench model** (file tree, tabs, ADE script helpers, console, validation, inspector, theme, window states),
* The **backend contracts** ADE Web expects,
* And the **front‑end architecture & UI components** that support the user experience.

As long as backend implementations respect these concepts and contracts, ADE Web can remain stable and backend‑agnostic, even as internal infrastructure evolves.
```

# apps/ade-web/docs/01-domain-model-and-naming.md
```markdown
# 01-domain-model-and-naming

**Purpose:** Single source of truth for concepts, vocabulary, and naming rules. Every other doc links back here instead of redefining things.

### 1. Overview

* What this doc is and why it exists.
* “If you’re unsure what to call something, check this first.”
* Scope: domain language, UI labels, and core TypeScript type names.

### 2. Core entities

For each, define:

* Canonical **name** (UI term).
* One-line definition.
* Primary **identifiers** (id/slug).
* Main **screen(s)** and **primary API endpoints**.

Entities to cover:

* **Workspace directory** vs **Workspace shell**.
* **Workspace** (owner of documents, runs, configs, members).
* **Document**.
* **Run** (the main term in the UI – “run” vs “run”).
* **Run** (if used in the UI at all) – or explicitly state it’s a backend/internal name only.
* **Build** (Config build, not engine build if there’s a distinction).
* **Configuration / Config** (and how those two words are used).
* **Config version** (draft / active / inactive).
* **User** vs **Member** vs **Principal**.
* **Role** / **Permission** / **Role assignment**.
* **Safe mode** (system vs workspace scoped if you ever add workspace scope).

### 3. Statuses and lifecycles

Subsections:

* **Documents**

  * Allowed statuses and meanings: `uploaded`, `processing`, `processed`, `failed`, `archived`.
  * Trigger events that move between statuses (upload, run start, run completion, delete/archive).

* **Runs**

  * Allowed statuses: `queued`, `running`, `succeeded`, `failed`, `cancelled`.
  * Relationship to runs/builds if relevant.
  * How these map to badge colours in the UI (high-level).

* **Configurations / Config versions**

  * Lifecycle states: `Draft`, `Active`, `Inactive`.
  * Allowed transitions (Draft → Active, Active → Inactive, etc.).
  * How “publish” vs “activate” vs “deactivate” map onto these states.

* **Safe mode**

  * `enabled`/`disabled`.
  * What “turned on” means in UX terms (all engine-invoking actions blocked).

### 4. Naming rules and conventions

* **UI vs backend naming:**

  * Use **Run** consistently in the UI for `/runs`.
  * Reserve **Run** for engine-level concepts or API object names if needed.
  * Use **Config** for UX & helper code (`ConfigList`, `useConfigsQuery`).
  * Use **Configuration** for TS types that mirror backend data (`Configuration`, `ConfigurationVersion`).

* **Type names:**

  * Singular, PascalCase domain types: `Workspace`, `WorkspaceSummary`, `Document`, `RunSummary`, `Configuration`, `ConfigVersion`.
  * `Summary` for list-row types, `Detail` for fully hydrated types.

* **Hook names:**

  * Queries: `use<Domain><What>Query` (`useDocumentsQuery`, `useRunsQuery`).
  * Mutations: `use<Verb><Domain>Mutation` (`useUploadDocumentMutation`).
  * UI state: `use<Something>State` or explicit (`useWorkbenchUrlState`, `useSafeModeStatus`).

* **File and component names:**

  * Screens: `<Domain>Screen.tsx` (`DocumentsScreen`, `RunsScreen`).
  * Shells: `WorkspaceShellScreen`.
  * Presentational components: `GlobalTopBar`, `ProfileDropdown`, `DocumentsTable`.

### 5. Term → Route → Type → Component mapping

* A table mapping:

  * Domain term → Primary URL → Main TS type(s) → Screen component(s).

* Example rows:

  * Workspace, Document, Run, Configuration, Config version, Safe mode.

### 6. Reserved and non-preferred terms

* List of words we **don’t** use, or aliases we explicitly discourage:

  * Don’t call a workspace a “project”.
  * Don’t call runs “tasks”.
  * Don’t call configs “pipelines” in the UI.
  * etc.

* The goal: reduce synonym noise for humans and AI.
```

# apps/ade-web/docs/02-architecture-and-project-structure.md
```markdown
# 02-architecture-and-project-structure

**Purpose:** Show where everything lives, what imports what, and how to name files and modules.

### 1. Overview

* Goal: “You can glance at the repo tree and know where to put/lookup code.”
* Relationship to 01 (concepts) and 03 (routing).

### 2. Directory layout

Describe the intended layout, e.g.:

```text
apps/ade-web/
  src/
    app/
    features/
    ui/
    shared/
    schema/
    generated-types/
    test/
```

For each top level:

* **`app/`**

  * `App.tsx`, `ScreenSwitch.tsx`, `NavProvider`, `AppProviders`.
  * Global shells, providers, and composition only. No domain details.

* **`features/`**

  * Route/feature slices (was `screens`).
  * Subfolders: `auth`, `workspace-directory`, `workspace-shell/documents`, `runs`, `config-builder`, `settings`, `overview`.
  * Each subfolder contains the screen component(s), feature-specific hooks, and sub-components.

* **`ui/`**

  * Reusable, presentational components: buttons, form controls, layout primitives, top bar, search, code editor, etc.
  * No domain logic, no API calls.

* **`shared/`**

  * Cross-cutting hooks and utilities:

    * `urlState`, `storage`, `ndjson`, `keyboard`, `permissions`, etc.
  * No React components that render UI.

* **`schema/`**

  * Hand-written domain models / Zod schemas / mappers.

* **`generated-types/`**

  * Code-generated TypeScript types from backend schemas (if used).

* **`test/`**

  * Vitest `setup.ts`.
  * Shared factories and helpers.

### 3. Module responsibility and dependencies

Spell out allowed imports:

* `ui/` does **not** import from `features/` or `app/`.
* `shared/` does **not** import from `features/` or `ui/`.
* `features/*` may import from `ui/`, `shared/`, `schema/`, `generated-types/`.
* `app/` may import from all of the above, but tries to stay thin.

Explain the rationale: this keeps circular deps and “god modules” at bay.

### 4. Aliases

Document the Vite/TS paths:

* `@app` → `src/app`
* `@features` or `@screens` → `src/features`
* `@ui` → `src/ui`
* `@shared` → `src/shared`
* `@schema` → `src/schema`
* `@generated-types` → `src/generated-types`
* `@test` → `src/test`

Mention: we prefer `@features` going forward, but keep `@screens` as a compatibility alias if needed.

### 5. File & naming conventions

* **Screens & shells:**

  * `DocumentsScreen.tsx`, `RunsScreen.tsx`, `ConfigBuilderScreen.tsx`, `WorkspaceShellScreen.tsx`.

* **Feature components:**

  * Feature-scoped chunks: `DocumentsTable.tsx`, `RunsFilters.tsx`, `ConfigList.tsx`.

* **Hooks:**

  * In feature folders: `useDocumentsQuery.ts`, `useSubmitRunMutation.ts`.
  * In `shared/`: `useSafeModeStatus.ts`, `useSearchParams.ts`.

* **API modules:**

  * `authApi.ts`, `workspacesApi.ts`, `documentsApi.ts`, `runsApi.ts`, `configsApi.ts`, `buildsApi.ts`, `rolesApi.ts`.
  * Thin, typed wrappers around fetch/axios.

* **Barrels (optional):**

  * Where, if anywhere, you allow `index.ts` barrels, and what they can re-export.

### 6. Example: walkthrough of one feature folder

* Pick `features/workspace-shell/documents/` and show:

  * `DocumentsScreen.tsx`
  * `DocumentsTable.tsx`
  * `useDocumentsQuery.ts`
  * `documentsApi.ts` (or imported from shared API folder)
  * How they compose.
```

# apps/ade-web/docs/03-routing-navigation-and-url-state.md
```markdown
# 03-routing-navigation-and-url-state

**Purpose:** Explain how URLs map to screens, how navigation works, and how query parameters encode view state.

### 1. Overview

* SPA on top of `window.history`.
* Custom router (`NavProvider`) instead of React Router.
* URL is the single source of truth for where you are.

### 2. App entry and top-level routes

* `main.tsx` → `<App>` → `NavProvider` → `AppProviders` → `ScreenSwitch`.

* Top-level paths:

  * `/`, `/login`, `/auth/callback`, `/setup`, `/logout`.
  * `/workspaces`, `/workspaces/new`.
  * `/workspaces/:workspaceId/...`.
  * Global not-found.

* Explain trailing slash normalization (`/foo/` → `/foo`).

### 3. Workspace routes

* Structure of workspace URLs:

  * `/workspaces/:workspaceId/documents`
  * `/workspaces/:workspaceId/runs`
  * `/workspaces/:workspaceId/config-builder`
  * `/workspaces/:workspaceId/settings`
  * `/workspaces/:workspaceId/overview` (optional).

* How “unknown section” in a workspace produces a workspace-local 404 instead of global 404.

### 4. Custom navigation layer

* Types:

  * `LocationLike`
  * `NavigationIntent`
  * `NavigationBlocker`

* `NavProvider`:

  * Tracks `location` from `window.location`.
  * Listens to `popstate`.
  * Runs navigation blockers and can cancel navigation.

* `useLocation()` and `useNavigate()`:

  * How `navigate(to, { replace? })` works.
  * Using `URL` to resolve relative links.

* `useNavigationBlocker()`:

  * How editors like Config Builder prevent losing unsaved changes.
  * Pattern for “save then navigate” flows.

### 5. SPA links

* `Link`:

  * Always renders `<a href={to}>`.
  * Intercepts unmodified left clicks and calls `navigate`.
  * Lets modified clicks (Cmd+Click, Ctrl+Click) behave normally.

* `NavLink`:

  * Active state logic: `end` vs prefix matching.
  * API (`className`, `children` as render function `{ isActive }`).

### 6. URL search parameters

* Helpers:

  * `toURLSearchParams`, `getParam`, `setParams`.

* `useSearchParams()`:

  * Return values and how to update (`setSearchParams(init, { replace })`).
  * When to prefer `replace` to avoid history spam.

### 7. SearchParamsOverrideProvider

* What it is:

  * Provider that intercepts `useSearchParams()` within its subtree.

* When it’s allowed:

  * Embedded flows that need “fake” query state.
  * Migration/legacy cases.

* Rule: Most screens should use real URL search; overrides are advanced/rare.

### 8. Important query parameters (global view)

* **Auth**: `redirectTo`:

  * Only relative paths allowed.
  * Validation rules to avoid open redirects.

* **Settings**: `view`:

  * `general`, `members`, `roles`.

* **Documents**: `q`, `status`, `sort`, `view`.

* **Config Builder**: overview (just names; full details in doc 09):

  * `tab`, `pane`, `console`, `view`, `file`.
```

# apps/ade-web/docs/04-data-layer-and-backend-contracts.md
```markdown
# 04-data-layer-and-backend-contracts

**Purpose:** Show how the frontend talks to `/api/v1/...`, how it uses React Query, and how streaming works.

### 1. Overview

* Relationship to backend: ADE Web is backend-agnostic but expects certain API contracts.
* High-level goal: each domain has a clear API module + hooks.

### 2. React Query configuration

* `AppProviders`:

  * Single `QueryClient` instance via `useState`.
  * Default options (`retry`, `staleTime`, `refetchOnWindowFocus`).

* Pattern:

  * Query hooks wrap QueryClient with strongly typed API functions.
  * Mutations for writes.

### 3. HTTP client pattern

* Describe the standard fetch wrapper:

  * JSON parse, error handling, auth headers.
  * Optional base URL (`/api` via Vite proxy).

* Structure:

  * Domain modules: `authApi.ts`, `workspacesApi.ts`, `documentsApi.ts`, `runsApi.ts`, `configsApi.ts`, `buildsApi.ts`, `runsApi.ts`, `rolesApi.ts`, etc.

* Function naming:

  * `listWorkspaces`, `createWorkspace`, `listDocuments`, `uploadDocument`, `listRuns`, `submitRun`, `listConfigurations`, `activateConfiguration`, etc.

### 4. Mapping ADE API routes to modules

Group the routes (from your CSV) by domain:

* **Auth & session (`authApi`)**

  * `/api/v1/auth/session`, `/auth/session/refresh`, `/auth/sso/login`, `/auth/sso/callback`, `/auth/me`, `/users/me`, `/setup`, `/setup/status`, auth providers, API keys.

* **Permissions & roles (`rolesApi`)**

  * `/api/v1/permissions`, `/me/permissions`, `/me/permissions/check`.
  * Global roles and role assignments: `/roles`, `/role-assignments`.

* **Workspaces (`workspacesApi`)**

  * `/api/v1/workspaces` CRUD.
  * `/workspaces/{workspace_id}/default`.
  * `/workspaces/{workspace_id}/members` (+ roles).
  * `/workspaces/{workspace_id}/roles`.
  * `/workspaces/{workspace_id}/role-assignments`.

* **Documents (`documentsApi`)**

  * `/workspaces/{workspace_id}/documents`.
  * `/documents/{document_id}` CRUD, `/download`, `/sheets`.

* **Runs & runs (`runsApi`, `runsApi`)**

  * `/workspaces/{workspace_id}/runs` (ledger, artifact, logs, outputs).
  * `/api/v1/runs/{run_id}...` if used directly.

* **Configurations & builds (`configsApi`, `buildsApi`)**

  * Workspace configs: `/workspaces/{workspace_id}/configurations` and `/versions`.
  * Activation/publish: `/activate`, `/deactivate`, `/publish`.
  * Files/directories: `/files`, `/files/{file_path}`, `/directories/{directory_path}`, `/export`.
  * Builds: `/workspaces/{workspace_id}/configs/{config_id}/builds` & `/builds/{build_id}`.

* **System & safe mode (`systemApi`)**

  * `/api/v1/health`, `/api/v1/system/safe-mode`.

Explain:

* Not every endpoint is necessarily surfaced in the UI today, but grouping should still be stable.

### 5. Typed models

* How `schema/` and `generated-types/` are used:

  * Domain models: `WorkspaceSummary`, `DocumentSummary`, `RunSummary`.
  * Generated models from backend schemas.

* Mapping patterns:

  * “Wire → domain” transform functions if you don’t use generated types directly.

### 6. Streaming NDJSON endpoints

* Endpoints:

  * Build logs: `/builds/{build_id}/logs`.
  * Run logs: `/runs/{run_id}/logs`, `/runs/{run_id}/logs` (depending on which you use).

* Abstractions in `shared/ndjson`:

  * Generic NDJSON stream parser.
  * Hook patterns, e.g. `useNdjsonStream(endpoint, options)`.

* Consumption in features:

  * Build console in Config Builder.
  * Run detail view console.

### 7. Error handling & retries

* Normalised error shape in the client:

  * HTTP status, message, optional code.

* Where 401/403 are handled:

  * Global handler (logout/redirect).
  * Local for permission errors (inline `Alert`).

* Patterns:

  * Toast vs inline error vs full error state.
  * When to `retry: false` in React Query (for permission errors).
```

# apps/ade-web/docs/05-auth-session-rbac-and-safe-mode.md
```markdown
# 05-auth-session-rbac-and-safe-mode

**Purpose:** All auth, identity, permissions, and safe mode behaviour in one place.

### 1. Overview

* Relationship to backend auth system.
* High-level flow: setup → login → workspace selection.

### 2. Initial setup flow

* `/api/v1/setup/status`, `/api/v1/setup`:

  * When we show the first-run setup screen.
  * Only first admin can complete it.

### 3. Authentication flows

* **Email/password**

  * `/api/v1/auth/session` POST/DELETE/refresh.
  * How login form works, where errors are shown.

* **SSO**

  * `/api/v1/auth/sso/login` and `/auth/sso/callback`.
  * “Choose provider” screen if multiple providers exist.

* **Redirects**

  * Use of `redirectTo` query param.
  * Validation rules (no external redirect).

### 4. Session & identity

* Canonical “who am I?” endpoint(s):

  * `/api/v1/auth/session` and/or `/users/me`.

* What the session data contains:

  * User id, name, email.
  * Global permissions.
  * Possibly workspace memberships with roles.

* Where session is cached:

  * In React Query as a `session` query.
  * Short-term in memory; no long-term storage of tokens in localStorage.

### 5. Roles & permissions model

* **Global roles & assignments**

  * `/roles`, `/role-assignments`.
  * Used for system-wide capabilities (like listing all users).

* **Workspace roles & assignments**

  * `/workspaces/{workspace_id}/roles`.
  * `/workspaces/{workspace_id}/role-assignments`.
  * Membership list and role editing in Settings.

* **Permissions**

  * Catalog (`/permissions`) and effective permissions (`/me/permissions`).
  * Permission key naming convention (e.g. `Workspace.Members.ReadWrite`, `Workspaces.Create`).

### 6. Permission checks in the UI

* Helpers in `shared/permissions`:

  * `hasPermission(permissions, key)`.
  * `hasAnyPermission(permissions, keys)`.

* Guidelines:

  * Hide vs disable:

    * Hide controls for actions the user should not be aware of.
    * Disable with tooltip for actions the user *knows* exist but cannot use (e.g. safe mode toggle).

* Examples:

  * Create workspace button.
  * Settings tabs.
  * Config activate/deactivate buttons.

### 7. Safe mode behaviour

* Reading `/api/v1/system/safe-mode`:

  * Polling or refetch triggers.

* Exactly what is blocked:

  * New runs/runs.
  * Config builds/validations.
  * Activate/publish actions.

* UI treatment:

  * Global banner inside workspace shell.
  * Disabled buttons with informative tooltips (“Safe mode is enabled: <message>”).

* Permissions:

  * Which permission is required to toggle safe mode.
  * How the Safe mode controls are shown only to authorised users.

### 8. Security considerations

* CSRF/credentials model:

  * E.g. cookie-based sessions with `sameSite` and CSRF token if applicable.

* CORS:

  * Mention reliance on Vite `/api` proxy in dev.

* Sensitive data:

  * Never store secrets or tokens in localStorage.
  * State persistence keys only hold preferences.
```

# apps/ade-web/docs/06-workspace-layout-and-sections.md
```markdown
# 06-workspace-layout-and-sections

**Purpose:** Describe the global UX frame: top bar, nav, directory, shell, and where each section fits.

### 1. Overview

* Two layers:

  * Workspace directory.
  * Workspace shell.

* How they share top bar, safe mode banner, notifications.

### 2. GlobalTopBar

* Slots:

  * `brand`, `leading`, `actions`, `trailing`, `secondaryContent`.

* Where `GlobalSearchField` appears:

  * In directory: workspace search.
  * In shell: workspace-scoped search (documents/runs/configs).

* Responsive behaviour:

  * How it collapses on small screens.

### 3. Workspace directory (`/workspaces`)

* Layout:

  * Heading, subtitle.
  * Workspace search with ⌘K / Ctrl+K.
  * “Create workspace” button with permission gating.

* States:

  * No workspaces / can create → CTA to create workspace.
  * No workspaces / cannot create → explain they need to be invited.

* Workspace cards:

  * Name, slug, default badge, roles summary.
  * Click behaviour (enter workspace shell to default section).

* Right-hand panel content (guidance/checklist).

### 4. Workspace shell (`/workspaces/:workspaceId/...`)

* Left navigation (desktop):

  * Workspace avatar/name.
  * Switch workspace affordance.
  * Sections: Documents, Runs, Config Builder, Settings, Overview.
  * Collapse/expand and per-workspace persistence.

* Mobile navigation:

  * Slide-in panel, open/close triggers.
  * Scroll lock and dismissal rules.

* Top bar in shell:

  * Workspace name + environment label.
  * Contextual search.
  * Profile dropdown.

### 5. Sections overview

For each section, 1–2 paragraphs and link to the detailed doc:

* **Documents** (doc 07).
* **Runs** (doc 07).
* **Config Builder** (docs 08–09).
* **Settings** (doc 05 for RBAC + this for UX).
* **Overview** (optional).

Mention, briefly:

* Primary goals of each section.
* Typical entry points from other sections.

### 6. Global banners & notifications

* Where safe mode banners render (inside workspace shell).
* Where error/info banners appear for cross-cutting issues.
* Where toast notifications originate and what they’re used for.
```

# apps/ade-web/docs/07-documents-runs-and-runs.md
```markdown
# 07-documents-runs-and-runs

**Purpose:** All operator workflows: working with documents, runs, and runs.

### 1. Overview

* Audience: analysts/operators, but written for implementers.
* Relationship to doc 01 (domain definitions).

### 2. Documents domain model

* Recap of document fields:

  * `id`, `name`, `contentType`, `size`, `status`, timestamps, `uploader`, `last_run`.

* Status transitions:

  * `uploaded` → `processing` → `processed` / `failed`.
  * `archived` and how it is reached.

* Immutability:

  * Re-uploading creates new document ID.

### 3. Documents screen behaviour

* List filtering:

  * Query `q`, status filters, sorting (`-created_at`, `-last_run_at`).
  * View presets: `mine`, `team`, `attention`, `recent` (if you have them).

* Upload flow:

  * Upload button + ⌘U / Ctrl+U.
  * Progress & error states.

* Row content:

  * What we show per document (type icon, size, last run status, uploader).

* Actions:

  * Run extraction.
  * Download original file.
  * Archive/delete.

### 4. Document sheets

* `/documents/{document_id}/sheets` expectations:

  * Fields: `name`, index, `is_active`.

* Sheet-selection UX:

  * When sheet list is fetched.
  * How we show checkboxes or multi-select.

* Fallback behaviour:

  * If endpoint missing or fails → show warning and “Use all worksheets”.

### 5. Runs (workspace ledger)

* Run fields recap:

  * `id`, `status`, timestamps, initiator, config version, input documents, outputs.

* Runs screen:

  * Filters: status, config, date range, initiator.
  * Columns: Run ID, status, config, created at, duration, initiator.

* Run detail view:

  * Link path (e.g. `/workspaces/:id/runs/:runId` if you have it).
  * Tabs/panels for logs, telemetry, outputs.

### 6. Runs and run options

* How “run” vs “run” are presented:

  * If the UI only exposes runs, say so.
  * If there’s a separate “run detail” surface, describe it.

* Run options:

  * `dry_run`, `validate_only`, `input_sheet_names`.
  * Where/how they are exposed in UI (e.g. advanced settings in run dialog).

### 7. Per-document run preferences

* What’s remembered:

  * Preferred config, config version, sheet subset, maybe run options.

* Where it’s stored:

  * LocalStorage key pattern: `ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences`.

* Behaviour:

  * Applied automatically when opening the run dialog again.
  * How to reset/override.

* Cross-link to doc 10 section on persistence.

### 8. Backend contracts for documents & runs

* Endpoint list with quick notes:

  * Documents: `/workspaces/{workspace_id}/documents`, `/documents/{document_id}`, `/download`, `/sheets`.
  * Runs: `/workspaces/{workspace_id}/runs`, `/runs/{run_id}/artifact`, `/logs`, `/outputs`.

* Mapping to hooks:

  * `useDocumentsQuery`, `useUploadDocumentMutation`, `useRunsQuery`, `useRunOutputsQuery`, etc.
```

# apps/ade-web/docs/08-configurations-and-config-builder.md
```markdown
# 08-configurations-and-config-builder

**Purpose:** Conceptual model for configurations and the non-editor parts of the Config Builder.

### 1. Overview

* What a configuration is (workspace-scoped config package).
* Relationship to underlying Python package and engine.

### 2. Configurations domain model

* Fields (id, name, display name, status, active version).
* Relationship with config versions (each config has multiple versions).

### 3. Config version lifecycle

* States: Draft, Active, Inactive (per doc 01).

* Actions and mappings:

  * Create/clone → new draft.
  * Validate/build draft.
  * Publish/activate → becomes active, previous active becomes inactive.
  * Deactivate/archive (if supported).

* How backend routes map:

  * `/configurations/{config_id}/publish`, `/activate`, `/deactivate`.
  * `/configurations/{config_id}/versions`.

### 4. Configurations list UI

* Columns:

  * Name, id, active version, draft state, last updated.

* Actions:

  * Open editor (workbench).
  * Clone from existing version.
  * Export configuration.
  * Activate/deactivate/publish.

* Filters/search on configs.

### 5. Manifest overview

* What the manifest describes:

  * Tables, columns, transforms, validators, options.

* How ADE Web uses it:

  * For display, column ordering, toggles for `enabled`, `required`.
  * To wire scripts (transforms, validators) via manifest references.

* Patch model:

  * ADE Web sends partial updates.
  * Rule: preserve unknown fields for forward compatibility.

### 6. Entering and exiting the workbench

* Routes & navigation:

  * How we navigate from `/config-builder` list to the workbench (e.g. query param with `configId` or deeper route).

* Return path:

  * Storage key: `ade.ui.workspace.<workspaceId>.workbench.returnPath`.
  * How we store the path before entering and restore on exit.

### 7. Safe mode interaction

* Which actions are disabled in safe mode:

  * Build, validate, publish/activate, run extraction from builder.

* Visual feedback:

  * Disabled build/run buttons and tooltip copy.
  * Cross-link to doc 05.

### 8. Backend contracts for configurations

* Key endpoints:

  * Listing configs: `/workspaces/{workspace_id}/configurations`.
  * Detail: `/configurations/{config_id}`.
  * Versions: `/configurations/{config_id}/versions`.
  * Export: `/configurations/{config_id}/export`.
  * Validate: `/configurations/{config_id}/validate`.

* How these map to hooks: `useConfigurationsQuery`, `useConfigVersionsQuery`, etc.
```

# apps/ade-web/docs/09-workbench-editor-and-scripting.md
```markdown
# 09-workbench-editor-and-scripting

**Purpose:** Deep dive into the IDE-like Config Builder workbench: layout, file tree, tabs, console, URL state, and ADE script helpers.

### 1. Overview

* Workbench is an “editor window” that can be docked/maximised.
* Reused concepts: `WorkbenchWindow`, console, validation pane.

### 2. Workbench window states

* **Restored**:

  * Embedded in Config Builder section.

* **Maximised**:

  * Full viewport overlay, workspace shell dimmed.

* **Docked / minimised**:

  * Hidden, with a dock UI to restore.

* Controls:

  * Minimise/maximise/close buttons.
  * Unsaved-changes behaviour and blockers.

### 3. Layout and panels

* **Activity bar**:

  * Modes: explorer, search (future), SCM (future), extensions (future), settings.

* **Explorer panel**:

  * File tree, iconography, context menu.

* **Editor area**:

  * Tab strip (pinned & unpinned tabs).
  * Code editor.

* **Bottom panel**:

  * Tabs: Console, Validation.

* **Inspector panel**:

  * Metadata: size, modifiedAt, contentType, ETag.
  * Load status and dirty state.

* Resize behaviour and persistence of panel sizes.

### 4. File tree model

* Types:

  * `WorkbenchFileKind`, `WorkbenchFileMetadata`, `WorkbenchFileNode`.

* Building from backend listing:

  * Using a flat `FileListing` with `path`, `name`, `kind`, `depth`.
  * `createWorkbenchTreeFromListing`.
  * Folder creation, path normalisation, sorting (folders first).

* Helper functions:

  * `extractName`, `deriveParent`, `findFileNode`, `findFirstFile`.

### 5. Tabs, content, and persistence

* `WorkbenchFileTab` fields:

  * `id`, `name`, `language`, `initialContent`, `content`, `status`, `etag`, `pinned`, `saving`, `saveError`, `lastSavedAt`.

* `useWorkbenchFiles` hook responsibilities:

  * Open/close tabs.
  * MRU order and keyboard navigation.
  * Lazy content loading & dirty tracking.
  * Save flow and ETag concurrency handling.

* Persistence:

  * `PersistedWorkbenchTabs` structure.
  * LocalStorage key: `ade.ui.workspace.<workspaceId>.config.<configId>.tabs`.

### 6. Workbench URL state

* Types:

  * `ConfigBuilderTab`, `ConfigBuilderPane`, `ConfigBuilderConsole`, `ConfigBuilderView`, `ConfigBuilderSearchState`.

* `readConfigBuilderSearch`:

  * Parsing from URL, normalising, tracking `present` flags.

* `mergeConfigBuilderSearch`:

  * How patches are applied and defaults removed from the URL.

* `useWorkbenchUrlState`:

  * API: `fileId`, `pane`, `console`, `consoleExplicit`, setters.
  * Strategy for preferring URL vs persisted state when both exist.

### 7. Console and validation panels

* **Console**:

  * Receives build and run events from NDJSON streams.
  * Shows log text and a run summary card.

* **Validation**:

  * Structured issues (severity, path, message).
  * Populated from validation endpoint results.

* Persistence:

  * `ConsolePanelPreferences` (`version`, `fraction`, `state`).
  * Key: `ade.ui.workspace.<workspaceId>.config.<configId>.console`.

### 8. Editor and theme preference

* `CodeEditor` component:

  * Props: `language`, `path`, `theme`, `readOnly`, `onSaveShortcut`.
  * `CodeEditorHandle` (focus + revealLine).

* Theme preference:

  * `EditorThemePreference` (`system` | `light` | `dark`).
  * `EditorThemeId` (`ade-dark`, `vs-light`).
  * LocalStorage key: `ade.ui.workspace.<workspaceId>.config.<configId>.editor-theme`.
  * System dark/light detection.

### 9. ADE script helpers and script API

* `registerAdeScriptHelpers`:

  * Scope detection based on file paths (`row_detectors`, `column_detectors`, `hooks`).
  * Features: hover docs, completions, signature help.

* Expected function signatures:

  * Row detectors.
  * Column detectors.
  * Transforms.
  * Validators.
  * Hooks (`on_run_start`, `after_mapping`, `before_save`, `on_run_end`).

* Note: helpers are guidance only, not enforcement of backend behaviour.
```

# apps/ade-web/docs/10-ui-components-a11y-and-testing.md
```markdown
# 10-ui-components-a11y-and-testing

**Purpose:** Document reusable UI components, accessibility patterns, keyboard shortcuts, and testing strategy. Also centralise state persistence key patterns.

### 1. Overview

* `src/ui` as app-specific component library.
* Target: consistent look/feel and accessible defaults.

### 2. Design tokens & theming (lightweight)

* Briefly describe:

  * Tailwind as the utility layer.
  * Any global CSS variables (spacing, typography, colours) if you have them.

* Editor theme vs overall app theme (if relevant).

### 3. Core components

Group and briefly describe patterns, not every prop:

* **Buttons**

  * `Button` variants (`primary`, `secondary`, `ghost`, `danger`), sizes, `isLoading`.
  * `SplitButton` for build control: primary action + menu.

* **Forms**

  * `Input`, `TextArea`, `Select`.

  * Error states via `invalid` and `aria-invalid`.

  * `FormField`: label, hint, error; wiring `id`/`aria-describedby`.

* **Feedback**

  * `Alert` (`info`, `success`, `warning`, `danger`).
  * When to use alert vs banner vs toast.

* **Identity**

  * `Avatar` (initials, sizes).
  * `ProfileDropdown` (actions, sign-out behaviour).

* **Navigation**

  * Tabs components (`TabsRoot`, `TabsList`, `TabsTrigger`, `TabsContent`).
  * `ContextMenu` for explorer, tabs, etc.

* **Search & top bar**

  * `GlobalSearchField`: behaviour, keyboard shortcut, suggestions.
  * `GlobalTopBar`: general usage.

* **Code editor**

  * `CodeEditor`: cross-link to 09 for advanced details.

### 4. Accessibility patterns

* **Tabs**

  * ARIA roles and keyboard navigation (`Left/Right`, `Home/End`).

* **Menus and dropdowns**

  * Focus trapping, `Esc` behaviour, arrow navigation.

* **Alerts and banners**

  * Use of `role="status"` or `role="alert"` where appropriate.

* **Forms**

  * `aria-invalid`, `aria-describedby` integration via `FormField`.

* **Modals and overlays**

  * Focus management for maximised workbench and dialogs.

### 5. Keyboard shortcuts

* **Global**

  * `⌘K` / `Ctrl+K`: open search.
  * `⌘U` / `Ctrl+U`: document upload (where enabled).

* **Workbench**

  * `⌘S` / `Ctrl+S`: save active editor file.
  * `⌘B` / `Ctrl+B`: build/reuse environment.
  * `⇧⌘B` / `Ctrl+Shift+B`: force rebuild.
  * `⌘W` / `Ctrl+W`: close active tab.
  * `⌘Tab` / `Ctrl+Tab`: recent-tab forward.
  * `⇧⌘Tab` / `Shift+Ctrl+Tab`: backward.
  * `Ctrl+PageUp/PageDown`: cycle by visual tab order.

* Scope rules:

  * Shortcuts only active when relevant area is focused.
  * Avoid overriding browser basics on generic inputs.

### 6. Notifications

* **Toasts**

  * Transient success/warning messages (saves, small errors).

* **Banners**

  * Cross-section warnings: safe mode, connectivity issues.
  * How they are composed from `Alert` + higher-level plumbing.

### 7. State persistence & user preferences (central summary)

* Prefix convention:

  * `ade.ui.workspace.<workspaceId>...`.

* Key patterns:

  * `...nav.collapsed`
  * `...workbench.returnPath`
  * `...config.<configId>.tabs`
  * `...config.<configId>.console`
  * `...config.<configId>.editor-theme`
  * `...document.<documentId>.run-preferences`

* Rules:

  * Preferences are per-user, per-workspace.
  * Data stored is non-sensitive and safe to clear.
  * Clearing localStorage should not corrupt server state.

* Cross-links:

  * Back to docs 07 and 09 where each preference is introduced in context.

### 8. Dev & testing workflow

* **Vite dev server**

  * Host/port env vars.
  * `/api` proxy behaviour.

* **Vitest configuration**

  * JSDOM environment.
  * `setup.ts` for mocks/polyfills.
  * Coverage via v8.

* **Testing strategy**

  * Utils in `shared/`: unit tests.
  * UI components in `ui/`: component tests.
  * Feature flows in `features/`: integration tests (navigation, streams, RBAC behaviours).
```
