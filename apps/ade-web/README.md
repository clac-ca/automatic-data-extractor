# ADE Web

ADE Web is the browser‑based front‑end for the **Automatic Data Extractor (ADE)** platform.

It serves two main personas:

- **Workspace owners / engineers** – design and evolve **Configurations** (backed by Python configuration packages / `ade_config` projects) that describe how documents are processed; manage Safe mode; and administer workspaces, SSO, roles, and members using the **Configuration Builder** workbench.
- **End users / analysts / operators** – upload documents, run extractions, monitor progress, inspect logs and telemetry, and download structured outputs.

This document describes **what** ADE Web does and the behaviour it expects from any compatible backend. It is intentionally **backend‑agnostic** and should be treated as the product‑level specification for ADE Web and its contracts with the backend.

---

## Contributing quick start

- Name things after the domain: `Workspace`, `Run`, `Configuration`, `ConfigVersion`, `Document`; keep routes/sections aligned (`/documents`, `/runs`, `/config-builder`, `/settings`) and mirror them under `screens/workspace-shell/sections`.
- Use canonical homes: build URLs via `@shared/nav/routes`; keep query params consistent with `docs/03`, `docs/06`, `docs/07` and the filter helpers they describe; source permission keys from `@schema/permissions` plus helpers in `@shared/permissions`.
- Reuse patterns instead of inventing new ones: copy the Documents/Runs list/detail and filter approach, and reuse the NDJSON streaming helper and event model.
- Respect layer boundaries: do not import from “upwards” layers; ESLint will flag `shared/` or `ui/` reaching into `screens/` or `app/`.
- See `CONTRIBUTING.md` and the numbered docs (`apps/ade-web/docs/01`–`10`) for the complete architecture reference.

---

## High‑level UX & layout

ADE Web has two major layers:

1. **Workspace directory** – where users discover and create workspaces.
2. **Workspace shell** – where users operate inside a specific workspace (Documents, Runs, **Configuration Builder**, Settings).

Both layers share common patterns:

- A **top bar** with brand/context, search, and profile menu.
- A main content area that adapts to desktop and mobile.
- A consistent approach to **navigation**, **URL state**, **Safe mode banners**, and **notifications**.

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
- A **short checklist** for new deployments (invite admins, configure roles, review configurations before production).

### Workspace shell layout (`/workspaces/:workspaceId/...`)

Inside a workspace, ADE Web uses a reusable **workspace shell**:

- **Left navigation (desktop)**:
  - Workspace avatar/initials and name.
  - “Switch workspace” affordance.
  - Primary sections:
    - Documents
    - Runs
    - Configurations (Configuration Builder)
    - Settings
  - Collapse/expand state is persisted **per workspace** (each workspace remembers nav compactness).

- **Top bar**:
  - Workspace name and optional environment label (e.g. “Production”, “Staging”).
  - Context‑aware **search** (via `GlobalSearchField`):
    - On **Documents**, it acts as a document‑scoped search.
    - Elsewhere, it can search within the workspace (sections, configurations, runs).
  - A profile dropdown (`ProfileDropdown`) with user display name/email and actions like “Sign out”.

- **Mobile navigation**:
  - The left nav becomes a slide‑in panel:
    - Opens via a menu button.
    - Locks body scroll while open.
    - Closes on navigation, tapping outside, or pressing Esc.

- **Safe mode banner**:
  - When Safe mode is active, a persistent banner appears within the workspace shell explaining that runs/builds are paused.

- **Notifications**:
  - Toasts for success/error messages.
  - Banners for cross‑cutting issues like Safe mode, connectivity, or workbench layout warnings.

Certain routes (especially the **Configuration Builder** workbench) can temporarily hide parts of the shell in favour of the immersive workbench layout.

---

## Core concepts

### Workspaces

A **workspace** is the primary unit of organisation and isolation:

- Owns **documents**, **runs**, **configurations**, and **membership/roles**.
- Has a human‑readable **name** and a stable **slug/ID** that appear in the UI and URLs.
- Has **settings** (name, slug, environment labels, Safe mode, etc.).
- Is governed by **workspace‑scoped RBAC**.

Users sign in, land on the **Workspace directory**, and then select (or create) a workspace before they can work with documents or configurations.

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
- Run dialogs (including the Configuration Builder **Test** dialog) can offer sheet‑level selection.

---

### Runs

Backend paths still use `/runs`; in the UI and TypeScript types we refer to the same entity as **Run** with the ID field `runId`.

A **Run** is a single execution of ADE against a set of inputs with a particular configuration version.

Key ideas:

- Runs are **workspace‑scoped** and usually tied to at least one document.
- Each run includes:
  - **Status**: `queued`, `running`, `succeeded`, `failed`, `cancelled`.
  - **Timestamps**:
    - Queued / created,
    - Started,
    - Completed / cancelled.
  - **Initiator** (user who triggered it, or system).
  - **Configuration version** used.
  - References to **input documents** (display names and counts).
  - Links to **outputs**:
    - An overall artifact (e.g. zipped outputs),
    - A list of named output files,
    - Logs/telemetry streams or downloads.
  - Optional **summary** and **error message**.

Run options (as supported by the backend) include:

Run options use the canonical `RunOptions` shape (camelCase in UI; backend uses
snake_case equivalents):

```ts
type RunMode = "normal" | "validation" | "test";

interface RunOptions {
  dryRun?: boolean;           // API: dry_run
  validateOnly?: boolean;     // API: validate_only
  forceRebuild?: boolean;     // API: force_rebuild (force env rebuild before run)
  inputSheetNames?: string[]; // API: input_sheet_names
  mode?: RunMode;             // optional view-model helper derived from flags
}
```

- `dryRun` – exercise the pipeline without emitting final outputs.
- `validateOnly` – run validators and checks only (a **validation run**, not a build).
- `forceRebuild` – request an environment rebuild before executing the run (backend
  also auto‑rebuilds when the environment is missing/dirty). Typically surfaced
  on validation/test flows rather than generic document runs.
- `inputSheetNames` – when provided, only these spreadsheet worksheets are processed.
- `mode` – optional label for UI/tests; typically `"validation"` for validation runs and `"test"` for sample runs.

See `docs/07-documents-and-runs.md` for the canonical `RunOptions` shape and API mapping.

**Build** always refers to an environment build (`Build` type via `/builds`). All
executions against documents—including validation runs and test runs—are `Run`
entities configured via `RunOptions`.

For a given document:

- ADE Web can remember **per‑document run preferences**:
  - Preferred configuration,
  - Preferred configuration version,
  - Preferred subset of sheet names.
- These preferences are stored in local, workspace‑scoped storage and reapplied the next time you run that document.

The backend exposes **streaming NDJSON APIs** for run events:

- ADE Web uses these for:
  - Live status updates,
  - Logs,
  - Telemetry summaries (rows processed, warnings, etc.).
- The same streams can be replayed to show historical run details.
- The Configuration Builder workbench reuses this to show build/run events inside its **Console**.

---

### Configurations & versions

A **Configuration** is the workspace concept ADE Web exposes. Each Configuration is **backed by a Python configuration package** (an `ade_config` project) that tells ADE how to:

- Interpret specific document formats,
- Validate incoming data,
- Transform them into structured outputs.

Per workspace:

- There may be **one or many** Configurations (e.g., per client, per pipeline).
- Each Configuration has **Configuration versions** (immutable snapshots).
- Exactly **one version is active per Configuration** for “normal” runs at any time.

#### Version lifecycle

Product‑level lifecycle:

- **Draft**
  - Fully editable.
  - Can be built, validated, and used for **test** runs.
- **Active**
  - Exactly one active version per Configuration.
  - Read‑only in the UI.
  - Used by default for new runs unless another version is explicitly selected.
- **Inactive**
  - Older or retired versions.
  - Not used for new runs.
  - Kept for history, audit, and rollback.

Backends may add internal states (e.g. “published”, “archived”), but ADE Web presents the lifecycle as **Draft → Active → Inactive**.

Typical flows:

1. Clone the **active** version (or a known‑good inactive one) into a new **draft**.
2. Edit code, configuration files, and manifest in the Configuration Builder.
3. Build the environment, run **validation runs**, and perform **test runs**
   against sample documents.
4. When satisfied, **activate** the draft:
   - It becomes **Active**.
   - The previous active version becomes **Inactive**.
5. Monitor early runs and adjust via new drafts as needed.

---

### Manifest & schema

Each configuration version exposes a structured **manifest** describing expected outputs and per‑table behaviour.

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
- Surfaces it in the Configuration Builder for:
  - Reordering columns,
  - Toggling enabled/required flags,
  - Linking transform/validator scripts.
- Sends **patches** to the backend, preserving unknown fields so the backend schema can evolve without breaking the UI.

---

### Safe mode

ADE includes a **Safe mode** kill switch for engine execution.

When **Safe mode is enabled**:

- Engine‑invoking actions are blocked, including:
  - New runs,
  - Environment builds,
  - Validation runs,
  - Test runs,
  - Activations.
- Read‑only operations continue to work:
  - Viewing documents,
  - Inspecting old runs,
  - Downloading existing artifacts.

Behaviour:

- Safe mode is **system‑wide**; optionally it can be extended with workspace scope.
- The backend exposes a **status endpoint** with:
  - `enabled: boolean`,
  - A human‑readable `detail` message.
- ADE Web periodically checks this status and:
  - Shows a banner with the detail message when enabled.
  - Disables “Run”, “Run extraction”, “Build”, “Test run”, and “Activate” buttons.
  - Uses clear tooltips (e.g. “Safe mode is enabled: …”) instead of silent failures.

Management:

- Safe mode is toggled from a **system‑level Settings screen** (not per‑workspace) and requires permissions like `System.SafeMode.Read` / `System.SafeMode.ReadWrite`.
- The UI:
  - Shows current state (enabled/disabled) and detail.
  - Lets authorised users update the message.
  - Provides a single toggle to enable/disable Safe mode.

---

### Roles & permissions

ADE Web is designed around **RBAC** (role‑based access control):

- Users hold **roles** per workspace (e.g. Owner, Maintainer, Reviewer, Viewer).
- Roles aggregate **permissions** (e.g. `Workspace.Members.ReadWrite`, `Workspace.Roles.ReadWrite`).

Permissions govern actions such as:

- Creating/deleting **workspaces**.
- Managing **workspace members**.
- Creating/updating **workspace roles**.
- Toggling **Safe mode**.
- Editing and activating **configuration versions**.
- Starting **runs** (normal, validation, and test modes).
- Viewing **logs** and **telemetry**.

Backend responsibilities:

- Encode permissions in the session / workspace membership.
- Enforce permissions server‑side on all operations.

Frontend responsibilities:

- Read permissions from session and workspace membership.
- Hide or disable UI controls the user cannot use.
- Use permission keys as hints (e.g. show members tab only if the user can see the membership list).
- Keep permission keys out of feature UIs by wrapping them in domain helpers (e.g. `useCanStartRuns(workspaceId)` built on `useCanInWorkspace`).

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
- `/config-builder` – Configuration Builder (configurations list + workbench).
- Configuration Builder naming stays locked to the route: nav label is **Configuration Builder**, route segment is `/config-builder`, and the feature folder is `features/workspace-shell/sections/config-builder`.
- `/settings` – Workspace settings (tabs controlled by `view` query param).
- `/overview` – Optional overview/summary surface.

If a user lands on `/workspaces/:workspaceId` **without** a section segment, the shell redirects to the configured default section (currently Documents, via a constant in `shared/nav/routes.ts` / `WorkspaceShellScreen`).

Unknown section paths inside a workspace are handled deliberately by the shell: `WorkspaceShellScreen` renders a **workspace‑local “Section not found”** state instead of the global 404 so users can recover by choosing another section without losing workspace context.

### Route helpers (`shared/nav/routes.ts`)

Workspace routes are centralised in `shared/nav/routes.ts`:

```ts
export const routes = {
  workspaces: "/workspaces",
  workspaceDocuments: (id: string) => `/workspaces/${id}/documents`,
  workspaceRuns: (id: string) => `/workspaces/${id}/runs`,
  workspaceConfigBuilder: (id: string) => `/workspaces/${id}/config-builder`,
  workspaceSettings: (id: string) => `/workspaces/${id}/settings`,
};
```

Use these helpers everywhere (links, navigation logic, tests) instead of hand‑rolled strings to keep the docs’ route map and the code in sync.

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

Because `new URL(to, window.location.origin)` assumes a root‑served SPA, if ADE Web ever needs to live under a sub‑path we will centralise the base path in `NavProvider` or `shared/nav/routes.ts` instead of baking `/`‑prefixed strings throughout the codebase.

**Hooks:**

* `useLocation()` – read the current location.
* `useNavigate()` – trigger SPA navigation.
* `useNavigationBlocker(blocker, when)` – register/unregister a navigation blocker while `when` is true.

Typical usage:

* Editors (especially Configuration Builder) use blockers to guard against losing unsaved changes.
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

### Typed query helpers for filters

For non‑trivial query state (documents filters, run filters), use typed helper pairs such as `parseDocumentFilters(params: URLSearchParams)` / `buildDocumentSearchParams(filters)` or `parseRunFilters` / `buildRunSearchParams` instead of scattering string keys. Keeping canonical param names (`q`, `status`, `view`, etc.) in one place preserves deep‑link consistency; see `docs/07-documents-and-runs.md` for the canonical filter shapes.

---

## Configuration Builder – workbench model

The **Configurations** section (Configuration Builder) lists configurations and launches the **Configuration Builder workbench**—the dedicated editing window for a single configuration version, backed by a file tree from the backend and a tabbed Monaco editor. In docs, use “Configuration Builder workbench” on first mention and “workbench” afterwards; reserve “editor” for the Monaco instance inside the window.

### Workbench window states

The workbench is hosted by a `WorkbenchWindow` context and route:

* **Restored** – workbench appears inline inside the Configurations section.
* **Maximized** – workbench takes over the viewport:

  * A dim overlay covers the workspace shell.
  * Page scroll is locked while maximized.
  * The underlying section shows an “Immersive focus active” notice.
* **Minimized/docked** – workbench UI is hidden from the main Configurations content:

  * The section shows “Workbench docked”.
  * A dock elsewhere in the Workspace shell can restore it.

Window controls in the workbench chrome:

* **Minimize** – dock the workbench.
* **Maximize / Restore** – toggle immersive focus.
* **Close** – close the workbench session for the current Configuration.

Unsaved‑changes guards still apply when closing or navigating away.

### File tree representation (`WorkbenchFileNode`)

Internally, the workbench models the backing configuration package as a tree:

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

For local development and empty configurations, the app can use:

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

  * Displays the configuration file tree.
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
* Console open/closed state and height are persisted per workspace+configuration.

On very small vertical screens, the console may auto‑collapse; the UI shows a banner explaining that the console was closed to preserve editor space.

### ADE script helpers & script API

To make ADE configuration editing more discoverable, the Monaco editor is augmented with ADE‑specific helpers via `registerAdeScriptHelpers`:

* **Scope‑aware**: helpers only activate in ADE configuration files:

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
* Keyed by workspace ID and configuration ID:

  * Example: `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.tabs`.
* Hydrated on load and filtered against the current tree.

### Editor theme preference

The editor honours user theme preference:

```ts
export type EditorThemePreference = "system" | "light" | "dark";
export type EditorThemeId = "ade-dark" | "vs-light";
```

* `useEditorThemePreference`:

  * Storage key: `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.editor-theme`.
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

* Key: `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.console`.
* On load:

  * Uses stored `fraction` if available.
  * Otherwise uses a default pixel height converted into a fraction of container height.
* The workbench may override initial open/closed state from persisted value if the URL query explicitly sets console state.

### Environment readiness & run pipeline

The workbench no longer exposes a dedicated “Build environment” control. Environment readiness is handled automatically when starting a run:

* **Validation run:** “Validation run” starts a run with `RunOptions.validateOnly: true` (backend receives `validate_only`). Console streams results; issues populate the **Validation** tab on completion.
* **Test run:** The **Test** split button opens the run dialog. The primary action reuses the existing environment; the dropdown option **Force build and test** sets `force_rebuild: true` so the backend rebuilds the venv inline before running.
* Environment reuse vs. rebuild is therefore controlled per run, not via a separate build button or keyboard shortcut.

### Running tests from the workbench

The **Test** split button opens a modal run dialog:

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
    * Optional `input_sheet_names`,
    * `force_rebuild` when “Force build and test” was chosen.
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

Configuration Builder’s layout and file selection are encoded in query parameters.

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

Outside the Configuration Builder, some important query parameters:

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
* Safe mode toggling lives in a **system‑level Settings screen** (not per‑workspace) and is permission‑gated via `System.SafeMode.*`; the workspace Settings section may surface read‑only state and link admins to the system screen.

Behaviour:

* Uses `useSearchParams` to:

  * Read the `view` parameter.
  * Normalise invalid values back to `general`.
  * Keep tab selection in sync with the URL via `setSearchParams({ view }, { replace: true })`.
* Tabs lazily mount their content to avoid unnecessary data fetching.

### Workbench return path

For smooth flow between operational views and configuration editing, the workbench can remember where to return after editing:

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
  * Trigger runs against a selected configuration version.
  * Show per‑document last run status and quick actions.

* **Runs**

  * Workspace‑wide ledger of runs.
  * Filter by status, configuration, date range, and initiator.
  * Link through to:

    * Logs (via NDJSON replay),
    * Telemetry summaries,
    * Output artifacts.

* **Configuration Builder**

  * Configurations list:

    * Shows configurations, IDs, status, active version.
    * “Open in workbench” opens the Configuration Builder workbench for a given configuration.
  * Workbench:

    * Dedicated Configuration Builder workbench window as described above.

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

  * Cross‑cutting issues: Safe mode, connectivity, console auto‑collapse, environment reuse, concurrency errors, etc.

Workbench‑specific banner scopes are used so messages (e.g. around console collapse or build reuse) can be dismissed or persisted independently.

Keyboard shortcuts (non‑exhaustive):

* **Global**

  * `⌘K` / `Ctrl+K` – open workspace/global search.
  * `⌘U` / `Ctrl+U` – document upload (where implemented).
* **Workbench**

  * `⌘S` / `Ctrl+S` – save active editor file.
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
  * HTTP semantics: `401` always means “not logged in” and triggers a redirect to `/login`; `403` means “logged in but not allowed” and should surface permission UI (hidden or disabled actions with an explanation).

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

  * Create run (document + configuration version + options).
  * NDJSON streaming endpoint for run events:

    * Status changes, logs, telemetry envelopes.
  * List runs (filterable by status, document, configuration, date).
  * Run outputs:

    * Listing of output files (path, byte size).
    * Artifact download (combined outputs, typically zip).
    * Telemetry download.

* **Configurations & Configuration Builder**

  * List configurations per workspace (with ID, display name, status, active version).
  * Read single configuration by ID.
  * File listing for a configuration version (flat listing consumable by `createWorkbenchTreeFromListing`).
  * File content endpoints:

    * Read (`GET`) with metadata (`size`, `mtime`, `content_type`, `etag`, `encoding`).
    * Write (`PUT`/`PATCH`) with:

      * `etag` preconditions (for concurrency),
      * `create` and `parents` flags where applicable.
    * Optional rename/delete endpoints.
  * Validation endpoint:

    * Accepts current configuration snapshot.
    * Returns structured validation issues for display in the Validation tab.
  * Run endpoints:

    * NDJSON streaming (`streamRun`) with support for `validate_only`, `input_document_id`, `input_sheet_names`, and `force_rebuild` (to rebuild the environment inline).
    * Emits run lifecycle events and summaries; ADE Web shows run and telemetry downloads.

* **Safe mode**

  * Global and optional workspace‑scoped status endpoint.
  * Mutations to toggle Safe mode and update message (permission‑gated).

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

### Data layer conventions

* Three tiers: shared HTTP client → domain API modules (`authApi`, `permissionsApi`, `rolesApi`, `workspacesApi`, `documentsApi`, `runsApi`, `configurationsApi`, `buildsApi`, `systemApi`, `apiKeysApi`) → React Query hooks co‑located with screens.
* Query keys stay canonical: params/filters are serialised via stable helpers (sorted keys + `JSON.stringify`) and ideally exposed through a small `queryKeys` factory instead of inline objects.
* Runs are run‑centric: `runId` is treated as globally unique; prefer the global `GET /api/v1/runs/{run_id}` + `useRunQuery(runId)` for detail/logs/outputs. Workspace IDs only appear when listing or creating runs; workspace detail endpoints remain optional for tenancy enforcement.
* runsApi signatures mirror that stance—workspace functions for `list/create`, run‑centric functions for `readRun`/`streamRunLogs`/downloads.
* Permissions get their own module for discoverability: `permissionsApi` (catalog, effective, checks) vs `rolesApi` (global role CRUD/assignments; workspace roles live under `workspacesApi`).

### Build tooling (Vite)

`apps/ade-web/vite.config.ts`:

* Plugins:

  * `@tailwindcss/vite` – Tailwind integration.
  * `@vitejs/plugin-react` – React Fast Refresh and JSX.
  * `vite-tsconfig-paths` – aligns TS path aliases with Vite resolve.

Aliases:

* `@app` → `src/app`
* `@features` → `src/screens`
* `@ui` → `src/ui`
* `@shared` → `src/shared`
* `@schema` → `src/schema`
* `@generated-types` → `src/generated-types`
* `@test` → `src/test`

Use `@features` going forward; the legacy `@screens` alias has been removed.

Screen slices physically live in `src/screens` (imported via `@features/*`); there is no parallel `src/features` folder. Layer boundaries (app → screens → ui/shared → schema/generated-types, with `test/` able to see everything) are linted so “upward” imports fail fast, and cross‑feature orchestration should stay with its owning screen unless it becomes truly reusable and belongs in `shared/`.

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

* Mirrors Vite aliases (`@app`, `@features`, `@shared`, `@ui`, etc.).
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

Testing philosophy:

* React Testing Library with behaviour‑first assertions; prefer semantic queries (`getByRole`, `getByLabelText`, visible text).
* Use `data-testid` only when no semantic selector exists, and add them in `src/ui` so selectors stay stable for features.
* Automated a11y tooling (e.g. axe) should run cleanly; violations are treated as test failures where practical.

---

## UI component library

ADE Web ships with a small, composable UI component library under `src/ui`, built on Tailwind CSS. It is intentionally light‑weight and application‑specific.

The layer stays presentational (no HTTP, routing, permissions, or storage), derives colours from Tailwind theme tokens instead of hard‑coding values so app‑wide theming (light/dark) remains viable, and bakes in ARIA/keyboard patterns so features do not have to re‑implement them.

Key building blocks:

* **Buttons**

  * `Button`:

    * Variants: `"primary" | "secondary" | "ghost" | "danger"`.
    * Sizes: `"sm" | "md" | "lg"`.
    * `isLoading` prop shows an inline spinner and disables the button.
  * `SplitButton`:

    * Primary action + secondary menu toggle, used for the Configuration Builder **Test** control (primary “Test”, menu “Force build and test”).
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
    * Used primarily in the Configuration Builder workbench.

These components ensure consistent layout, accessibility, and styling across ADE Web while keeping the app’s structure relatively simple.

---

## Summary

ADE Web is the operational and configuration console for Automatic Data Extractor:

* **Analysts** use it to upload documents, run extractions, inspect runs, and download outputs.
* **Workspace owners / engineers** use it to evolve workspace **Configurations** (backed by Python configuration packages), validate and test changes, and safely roll out new versions using the Configuration Builder workbench.
* **Admins** use it to manage workspaces, members, roles, SSO hints, and Safe mode.

This README captures:

* The **conceptual model** (workspaces, documents, runs, configurations, Safe mode, roles),
* The **navigation and URL‑state conventions** (custom history, SPA links, search params, deep linking),
* The **Configuration Builder workbench model** (file tree, tabs, ADE script helpers, console, validation, inspector, theme, window states),
* The **backend contracts** ADE Web expects,
* And the **front‑end architecture & UI components** that support the user experience.

As long as backend implementations respect these concepts and contracts, ADE Web can remain stable and backend‑agnostic, even as internal infrastructure evolves.
