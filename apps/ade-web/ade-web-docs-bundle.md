# Logical module layout (source -> sections below):
# - apps/ade-web/README.md - ADE Web
# - apps/ade-web/docs/01-domain-model-and-naming.md - ADE Web — Domain model & naming
# - apps/ade-web/docs/02-architecture-and-project-structure.md - 02 – Architecture and project structure
# - apps/ade-web/docs/03-routing-navigation-and-url-state.md - 03 – Routing, navigation, and URL state
# - apps/ade-web/docs/04-data-layer-and-backend-contracts.md - 04 – Data layer and backend contracts
# - apps/ade-web/docs/05-auth-session-rbac-and-safe-mode.md - 05 – Auth, Session, RBAC, and Safe Mode
# - apps/ade-web/docs/06-workspace-layout-and-sections.md - 06 – Workspace layout and sections
# - apps/ade-web/docs/07-documents-and-runs.md - 07 – Documents and Runs
# - apps/ade-web/docs/08-configurations-and-config-builder.md - 08 – Configurations and Config Builder
# - apps/ade-web/docs/09-workbench-editor-and-scripting.md - 09 – Workbench editor and scripting
# - apps/ade-web/docs/10-ui-components-a11y-and-testing.md - 10. UI components, accessibility, and testing

# apps/ade-web/README.md
```markdown
# ADE Web

ADE Web is the browser‑based front‑end for the **Automatic Data Extractor (ADE)** platform.

It serves two main personas:

- **Workspace owners / engineers** – design and evolve **Configurations** (backed by Python configuration packages / `ade_config` projects) that describe how documents are processed; manage Safe mode; and administer workspaces, SSO, roles, and members.
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
2. **Workspace shell** – where users operate inside a specific workspace.

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
    - Configurations (Config Builder)
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

Certain routes (especially the **Config Builder** workbench) can temporarily hide parts of the shell in favour of the immersive workbench layout.

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
- Run dialogs (including the Config Builder **Run extraction** dialog) can offer sheet‑level selection.

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
  inputSheetNames?: string[]; // API: input_sheet_names
  mode?: RunMode;             // optional view-model helper derived from flags
}
```

- `dryRun` – exercise the pipeline without emitting final outputs.
- `validateOnly` – run validators and checks only (a **validation run**, not a build).
- `inputSheetNames` – when provided, only these spreadsheet worksheets are processed.
- `mode` – optional label for UI/tests; typically `"validation"` for validation runs and `"test"` for sample runs.

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
- The Config Builder workbench reuses this to show build/run events inside its **Console**.

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
2. Edit code, configuration files, and manifest in the Config Builder.
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
- Surfaces it in the Config Builder for:
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
- `/config-builder` – Config Builder (config list + workbench).
- Config Builder naming stays locked to the route: nav label is **Config Builder**, route segment is `/config-builder`, and the feature folder is `features/workspace-shell/sections/config-builder`.
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

### Typed query helpers for filters

For non‑trivial query state (documents filters, run filters), use typed helper pairs such as `parseDocumentFilters(params: URLSearchParams)` / `buildDocumentSearchParams(filters)` or `parseRunFilters` / `buildRunSearchParams` instead of scattering string keys. Keeping canonical param names (`q`, `status`, `view`, etc.) in one place preserves deep‑link consistency; see `docs/07-documents-and-runs.md` for the canonical filter shapes.

---

## Config Builder – workbench model

The **Configurations** section (Config Builder) lists configurations and launches the **Config Builder workbench**—the dedicated editing window for a single configuration version, backed by a file tree from the backend and a tabbed Monaco editor. In docs, use “Config Builder workbench” on first mention and “workbench” afterwards; reserve “editor” for the Monaco instance inside the window.

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

### Build & run pipeline

The **workbench chrome** includes a **Build environment** split button (implemented via `SplitButton`):

* Default click:

  * Starts `streamBuild(workspaceId, configurationId, { force, wait }, signal)`.
  * Prints build events into the **Console**.
  * Detects and highlights environment reuse (e.g. “Environment reused; nothing to rebuild.”).
* Menu options:

  * “Build / reuse environment” – normal behaviour.
  * “Force rebuild now” – run a full rebuild immediately.
  * “Force rebuild after current build” – queue a forced rebuild.
* Keyboard shortcuts:

  * `⌘B` / `Ctrl+B` – default build.
  * `⇧⌘B` / `Ctrl+Shift+B` – force rebuild.

**Validation run:**

* “Validation run” action starts a run with `RunOptions.validateOnly: true`
  (UI may also set `mode: "validation"`; backend receives `validate_only`).
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
    * `RunOptions` in camelCase (converted to `dry_run` / `validate_only` /
      `input_sheet_names`), typically with `mode: "test"` for clarity.
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

* **Config Builder**

  * Config list:

    * Shows configurations, IDs, status, active version.
    * “Open in workbench” opens the Config Builder workbench for a given configuration.
  * Workbench:

    * Dedicated Config Builder workbench window as described above.

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

* **Configurations & Config Builder**

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
  * Build endpoint:

    * NDJSON streaming (`streamBuild`) with `force` and `wait` options.
    * Emits a final `build.completed` event with `status`, `summary`, `error_message`.
    * Implements environment reuse detection so ADE Web can hint whether a rebuild actually happened.

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
* **Workspace owners / engineers** use it to evolve workspace **Configurations** (backed by Python configuration packages), validate and test changes, and safely roll out new versions using the Config Builder workbench.
* **Admins** use it to manage workspaces, members, roles, SSO hints, and Safe mode.

This README captures:

* The **conceptual model** (workspaces, documents, runs, configurations, Safe mode, roles),
* The **navigation and URL‑state conventions** (custom history, SPA links, search params, deep linking),
* The **Config Builder workbench model** (file tree, tabs, ADE script helpers, console, validation, inspector, theme, window states),
* The **backend contracts** ADE Web expects,
* And the **front‑end architecture & UI components** that support the user experience.

As long as backend implementations respect these concepts and contracts, ADE Web can remain stable and backend‑agnostic, even as internal infrastructure evolves.
```

# apps/ade-web/docs/01-domain-model-and-naming.md
```markdown
# ADE Web — Domain model & naming

This document defines the domain concepts that the ADE web app works with and how we name them in the UI, API shapes, and frontend code. It’s meant to keep the frontend in lockstep with the ADE engine and API (workspaces, configurations backed by configuration packages, builds, runs, documents, artifacts).

---

## Naming contract (quick checklist)

Keep these names and IDs aligned across UI copy, types, routes, and folders:

- Workspace – Workspace, `workspaceId`
- Configuration – Configuration, `configurationId`
- Configuration package – backing Python project for a Configuration (never a separate UI entity)
- Configuration version – `ConfigurationVersion`, `configurationVersionId`
- Build – Build, `buildId` (environment)
- Run – Run, `runId`
- Document – Document, `documentId`
- Artifact – `RunArtifact` / Artifact, tied to `runId`
- Routes: `/workspaces`, `/workspaces/:workspaceId/{documents|runs|config-builder|settings}`
- Feature folders: `features/workspace-shell/sections/{documents|runs|config-builder|settings}`
- API modules: `workspacesApi`, `configurationsApi`, `documentsApi`, `runsApi`, `buildsApi`
- Storage prefix: `ade.ui.workspace.<workspaceId>…`

**Config Builder naming rule:** the nav label is **Config Builder**, the route segment is `/config-builder`, and the screen/folder lives at `features/workspace-shell/sections/config-builder`. Keep all three in sync.

If this table and the folder structure always agree, onboarding stays trivial for new contributors and agents.

---

## 1. Goals

**Audience**

* Frontend engineers working in `apps/ade-web/`
* API/engine maintainers who care about UX terminology
* Anyone writing docs, tests, or debug logs that reference ADE entities

**Goals**

1. Share a single mental model of “things” in ADE Web.
2. Align user‑facing names, API types, and filesystem terms.
3. Avoid subtle run naming inconsistencies.
4. Make it obvious how to name new screens, hooks, and types.

---

## 2. Big picture: the ADE Web domain

At a high level:

1. A **Workspace** owns everything for a given team/tenant.
2. Within a workspace, users author **Configurations** — workspace concepts backed by installable `ade_config` (Python configuration) packages.
3. Each Configuration can be **built** into a virtualenv that includes `ade_engine` + that `ade_config`.
4. Users upload **Documents** (Excel/CSV) to the workspace.
5. Users launch **Runs** that execute a **Build** against one or more **Documents**, producing **Artifacts** (`output.xlsx` and `artifact.json`).

Conceptually:

```text
Workspace
 ├─ Configurations (backed by configuration packages)
 │    ├─ Builds
 │    │    └─ Runs
 │    │         ├─ Input documents
 │    │         └─ Artifacts (output.xlsx, artifact.json)
 └─ Shared documents
```

---

## 3. Core entities

### 3.1 Summary table

| Concept        | UI label        | Recommended TS type name   | Typical ID field(s)                     | Backend / storage hints                       |
| -------------- | --------------- | -------------------------- | --------------------------------------- | --------------------------------------------- |
| Workspace      | Workspace       | `Workspace`                | `workspaceId`                           | `workspaces/<workspace_id>/…`                 |
| Configuration  | Configuration   | `Configuration`            | `configurationId`, `workspaceId`        | `configurations/<configuration_id>/…`         |
| Build          | Build           | `Build`                    | `buildId`, `configurationId`            | `.venv/<configuration_id>/ade-runtime/build.json`  |
| Run            | Run             | `Run`                      | `runId`                                 | `runs/<run_id>/…`                             |
| Document       | Document        | `Document`                 | `documentId`, `workspaceId`             | `documents/<document_id>.<ext>`               |
| Artifact       | Artifact        | `Artifact` / `RunArtifact` | `runId`                                 | `runs/<run_id>/logs/artifact.json`            |
| Template       | Config template | `ConfigTemplate`           | `templateId`                            | `templates/config_packages/…`                 |

> The exact TS types come from `@schema` (OpenAPI‑generated); in the web app we usually alias those to ergonomic names rather than importing from `@generated-types` directly. 

---

### 3.2 Workspace

**What it represents**

* Top‑level container and isolation boundary.
* Owns configurations (backed by configuration packages), runs, documents, artifacts, and runtime state under `./data/workspaces/<workspace_id>/…`. 

**User‑facing naming**

* Singular: **Workspace**
* Plural: **Workspaces**
* Examples in copy:

  * “Create workspace”
  * “Switch workspace”
  * “No workspaces yet”

**Code & API naming**

* Route param: `workspaceId`
* TS field: `workspaceId: string`
* Backend / storage convention: `workspace_id` and `<workspace_id>` segments

**Frontend conventions**

* Type alias from schema:

  ```ts
  import type { WorkspaceEnvelope } from "@schema"; // example

  type Workspace = WorkspaceEnvelope; // frontend alias
  ```

* Hooks:

  * `useWorkspaces()` — list
  * `useWorkspace(workspaceId)` — detail

* Components:

  * `<WorkspacesScreen />`
  * `<WorkspaceSelector />`

---

### 3.3 Configuration

**What it represents**

* A workspace‑scoped **Configuration** that describes how ADE processes documents.
* Each Configuration is **backed by an installable `ade_config` Python package** containing detectors, transforms, validators, hooks, and a manifest.
* Source of truth for the backing package lives under a workspace: `configurations/<configuration_id>/…` (and may be represented on disk as `config_packages/<configuration_id>/…`).

**User‑facing naming**

* Singular: **Configuration**
* Plural: **Configurations**
* When referring to the Python packaging form, call it the **backing configuration package**; keep “Configuration” in UI copy and React components.

**Code & API naming**

* IDs:

  * `configurationId: string`
  * `workspaceId: string`
* Common fields:

  * `name`, `description`
  * `status` / `displayVersion` (if applicable)
  * `createdAt`, `updatedAt`
* Backend convention: `configuration_id`, canonical path `configurations/…` (with the backing package stored under `config_packages/…`).

**Frontend conventions**

* Type alias: `type Configuration = Schema.Configuration…;`
* Hooks:

  * `useConfigurations(workspaceId)`
  * `useConfiguration({ workspaceId, configurationId })`
* Components:

  * `<ConfigurationList />`
  * `<ConfigurationDetail />`
  * `<CreateConfigurationDialog />`

---

### 3.4 Build

**What it represents**

* A build is a **frozen Python environment** (virtualenv) for a specific Configuration:

  * Contains `ade_engine`, the backing `ade_config` package, and its dependencies.
* Build metadata lives alongside the venv under `.venv/<configuration_id>/ade-runtime/build.json`.

**User‑facing naming**

* Singular: **Build**
* Plural: **Builds**
* Copy examples:

  * “Latest build”
  * “Build failed”
  * “Trigger build”

**Code & API naming**

* IDs:

  * `buildId` (if surfaced as a first‑class entity)
  * `configurationId`, `workspaceId`
* Typical fields:

  * `status` (`"pending" | "running" | "succeeded" | "failed"` – actual values defined by the API)
  * `createdAt`, `startedAt`, `finishedAt`
  * `engineVersion`, `configVersion`

**Frontend conventions**

* Type: `Build`
* Hooks:

  * `useBuilds(configurationId)`
  * `useBuild(configurationId, buildId)`
  * `useTriggerBuild()` mutation
* Components:

  * `<BuildTimeline />`
  * `<BuildStatusBadge />`

---

### 3.5 Run

**What it represents**

* A **Run** is a user‑visible execution of a build against one or more documents.
* The backend wire field is `run_id`; we map that once to `runId` in the frontend and keep **Run** as the domain concept.

**Terminology rule**

* In **UI copy** and UX discussions: say **Run**.

  * “Run history”, “Run details”, “Start run”
* In **code & API**:

  * Use the `Run` type and the field name `runId` (mapped from `run_id`).
  * If the engine exposes an additional identifier, carry it as `engineRunId` instead of duplicating `runId`.

**Code & API naming**

* IDs:

* `runId` (frontend field name mapped from `run_id`)
* `workspaceId`, `configurationId`, `buildId`
* Typical fields:

  * `status` (`"queued"`, `"running"`, `"succeeded"`, `"failed"`, etc. — defined by API)
  * `inputDocuments: Document[]`
  * `artifact` metadata (path to `output.xlsx`, `artifact.json`)

**Frontend conventions**

* Type:

  ```ts
  interface Run {
    runId: string;   // domain ID mapped from run_id
    status: RunStatus;
    // …
  }
  ```

* Hooks:

* `useRuns(configurationId)` / `useRunsForBuild(buildId)`
  * `useRun(runId)`
  * `useStartRun()` mutation

* Components:

  * `<RunList />`
  * `<RunDetailScreen />`
  * `<RunStatusPill />`

---

### 3.6 Document

**What it represents**

* An uploaded **input file** (Excel/CSV) owned by a workspace.
* Stored under `workspaces/<workspace_id>/documents/<document_id>.<ext>`. 

**User‑facing naming**

* Singular: **Document**
* Plural: **Documents**
* Copy examples:

  * “Upload document”
  * “Recent documents”
  * “Document used in this run”

**Code & API naming**

* IDs:

  * `documentId`, `workspaceId`
* Typical fields:

  * `filename`, `contentType`, `sizeBytes`
  * `uploadedAt`, `uploadedBy`
  * Optional `lastRunId` / `lastRunStatus` (view model convenience)

**Frontend conventions**

* Types:

  * `Document`
  * `DocumentSummary` (if you introduce lightweight list DTOs)
* Hooks:

  * `useDocuments(workspaceId)`
  * `useDocument(documentId)`
* Components:

  * `<DocumentUpload />`
  * `<DocumentTable />`

---

### 3.7 Artifact

**What it represents**

* The structured result of a run:

  * Normalized workbook (`output.xlsx`)
  * Narrative + metrics in `artifact.json` under `runs/<run_id>/logs/`. 

**User‑facing naming**

* Singular: **Artifact**
* Plural: **Artifacts**
* Copy examples:

  * “Download artifact”
  * “Artifact summary”

**Code & API naming**

* IDs:

  * `runId`
* Fields typically follow the artifact schema (see `docs/14-run_artifact_json.md` in the backend docs). 

**Frontend conventions**

* Types:

  * `Artifact` or `RunArtifact`
  * Specific views: `ArtifactSheetSummary`, `ArtifactIssue`
* Components:

  * `<ArtifactSummary />`
  * `<ArtifactIssuesPanel />`
  * `<DownloadArtifactButton />`

---

### 3.8 Config template

**What it represents**

* A **template** for bootstrapping new configuration packages.
* Backend templates live under `apps/ade-api/src/ade_api/templates/config_packages/`. 

**Naming**

* UI label: **Config template**
* Type: `ConfigTemplate`
* IDs: `templateId`

---

## 4. Naming conventions in the frontend

### 4.1 General principles

1. **Prefer domain words over implementation words**

   * Use **Run** in UI copy.
   * Use **Configuration** instead of ad‑hoc terms like “ruleset” or “profile”, and only mention the backing **configuration package** when describing Python packaging.
2. **Mirror backend identifiers but adapt to JS/TS style**

   * Backend JSON / URLs: `workspace_id`, `configuration_id`, `run_id`. 
   * TypeScript / React:

     * `workspaceId`, `configurationId`, `runId`.
3. **Single canonical name per concept**

   * Don’t mix “workspace” vs “project”, “run” vs “execution” in the same surface.

---

### 4.2 TypeScript & schema types

**Sources of truth**

* OpenAPI‑generated TS lives in `apps/ade-web/src/generated-types/openapi.d.ts`. 
* A curated module in `src/schema/` re‑exports stable shapes (e.g. `SessionEnvelope`). 

**Conventions**

* Import API types from `@schema` (never from `@generated-types/*` in app code).

* Alias noisy API names to clean domain aliases at the edge:

  ```ts
  import type { WorkspaceEnvelope, RunEnvelope } from "@schema";

  type Workspace = WorkspaceEnvelope;
  type Run = RunEnvelope;
  ```

* Use **PascalCase** for type names (`Workspace`, `Configuration`, `Build`, `Run`).

* Avoid `IWorkspace` / `TWorkspace` prefixes.

---

### 4.3 IDs and relationships

**Field naming**

* Always use `<entity>Id`:

  * `workspaceId`
  * `configurationId`
  * `buildId`
  * `runId`
  * `documentId`
  * If you need the raw engine ID: keep mapping it into `runId`, or add a distinct `engineRunId`.
* Do the snake_case → camelCase translation exactly once in `schema/` mapping helpers (e.g. `fromApiRun`, `fromApiConfiguration`) so screens never see `run_id`/`configuration_id`.

**Relationship shape examples**

```ts
interface WorkspaceRef {
  workspaceId: string;
}

interface ConfigurationRef extends WorkspaceRef {
  configurationId: string;
}

interface BuildRef extends ConfigurationRef {
  buildId: string;
}

interface RunRef {
  runId: string;
}
```

---

### 4.4 React screens, components, and hooks

**Screens**

* Place screens under `src/screens/<FeatureName>/`.
* Name the top‑level component `<FeatureName>Screen`:

  * `<WorkspacesScreen />`
  * `<ConfigPackageScreen />`
  * `<RunDetailScreen />`

**Feature components**

* Use domain nouns:

  * `<WorkspaceList />`, `<ConfigPackageList />`, `<RunTable />`
* For dialogs/modals:

  * `<CreateWorkspaceDialog />`
  * `<StartRunDialog />`

**Hooks**

* Data‑fetch hooks:

  * `useWorkspaces()`
  * `useConfigurations(workspaceId)`
  * `useRuns(workspaceId)`
* Mutation hooks:

  * `useCreateWorkspace()`
  * `useCreateConfiguration()`
  * `useTriggerBuild()`
  * `useStartRun()`

**Navigation**

* Use the nav helpers from `@app/nav` (`useNavigate`, `useLocation`, `Link`, `NavLink`). 
* Route param names must match the `<entity>Id` convention:

  * `/workspaces/:workspaceId`
  * `/workspaces/:workspaceId/config-builder` (and any nested params like `:configurationId` or `/builds/:buildId` if used)
  * `/runs/:runId` (or nested, depending on actual router structure)

---

### 4.5 Status strings and enums

**Backend**

* Status values are plain strings (e.g. `"pending"`, `"running"`, `"succeeded"`, `"failed"`).
* Exact values are defined by the OpenAPI schema.

**Frontend**

* Represent them as string unions:

  ```ts
  type BuildStatus = "pending" | "running" | "succeeded" | "failed";
  type RunStatus = "queued" | "running" | "succeeded" | "failed";
  ```

* UI components should map status → consistent visual treatments:

  * `status="succeeded"` → success color
  * `status="failed"` → danger color

---

## 5. Putting it together (example flow)

End‑to‑end naming for a typical user flow:

1. User selects a **Workspace** (`workspaceId`).
2. They open a **Configuration** (`configurationId`) and click **Build**.
3. The system creates/updates a **Build** for that Configuration (`buildId`) and shows its **Build status**.
4. They **Upload document(s)** to the workspace (`documentId`).
5. From the configuration/build screen they click **Start run**:

   * Web sends a `runId`‑centric request to the API.
   * UI shows a **Run** in the run list with `runId` mapped from the backend `run_id`.
6. When the run completes, UI links to the **Artifact**:

   * “Download output workbook”
   * “View artifact details”

At each step, the same concepts and names are used in copy, code, and API contracts.
```

# apps/ade-web/docs/02-architecture-and-project-structure.md
```markdown
# 02 – Architecture and project structure

This document describes how `ade-web` is organised on disk, how the main layers depend on each other, and the naming conventions we use for files and modules.

If **01‑domain‑model‑and‑naming** tells you *what* the app talks about (workspaces, documents, runs, configurations), this doc tells you *where* that logic lives and *how* it is wired together.

---

## 1. Goals and principles

The architecture is intentionally boring and predictable:

- **Feature‑first** – code is grouped by user‑facing feature (auth, documents, runs, config builder), not by technical layer.
- **Layered** – app shell → screens → shared utilities & UI primitives → types.
- **One‑way dependencies** – each layer imports “downwards” only, which keeps cycles and hidden couplings out.
- **Obvious naming** – given a route or concept name, you should know what file to search for.

Everything below exists to make those goals explicit.

### Instant understanding defaults

- **Domain‑first naming:** keep the language 1:1 with the product (types such as `Workspace`, `Run`, `Configuration`, `ConfigVersion`, `Document`; hooks like `useRunsQuery`, `useStartRunMutation`; sections `/documents`, `/runs`, `/config-builder`, `/settings` mirrored under `screens/workspace-shell/sections/...`).
- **One canonical home per concept:** routes live in `@shared/nav/routes`; query parameter names stay consistent with `docs/03`, `docs/06`, `docs/07` and their filter helpers (`parseDocumentFilters`, `parseRunFilters`, `build*SearchParams`); permission keys live in `@schema/permissions` with helpers in `@shared/permissions`.
- **Reuse patterns:** new list/detail flows should copy Documents/Runs; new URL‑backed filters should reuse the existing filter helpers rather than inventing new query names; NDJSON streaming should go through the shared helper and event model.
- **Respect the layers:** never import “upwards” (e.g. `shared/` → `screens/`); linting enforces the boundaries.

See `../CONTRIBUTING.md` for the quick version; the rest of this doc unpacks where things live.

---

## 2. Top‑level layout

All relevant code lives under `apps/ade-web/src`:

```text
apps/ade-web/
  src/
    app/              # App shell: providers, global layout, top-level routing
    screens/          # Screen/feature slices (aliased as "@features")
    ui/               # Reusable presentational components
    shared/           # Cross-cutting hooks, utilities, and API modules (no UI)
    schema/           # Hand-written domain models / schemas
    generated-types/  # Types generated from backend schemas
    test/             # Vitest setup and shared testing helpers
````

> Screen folders live in `src/screens` and are imported via `@features/*` (historical alias). There is no `src/features` directory.

At a high level:

* `app/` is the **composition root**.
* `screens/` contains **route‑level screens/features**.
* `ui/` contains **UI primitives** with no domain knowledge.
* `shared/` contains **infrastructure** and **cross‑cutting logic**.
* `schema/` and `generated-types/` define **types**.
* `test/` holds **test infrastructure**.

---

## 3. Layers and dependency rules

We treat the codebase as layered, with imports flowing “down” only:

```text
        app
        ↑
     screens (@features)
     ↑          ↑
    ui        shared
      ↑         ↑
   schema   generated-types
        ↑
       test (can see everything)
```

Allowed dependencies:

* `app/` → may import from `screens/`, `ui/`, `shared/`, `schema/`, `generated-types/`.
* `screens/` → may import from `ui/`, `shared/`, `schema/`, `generated-types/`.
* `ui/` → may import from `shared/`, `schema/`, `generated-types/`.
* `shared/` → may import from `schema/`, `generated-types/`.
* `schema/` → may import from `generated-types/` (if needed).
* `generated-types/` → must not import from anywhere else.
* `test/` → may import from anything in `src/`, but nothing in `src/` should import from `@test`.

Forbidden dependencies:

* `ui/` **must not** import from `screens/` or `app/`.
* `shared/` **must not** import from `screens/`, `ui/`, or `app/`.
* `screens/` **must not** import from `app/`.

If you ever want to import “upwards” (e.g. from `shared/` to `screens/`), that’s a sign the code should be moved into a smaller module at the right layer.

We lint these boundaries (module‑boundary rules in ESLint) so you get a fast failure if, for example, `shared/` tries to import a screen. Update the rule if you add new top‑level folders.

---

## 4. `app/` – application shell

**Responsibility:** Compose the entire app: providers, navigation, top‑level layout, and screen selection.

Typical structure:

```text
src/app/
  App.tsx
  ScreenSwitch.tsx
  NavProvider/
    NavProvider.tsx
    Link.tsx
    NavLink.tsx
  AppProviders/
    AppProviders.tsx
  layout/
    GlobalLayout.tsx
    WorkspaceShellLayout.tsx
```

What belongs here:

* `<App>` – root component used in `main.tsx`.
* `NavProvider` – custom navigation context built on `window.history`.
* `AppProviders` – React Query client and other global providers.
* `ScreenSwitch` – top‑level route switch that decides which feature screen to show.
* High‑level layout wrappers (e.g. global error boundary, shell frame).

What does **not** belong here:

* Feature‑specific logic (documents, runs, configurations, etc.).
* Direct API calls to `/api/v1/...`.
* Reusable UI primitives (those go in `ui/`).

`app/` is glue and composition only.

---

## 5. `screens/` – screen/feature slices

**Responsibility:** Implement user‑facing features and screens: auth, workspace directory, workspace shell, and each shell section (Documents, Runs, Config Builder, Settings, Overview). The physical folder is `src/screens/`, imported via the `@features/*` alias.

Example structure:

```text
src/screens/
  auth/
    LoginScreen.tsx
    AuthCallbackScreen.tsx
    LogoutScreen.tsx
    useLoginMutation.ts
  workspace-directory/
    WorkspaceDirectoryScreen.tsx
    WorkspaceCard.tsx
    useWorkspaceDirectoryQuery.ts
  workspace-shell/
    WorkspaceShellScreen.tsx
    nav/
      WorkspaceNav.tsx
      useWorkspaceNavItems.ts
    sections/
      documents/
        DocumentsScreen.tsx
        DocumentsTable.tsx
        DocumentsFilters.tsx
        useDocumentsQuery.ts
        useUploadDocumentMutation.ts
      runs/
        RunsScreen.tsx
        RunsTable.tsx
        RunsFilters.tsx
        useRunsQuery.ts
        useStartRunMutation.ts
      config-builder/
        ConfigBuilderScreen.tsx
        ConfigList.tsx
        workbench/
          WorkbenchWindow.tsx
          WorkbenchExplorer.tsx
          WorkbenchTabs.tsx
          useWorkbenchFiles.ts
          useWorkbenchUrlState.ts
      settings/
        WorkspaceSettingsScreen.tsx
        MembersTab.tsx
        RolesTab.tsx
      overview/
        WorkspaceOverviewScreen.tsx
```

Keep section naming 1:1 across the UI: the nav item is **Config Builder**, the route segment is `config-builder`, and the feature folder is `screens/workspace-shell/sections/config-builder`. That folder owns both the configurations list and the workbench editing mode.

What belongs here:

* **Screen components** (`*Screen.tsx`) that:

  * Decide which data to fetch.
  * Map URL state to props.
  * Compose `ui/` components into a page.
  * Choose which mutations to call on user actions.

* **Feature‑specific hooks**:

  * `useDocumentsQuery`, `useRunsQuery`, `useStartRunMutation`, `useWorkspaceMembersQuery`, etc.

* **Feature‑specific components**:

  * `DocumentsTable`, `RunsFilters`, `ConfigurationList`, `RunExtractionDialog`.

What does **not** belong here:

* Generic UI primitives (buttons, inputs, layout) → `ui/`.
* Cross‑feature logic (API clients, storage helpers) → `shared/`.

When you add a new route or screen, it should live under `screens/`, in a folder that mirrors the URL path.

---

## 6. `ui/` – presentational component library

**Responsibility:** Provide reusable UI components with no knowledge of ADE’s domain concepts. They render markup, accept props, and raise events; they don’t know what a “run”, “workspace”, or “configuration” is.

Example structure:

```text
src/ui/
  button/
    Button.tsx
    SplitButton.tsx
  form/
    Input.tsx
    TextArea.tsx
    Select.tsx
    FormField.tsx
  feedback/
    Alert.tsx
    ToastContainer.tsx
  nav/
    Tabs/
      TabsRoot.tsx
      TabsList.tsx
      TabsTrigger.tsx
      TabsContent.tsx
    ContextMenu.tsx
  identity/
    Avatar.tsx
    ProfileDropdown.tsx
  layout/
    Page.tsx
    SidebarLayout.tsx
  global/
    GlobalTopBar.tsx
    GlobalSearchField.tsx
  code/
    CodeEditor.tsx
```

What belongs here:

* Buttons, split buttons, links styled as buttons.
* Inputs, textareas, selects, form field wrappers.
* Alerts, banners, toasts.
* Tabs, context menus, dropdowns.
* Avatars and profile menus.
* Global top bar and search field components.
* Monaco editor wrapper (`CodeEditor`).

What does **not** belong here:

* Business logic (no calls to `*Api` modules).
* Domain types in props (prefer generic names like `items`, `onSelect` rather than `runs`, `onRunClick`).
* Route knowledge (no `navigate` calls).

Screens in `screens/` own domain logic and pass data into these components.

---

## 7. `shared/` – cross‑cutting utilities and hooks

**Responsibility:** Provide non‑UI building blocks used by many features. This includes API clients, URL helpers, storage utilities, streaming helpers, permission checks, keyboard shortcut wiring, etc.

Example structure:

```text
src/shared/
  api/
    authApi.ts
    permissionsApi.ts
    rolesApi.ts
    workspacesApi.ts
    documentsApi.ts
    runsApi.ts
    configurationsApi.ts
    buildsApi.ts
    systemApi.ts
    apiKeysApi.ts
  nav/
    routes.ts             # route builders like workspaceRuns(workspaceId)
  url-state/
    urlState.ts           # toURLSearchParams, getParam, setParams
    useSearchParams.ts
    SearchParamsOverrideProvider.tsx
  navigation-blockers/
    useNavigationBlocker.ts
  storage/
    storage.ts            # namespaced localStorage helpers
  streams/
    ndjson.ts             # NDJSON streaming and event parsing
  keyboard/
    shortcuts.ts          # global/workbench shortcut registration
  permissions/
    permissions.ts        # hasPermission, hasAnyPermission
  time/
    formatters.ts         # time/date formatting helpers
```

What belongs here:

* **API modules** wrapping `/api/v1/...`:

  * `documentsApi.listWorkspaceDocuments`, `runsApi.listWorkspaceRuns`, `runsApi.startRun`, `configurationsApi.listConfigurations`, etc.

* **URL helpers**:

  * `toURLSearchParams`, `getParam`, `setParams`.
  * `useSearchParams` hook and `SearchParamsOverrideProvider`.

* **Route builders**:

  * Functions that produce pathnames from IDs:

    * `workspaceDocuments(workspaceId)`, `workspaceRuns(workspaceId)`, etc.

* **Infrastructure hooks and utilities**:

  * `useNavigationBlocker`.
  * Local storage read/write with ADE‑specific namespacing.
  * NDJSON stream parsing.
  * Permission check helpers.
  * Keyboard shortcut registration helpers.

What does **not** belong here:

* JSX components.
* Feature‑specific business logic (that belongs under `screens/`).
* Any knowledge of `Screen` components.

If a utility function does not render UI and is reused by multiple features, it probably belongs in `shared/`. Rule of thumb for service‑style orchestration: if the logic only makes sense inside a single workspace section (e.g. “Run & follow run” within Documents), keep it with that screen; move it into `shared/` only when it is truly reusable across sections (e.g. NDJSON parsing, per‑document run preferences, permission helpers).

---

## 8. `schema/` and `generated-types/` – types and models

### 8.1 `generated-types/`

**Responsibility:** Contain types generated directly from backend schemas (e.g. OpenAPI codegen).

* These types are the “raw wire” shapes.
* This folder is a leaf: it should not import from anywhere else in `src/`.

You can use these types directly where appropriate, but often it’s better to wrap them in `schema/` so the rest of the app works with stable, frontend‑friendly models.

### 8.2 `schema/`

**Responsibility:** Define the frontend domain types and any mapping from backend models.

Example structure:

```text
src/schema/
  workspace.ts
  document.ts
  run.ts
  configuration.ts
  permissions.ts
```

Typical content:

* `WorkspaceSummary`, `WorkspaceDetail`.
* `DocumentSummary`, `DocumentDetail`, `DocumentStatus`.
* `RunSummary`, `RunDetail`, `RunStatus`.
* `Configuration`, `ConfigVersion`.
* Permission and role models.

You can also provide mapping helpers:

```ts
// run.ts
import type { ApiRun } from "@generated-types";

export interface RunSummary {
  id: string;
  status: RunStatus;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  // ...
}

export function fromApiRun(apiRun: ApiRun): RunSummary {
  // convert and normalise fields here
}
```

Standard helpers to keep snake_case out of screens:

* `fromApiRun(apiRun: ApiRun): Run` – maps `run_id` → `runId` and normalises timestamps/status.
* `fromApiConfiguration(apiConfig: ApiConfiguration): Configuration` – maps `configuration_id` → `configurationId` plus any display helpers.

All snake_case → camelCase translation happens here so screens and hooks work with predictable models.

Features import types from `@schema`, not from `@generated-types`, to keep the rest of the code insulated from backend schema churn.

---

## 9. `test/` – testing setup and helpers

**Responsibility:** Provide shared testing configuration and helpers.

Example structure:

```text
src/test/
  setup.ts             # Vitest config: JSDOM, polyfills, globals
  factories.ts         # test data builders (workspaces, documents, runs, configurations)
  test-utils.tsx       # renderWithProviders, etc.
```

* `setup.ts` is referenced from `vitest.config.ts` and runs before each test.
* Factories can live here or near their domains, but this is the central place for shared ones.
* Only test code should import from `@test/*`.

Tests for a specific component or hook live alongside that code (e.g. `RunsScreen.test.tsx` next to `RunsScreen.tsx`).

---

## 10. Path aliases and import style

We use a small set of TS/Vite aliases to keep imports readable:

* `@app` → `src/app`
* `@features` → `src/screens`
* `@ui` → `src/ui`
* `@shared` → `src/shared`
* `@schema` → `src/schema`
* `@generated-types` → `src/generated-types`
* `@test` → `src/test` (tests only)

Guidelines:

* Use aliases when crossing top‑level directories:

  ```ts
  // Good
  import { WorkspaceShellScreen } from "@features/workspace-shell/WorkspaceShellScreen";
  import { GlobalTopBar } from "@ui/global/GlobalTopBar";
  import { listWorkspaceRuns } from "@shared/api/runsApi";
  import { RunSummary } from "@schema/run";

  // Avoid
  import { listWorkspaceRuns } from "../../../shared/api/runsApi";
  ```

* Within a small screen folder, relative imports are fine and often clearer:

  ```ts
  // inside screens/workspace-shell/sections/runs
  import { RunsTable } from "./RunsTable";
  import { useRunsQuery } from "./useRunsQuery";
  ```

* Use barrel files (`index.ts`) sparingly and only for small, coherent clusters; they can hide dependency direction and complicate tree‑shaking.

---

## 11. Naming conventions

This section summarises naming conventions used in this document. See **01‑domain‑model‑and‑naming** for the domain vocabulary itself.

### 11.1 Screens and containers

* Screen components end with `Screen`:

  * `LoginScreen`, `WorkspaceDirectoryScreen`, `WorkspaceShellScreen`.
  * `DocumentsScreen`, `RunsScreen`, `ConfigBuilderScreen`, `WorkspaceSettingsScreen`, `WorkspaceOverviewScreen`.

* Each screen file is named identically to its component, and exports it as the default or main named export.

### 11.2 Feature components

* Feature‑local components describe their role:

  * `DocumentsTable`, `DocumentsFilters`, `RunsTable`, `RunsFilters`, `ConfigList`, `RunExtractionDialog`.

* Folder structure mirrors URL structure:

  * `/workspaces/:workspaceId/documents` → `screens/workspace-shell/sections/documents/`.
  * `/workspaces/:workspaceId/runs` → `screens/workspace-shell/sections/runs/`.

### 11.3 Hooks

* **Queries** use `use<Domain><What>Query`:

  * `useDocumentsQuery`, `useRunsQuery`, `useConfigurationsQuery`, `useWorkspaceMembersQuery`.

* **Mutations** use `use<Verb><Domain>Mutation`:

  * `useUploadDocumentMutation`, `useStartRunMutation`, `useActivateConfigurationMutation`, `useDeactivateConfigurationMutation`.

* **State / infra hooks** use descriptive names:

  * `useSafeModeStatus`, `useWorkbenchUrlState`, `useNavigationBlocker`, `useSearchParams`.

### 11.4 API modules

* API modules live under `shared/api` and are named `<domain>Api.ts`:

  * `authApi.ts`, `permissionsApi.ts`, `rolesApi.ts`, `workspacesApi.ts`, `documentsApi.ts`, `runsApi.ts`, `configurationsApi.ts`, `buildsApi.ts`, `systemApi.ts`, `apiKeysApi.ts`.

* Functions are “verb + noun” with noun matching the domain model:

  ```ts
  listWorkspaces();
  createWorkspace(input);
  listWorkspaceDocuments(workspaceId, params);
  uploadDocument(workspaceId, file);
  listWorkspaceRuns(workspaceId, params);
  startRun(workspaceId, payload);
  listConfigurations(workspaceId, params);
  activateConfiguration(workspaceId, configurationId);
  ```

Feature hooks wrap these functions into React Query calls.

### 11.5 Types and models

* Domain types are singular, PascalCase:

  * `WorkspaceSummary`, `WorkspaceDetail`.
  * `DocumentSummary`, `DocumentDetail`, `DocumentStatus`.
  * `RunSummary`, `RunDetail`, `RunStatus`.
  * `Configuration`, `ConfigVersion`.

* If you need to distinguish backend wire types, use a clear prefix/suffix (`ApiRun`, `ApiDocument`) and isolate them in `schema/` or `generated-types/`.

---

## 12. Worked example: the Documents feature

To make the structure concrete, here’s how the **Documents** section of the workspace shell fits into the architecture.

```text
src/
  app/
    ScreenSwitch.tsx              # Routes /workspaces/:id/documents → DocumentsScreen
  screens/
    workspace-shell/
      sections/
        documents/
          DocumentsScreen.tsx
          DocumentsTable.tsx
          DocumentsFilters.tsx
          RunExtractionDialog.tsx
          useDocumentsQuery.ts
          useUploadDocumentMutation.ts
  ui/
    button/Button.tsx
    form/Input.tsx
    feedback/Alert.tsx
    global/GlobalTopBar.tsx
  shared/
    api/documentsApi.ts           # listWorkspaceDocuments, uploadDocument, deleteDocument...
    url-state/useSearchParams.ts
    nav/routes.ts                 # workspaceDocuments(workspaceId)
    permissions/permissions.ts
  schema/
    document.ts                   # DocumentSummary, DocumentDetail, DocumentStatus
```

Flow:

1. **Routing**

   * `ScreenSwitch` examines the current location.
   * `/workspaces/:workspaceId/documents` is mapped to `DocumentsScreen`.

2. **Screen logic**

   * `DocumentsScreen`:

     * Reads search parameters (`q`, `status`, `sort`, `view`) via `useSearchParams` from `@shared/url-state`.
     * Calls `useDocumentsQuery(workspaceId, filters)` to fetch data.
     * Renders `GlobalTopBar` and the page layout.
     * Composes `DocumentsFilters`, `DocumentsTable`, and `RunExtractionDialog`.
     * Wires buttons to `useUploadDocumentMutation` and navigation helpers from `@shared/nav/routes`.

3. **Data fetching**

   * `useDocumentsQuery` uses React Query and `documentsApi.listWorkspaceDocuments` under the hood.
   * `documentsApi` builds the `/api/v1/workspaces/{workspace_id}/documents` URL and parses the JSON response.
   * The response is mapped into `DocumentSummary[]` using types from `@schema/document`.

4. **Presentation**

   * `DocumentsTable` and `DocumentsFilters` are presentational components:

     * They receive data and callbacks via props.
     * They use `ui` primitives (`Button`, `Input`, `Alert`) for consistent look and accessibility.

The **Runs** section follows the same pattern, with:

* `screens/workspace-shell/sections/runs/…`
* `RunsScreen`, `RunsTable`, `useRunsQuery`, `useStartRunMutation`.
* `shared/api/runsApi.ts`.
* Domain types in `schema/run.ts`.

If you follow the structure and rules in this doc, adding or changing a feature should always feel the same: pick the right folder in `screens/`, wire it through `app/ScreenSwitch.tsx`, use `shared/` for cross‑cutting logic, and build the UI out of `ui/` primitives.
```

# apps/ade-web/docs/03-routing-navigation-and-url-state.md
```markdown
# 03 – Routing, navigation, and URL state

This document describes how ADE Web turns URLs into screens, how navigation works in our single‑page app, and how we use query parameters to store shareable UI state.

Use this as the reference for anything that:

- Reads or writes the browser location.
- Navigates between screens.
- Encodes view state (filters, tabs, layout) in the URL.

It assumes you’ve read:

- `01-domain-model-and-naming.md` for core terms (workspace, document, run, configuration).
- `02-architecture-and-project-structure.md` for where code lives.

---

## 1. Goals and principles

The routing and navigation layer is designed to be:

- **Predictable** – the URL always tells you “where you are” and “what you’re looking at”.
- **Shareable** – copying the URL should reopen the same view with the same filters/layout.
- **Small** – a thin wrapper around `window.history`, not a framework inside a framework.
- **Guardable** – editors can block navigation when there are unsaved changes.

We follow a few rules:

1. The **location bar is authoritative**. A reload should land you back on the same screen with the same view state.
2. All navigation goes through **`NavProvider`** (`useNavigate` / `Link` / `NavLink`), not raw `history.pushState`.
3. **Query parameters** are the standard way to represent view‑level state that should survive refresh and be shareable.
4. Navigation blockers are **opt‑in and local** to the features that need them (e.g. the Config Builder workbench).

### Canonical sources and names

- Build workspace routes via `@shared/nav/routes` instead of hand‑rolled strings so the route map below and the code stay in sync.
- Query parameter names for workspace sections are defined in the Documents/Runs filter helpers (`parseDocumentFilters` / `buildDocumentSearchParams`, `parseRunFilters` / `buildRunSearchParams`) described in `docs/06` and `docs/07`; add new keys there to keep deep links consistent.
- Permission checks referenced in navigation (e.g. showing nav items) should use the keys in `@schema/permissions` and helper logic in `@shared/permissions`, not ad‑hoc strings.

---

## 2. Routing stack overview

The high‑level stack looks like this:

```tsx
// main.tsx
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
````

```tsx
// App.tsx
export function App() {
  return (
    <NavProvider>
      <AppProviders>
        <ScreenSwitch />
      </AppProviders>
    </NavProvider>
  );
}
```

* **`NavProvider`**
  Owns the current location, listens to `popstate`, applies navigation blockers, and exposes navigation hooks.

* **`AppProviders`**
  Wraps the app with React Query and any other cross‑cutting providers.

* **`ScreenSwitch`**
  Looks at `location.pathname` and chooses the top‑level screen. It is the **only place** that maps raw paths to top‑level React components.

Everything below `ScreenSwitch` (workspaces, documents, runs, Config Builder) uses URL‑encoded view state and query parameters.

---

## 3. Route map

### 3.1 Top‑level routes

`ScreenSwitch` handles a small, explicit set of path prefixes (pseudo‑code):

```ts
switch (true) {
  case path === "/":                  return <EntryScreen />;
  case path === "/login":             return <LoginScreen />;
  case path === "/auth/callback":     return <AuthCallbackScreen />;
  case path === "/setup":             return <SetupScreen />;
  case path === "/logout":            return <LogoutScreen />;

  case path === "/workspaces":        return <WorkspaceDirectoryScreen />;
  case path === "/workspaces/new":    return <CreateWorkspaceScreen />;

  case path.startsWith("/workspaces/"):
    return <WorkspaceShellScreen />;

  default:
    return <NotFoundScreen />;
}
```

Supported top‑level routes:

| Path                         | Responsibility                              |
| ---------------------------- | ------------------------------------------- |
| `/`                          | Entry strategy (decide login/setup/app).    |
| `/login`                     | Login form & auth provider selection.       |
| `/auth/callback`             | Auth provider callback handler.             |
| `/setup`                     | First‑time administrator setup.             |
| `/logout`                    | Logout and session teardown.                |
| `/workspaces`                | Workspace directory.                        |
| `/workspaces/new`            | Create a workspace.                         |
| `/workspaces/:workspaceId/*` | Workspace shell and all workspace sections. |
| `*`                          | Global “Not found” screen.                  |

We **normalize trailing slashes**:

* `/foo/` → `/foo`
* `/workspaces/123/runs/` → `/workspaces/123/runs`

This avoids subtle “same page, different URL” duplication.

### 3.2 Workspace shell routes

Inside `/workspaces/:workspaceId`, the next path segment selects the section:

| Segment          | Example path                     | Section                       |
| ---------------- | -------------------------------- | ----------------------------- |
| `documents`      | `/workspaces/123/documents`      | Documents list & run triggers |
| `runs`           | `/workspaces/123/runs`           | Runs ledger (workspace run history) |
| `config-builder` | `/workspaces/123/config-builder` | Config Builder (configurations list + workbench) |
| `settings`       | `/workspaces/123/settings`       | Workspace settings            |
| `overview`*      | `/workspaces/123/overview`       | Overview/summary (optional)   |

* The `overview` section is optional; if not present, the shell can redirect to a default (e.g. Documents).

Naming stays 1:1: the nav item reads **“Config Builder”**, the route segment is `config-builder`, and the feature folder is `features/workspace-shell/sections/config-builder`. The Config Builder section always includes both the configurations list and the workbench editing mode.

If the workspace ID is valid but the section segment is unknown, the shell should render a **workspace‑local “Section not found”** state, not the global 404. This lets the user switch to another section without leaving the workspace.

### 3.3 Route helpers (`shared/nav/routes.ts`)

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

Use these helpers everywhere (links, navigation logic, tests) instead of hand‑rolled strings. Keeping one source of truth helps the tables above stay in sync with the code.

---

## 4. Navigation model (`NavProvider`)

`NavProvider` is our small custom router: it owns `location`, exposes navigation hooks, and coordinates blockers.

### 4.1 Core types

```ts
type LocationLike = {
  pathname: string;
  search: string;
  hash: string;
};

type NavigationKind = "push" | "replace" | "pop";

type NavigationIntent = {
  readonly to: string;             // full URL string (path + search + hash)
  readonly location: LocationLike; // parsed target
  readonly kind: NavigationKind;
};

type NavigationBlocker = (intent: NavigationIntent) => boolean;
```

* **`LocationLike`** – the minimal location object we expose to components.
* **`NavigationIntent`** – “we are about to navigate to `to`”.
* **`NavigationBlocker`** – returns `true` to allow navigation, `false` to cancel.

### 4.2 Provider behaviour

`NavProvider`:

1. **Initialises location**

   * Reads `window.location` on mount.
   * Normalises the pathname (e.g. trims trailing `/`).

2. **Handles back/forward (`popstate`)**

   * Subscribes to `window.onpopstate`.
   * On event:

     * Constructs a `NavigationIntent` with `kind: "pop"` and the new target.
     * Runs all registered blockers:

       * If **any** returns `false`:

         * Reverts to the previous URL via `history.pushState`.
         * Does **not** update its internal `location` state.
       * Otherwise, updates `location`.

3. **Handles programmatic navigation**

   * Exposes `navigate(to, options?)` via `useNavigate()` (see below).
   * For programmatic calls:

     * Resolves `to` with `new URL(to, window.location.origin)`.
     * Builds a `NavigationIntent` with `kind: "push"` or `"replace"`.
     * Runs blockers.
     * If allowed:

       * Calls `history.pushState` or `history.replaceState`.
       * Dispatches a synthetic `PopStateEvent` so all navigation paths go through the same logic.

The result: back/forward, `Link` clicks, and `navigate()` all share one code path and one blocker mechanism.

Because `new URL(to, window.location.origin)` assumes a root‑served app, if ADE Web ever needs to live under a sub‑path we will centralise the base path in `NavProvider` or `shared/nav/routes.ts` instead of sprinkling `/`‑prefixed strings through components.

### 4.3 Reading the current location (`useLocation`)

```ts
const { pathname, search, hash } = useLocation();
```

* Returns the current `LocationLike`.
* Updates whenever navigation is accepted.
* Use this in any component that needs to:

  * Match route segments (e.g. active nav items).
  * Parse query parameters (`new URLSearchParams(search)`).

**Do not** read `window.location` directly inside React components.

### 4.4 Programmatic navigation (`useNavigate`)

```ts
type NavigateOptions = { replace?: boolean };
type Navigate = (to: string, options?: NavigateOptions) => void;

const navigate = useNavigate();
navigate("/workspaces");
```

* `to` can be:

  * An absolute path (`/workspaces/123/runs`).
  * A relative path (`../documents`).
  * A query‑only change (`?view=members`).

* `replace: true` uses `history.replaceState`, substituting the current entry rather than pushing a new one.

**Guidelines:**

* Use `replace: true` when you’re **fixing** or **normalising** a URL (e.g. invalid `view` value → `view=general`).
* Use the default (`replace: false`) when you’re taking a **logical step** (navigating to another screen).

Never call `history.pushState` or `window.location` directly for internal navigation; always go through `navigate`.

### 4.5 Navigation blockers (`useNavigationBlocker`)

Use navigation blockers when a view has **unsaved changes** that shouldn’t be lost silently.

Conceptual API:

```ts
useNavigationBlocker(blocker: NavigationBlocker, when: boolean);
```

Example pattern for the Config Builder editor:

```ts
const { pathname } = useLocation();

useNavigationBlocker(
  (intent) => {
    if (!hasUnsavedChanges) return true;

    const samePath = intent.location.pathname === pathname;
    if (samePath) {
      // allow query/hash changes even when dirty
      return true;
    }

    // Show your own confirmation UI instead of window.confirm in the real code
    return window.confirm("You have unsaved changes. Leave without saving?");
  },
  hasUnsavedChanges,
);
```

Guidelines:

* Blockers should be **local** to the component that owns the unsaved state.
* They must be **fast** and side‑effect‑free apart from prompting the user.
* Always treat query/hash‑only changes specially (usually allowed even when dirty).

---

## 5. SPA links (`Link` and `NavLink`)

We wrap `<a>` to get SPA navigation while preserving browser semantics (right‑click, middle‑click, copy link).

### 5.1 `Link`

Conceptual props:

```ts
interface LinkProps
  extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  to: string;
  replace?: boolean;
}
```

Behaviour:

* Renders `<a href={to}>…</a>`.

* On click:

  1. Calls any `onClick` handler.
  2. If `event.defaultPrevented`, does nothing else.
  3. If a modifier key is pressed (`meta`, `ctrl`, `shift`, `alt`) or it’s not a left‑click:

     * Let the browser handle it (new tab/window, context menu).
  4. Otherwise:

     * `preventDefault()`.
     * Call `navigate(to, { replace })`.

Use `Link` for all **internal** navigations where you would otherwise use `<a>`.

### 5.2 `NavLink`

`NavLink` adds an “active” state on top of `Link`:

```ts
const isActive = end
  ? pathname === to
  : pathname === to || pathname.startsWith(`${to}/`);
```

Extra props:

* `end?: boolean` – if true, only exact path matches are active.
* `className?: string | ((state: { isActive: boolean }) => string)`.
* `children: ReactNode | ((state: { isActive: boolean }) => ReactNode)`.

Typical usage for left navigation inside the workspace shell:

```tsx
<NavLink
  to={routes.workspaceRuns(workspaceId)}
  className={({ isActive }) =>
    clsx("nav-item", isActive && "nav-item--active")
  }
>
  Runs
</NavLink>
```

Use `NavLink` anywhere you want route‑aware styling, e.g. nav menus, route‑backed tabs.

---

## 6. URL state and search parameters

### 6.1 Why encode state in the URL

We use query parameters for view‑level state that:

* Should survive refresh,
* Should be shareable via URL, and
* Does not need to stay private.

Examples:

* Documents filters and sort order.
* Which settings tab is selected.
* Config Builder layout (editor vs split vs zen, which pane is open).

Plain local component state is fine for **purely ephemeral** UI (e.g. whether a dropdown is open). If a user might:

* Bookmark it,
* Share it with a teammate, or
* Expect the browser back button to step through it,

it should live in the URL.

### 6.2 Low‑level helpers

Helpers in `shared/urlState` handle raw query string operations:

* `toURLSearchParams(init)`

  * Accepts strings, `URLSearchParams`, arrays, or plain objects.
  * Produces a `URLSearchParams` instance.

* `getParam(search, key)`

  * Extracts a single value from a `search` string (with or without `?`).

* `setParams(url, patch)`

  * Patches query parameters on a `URL` object and returns the new `path + search + hash`.

You rarely need these directly; they power `useSearchParams()`.

### 6.3 `useSearchParams()`

API:

```ts
const [params, setSearchParams] = useSearchParams();
```

* `params` – current `URLSearchParams` for `location.search`.
* `setSearchParams(init, options?)` – update query parameters:

  ```ts
  type SearchParamsInit =
    | string
    | string[][]
    | URLSearchParams
    | Record<string, string | string[] | null | undefined>
    | ((prev: URLSearchParams) => SearchParamsInit);

  interface SetSearchParamsOptions {
    replace?: boolean;
  }
  ```

When called:

1. We compute the new `URLSearchParams`.
2. Build a full target URL with the current `pathname` and `hash`.
3. Call `navigate(target, { replace })` under the hood.

**Usage patterns:**

* Patch in place:

  ```ts
  setSearchParams(prev => {
    const params = new URLSearchParams(prev);

    if (nextStatus) params.set("status", nextStatus);
    else params.delete("status");

    return params;
  }, { replace: true });
  ```

* Use `replace: true` when tweaking filters or tabs (back button should skip over tiny changes).

* Use `replace: false` if query changes represent a new logical step in a flow (less common).

### 6.4 `SearchParamsOverrideProvider`

Most of the app should talk to the **real** URL. `SearchParamsOverrideProvider` exists for a few niche cases where a subtree needs **query‑like** state but must not mutate `window.location`.

Conceptually:

```ts
interface SearchParamsOverrideValue {
  readonly params: URLSearchParams;
  readonly setSearchParams: (
    init: SetSearchParamsInit,
    options?: SetSearchParamsOptions,
  ) => void;
}
```

Within the provider:

* `useSearchParams()` returns the override instead of the global URL‑backed one.

Use cases:

* Embedded flows that reuse components expecting `useSearchParams`, but where URL changes would be misleading.
* Transitional/legacy flows where you cannot yet change the real URL model.

Rules:

* **Do not** wrap whole sections or screens; that defeats deep‑linking.
* Document each usage with a comment explaining why the override is needed.
* Prefer migrating to real URL state over time.

### 6.5 Typed query helpers for filters

For non‑trivial query state (documents filters, run filters), use typed helper pairs instead of scattered strings: `parseDocumentFilters(params: URLSearchParams)` / `buildDocumentSearchParams(filters)` or `parseRunFilters` / `buildRunSearchParams`. Centralising canonical names (`q`, `status`, `view`, etc.) keeps components consistent and deep links predictable. See `07-documents-and-runs.md` for the canonical filter shapes.

---

## 7. Canonical query parameters

This section defines the expected query parameters per view. Having one place to look keeps naming consistent.

### 7.1 Auth

On `/login` and related auth routes:

* `redirectTo` (string):

  * Target path after successful login.
  * Must be a **relative**, same‑origin path.
  * Examples: `/workspaces`, `/workspaces/123/documents`.

The backend and frontend both validate `redirectTo` to avoid open redirects.

### 7.2 Workspace settings

On `/workspaces/:workspaceId/settings`:

* `view` (string):

  * Allowed values: `general`, `members`, `roles`.
  * Controls which tab is active.

Behaviour:

* Invalid or missing `view` is normalised to `general` using `navigate(..., { replace: true })` to keep history clean.

### 7.3 Documents

On `/workspaces/:workspaceId/documents`:

* `q` (string):

  * Free‑text query (document name, source, etc.).

* `status` (string):

  * Comma‑separated document statuses.
  * Example: `status=uploaded,processed,failed`.

* `sort` (string):

  * Sort key and direction.
  * Examples: `sort=-created_at`, `sort=-last_run_at`.

* `view` (string):

  * View preset.
  * Suggested values: `all`, `mine`, `team`, `attention`, `recent`.

These parameters make documents views sharable:

> “Show me all failed documents in workspace X” should be a URL, not just a filter in memory.

### 7.4 Runs

On `/workspaces/:workspaceId/runs`:

* `status` (string, optional):

  * Comma‑separated run statuses.

* `configurationId` (string, optional):

  * Filter by configuration ID.

* `initiator` (string, optional):

  * Filter by user id/email.

* `from`, `to` (string, optional):

  * ISO‑8601 date boundaries for run start time.

These names should be stable so that links from other parts of the UI (e.g. “View runs for this configuration”) can construct correct URLs.

### 7.5 Config Builder (summary)

On `/workspaces/:workspaceId/config-builder` with an active workbench:

* `pane` (string):

  * Bottom panel tab: `console` or `validation`.

* `console` (string):

  * Console visibility: `open` or `closed`.

* `view` (string):

  * Layout mode: `editor`, `split`, `zen`.

* `file` (string):

  * ID/path of the active file in the workbench.

The Config Builder URL state is documented in detail in `09-workbench-editor-and-scripting.md`. The important rule here: we only write **non‑default** values back into the URL to keep it tidy.

---

## 8. Extending the route map and URL state

When adding new routes or URL‑encoded state, follow this checklist:

1. **Decide the owner and scope**

   * Global (auth, setup, workspace directory) vs workspace‑scoped (`/workspaces/:workspaceId/...`).
   * Which feature folder will own the screen (`features/workspace-shell/runs`, etc.).

2. **Add a `Screen` component and hook it into `ScreenSwitch`**

   * Create `SomethingScreen.tsx` under the appropriate feature folder.
   * Add a branch in `ScreenSwitch` (for top‑level) or in `WorkspaceShellScreen` (for sections).

3. **Define route helpers**

   * Centralise URL construction in `shared/nav/routes.ts` (see §3.3), and add any new helpers there.
   * Use these helpers in `Link` / `NavLink`, navigation logic, and tests instead of ad‑hoc strings. If we ever host under a sub‑path, this is where a base path would be defined.

4. **Register query parameters here**

   * Add a row/section in §7 for new query parameters.
   * Decide names and allowed values up front; avoid one‑off strings sprinkled in components.

5. **Use `useSearchParams()` in your feature**

   * Do not hand‑parse `location.search`.
   * Prefer `setSearchParams(prev => ...)` with `{ replace: true }` for filters.

6. **Avoid surprises**

   * Don’t override history in unexpected ways.
   * Don’t encode large or sensitive payloads in the URL.

If we follow these patterns, the routing and URL‑state model stays small, obvious, and easy to extend as ADE Web grows.
```

# apps/ade-web/docs/04-data-layer-and-backend-contracts.md
```markdown
# 04 – Data layer and backend contracts

This document explains how `ade-web` talks to the ADE backend:

- the **data layer architecture** (HTTP client, API modules, React Query hooks),
- how `/api/v1/...` routes are **grouped by domain**,
- how we model **Runs**, workspaces, documents, and configurations in the data layer,
- and how we handle **streaming**, **errors**, and **caching**.

It is the implementation‑level companion to:

- the domain language in `01-domain-model-and-naming.md`, and
- the UX overview in the top‑level `README.md`.

All terminology here uses **Run** as the primary execution unit. Backend routes expose the REST plural `/runs`; in the UI and types we keep the concept as Run with the ID field `runId`.

---

## 1. Architecture and goals

The data layer has three tiers:

1. A **thin HTTP client** that knows how to call `/api/v1/...` and normalise errors.
2. **Domain API modules** (e.g. `workspacesApi`, `documentsApi`, `runsApi`) that wrap specific endpoints.
3. **React Query hooks** in feature folders that connect those modules to UI components.

Flow:

```text
[ Screens / Features ]
        │
        ▼
[ React Query hooks ]  e.g. useWorkspaceRunsQuery, useDocumentsQuery
        │
        ▼
[ API modules ]        e.g. workspacesApi, documentsApi, runsApi
        │
        ▼
[ HTTP client ]        shared/api/httpClient.ts
        │
        ▼
[ ADE API ]            /api/v1/...
````

Design goals:

* **Single source of truth** for each endpoint.
* **Type‑safe** responses with explicit models.
* **Predictable caching** via React Query.
* **Clear separation**:

  * Screens know about hooks and domain types.
  * Hooks know about API modules.
  * API modules know about HTTP and paths.

No UI code calls `fetch` directly; everything goes through the shared HTTP client.

---

## 2. HTTP client

All HTTP calls go through a shared client in `src/shared/api/httpClient.ts` (or equivalent).

### 2.1 Responsibilities

The HTTP client is responsible for:

* Building the full URL (e.g. `/api/v1/...` under the `/api` proxy).
* Serialising request bodies (JSON by default).
* Attaching credentials (cookies, headers) as required.
* Parsing JSON responses.
* Exposing streaming bodies when needed (for NDJSON).
* Mapping non‑2xx responses to a unified `ApiError`.

It deliberately does **not** know about workspaces, runs, configurations, etc.

### 2.2 Basic interface

A minimal shape:

```ts
export interface ApiErrorPayload {
  status: number;
  message: string;
  code?: string;
  details?: unknown;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;
}

export async function apiRequest<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  options?: {
    query?: Record<string, unknown>;
    body?: unknown;
    signal?: AbortSignal;
    headers?: Record<string, string>;
  },
): Promise<T> {
  // ...
}
```

Rules:

* API modules **only** use `apiRequest`; they never use `fetch` directly.
* `apiRequest` throws an `ApiError` for any non‑2xx status, with a meaningful `message` where possible.

### 2.3 Authentication and 401/403

* 401 (unauthenticated) is handled at a **global** layer (e.g. invalidate session, redirect to `/login`).
* 403 (forbidden) is surfaced to the UI as a permissions error.

The HTTP client itself does not automatically refresh tokens; that logic lives in the auth/session layer and React Query hooks.

---

## 3. React Query

React Query orchestrates fetching, caching, and background updates.

### 3.1 Query client configuration

`AppProviders` creates a single `QueryClient` with sane defaults:

* `retry: 1` – most ADE errors are not transient.
* `staleTime: 30_000` – many reads can be reused for ~30 seconds.
* `refetchOnWindowFocus: false` – avoids surprise reloads when switching tabs.

These can be overridden per query (e.g. for health checks).

### 3.2 Query keys

Query keys must be:

* **Stable** – same inputs → same key.
* **Descriptive** – easy to inspect in devtools.
* **Scoped** – from global → workspace → resource.
* **Canonical** – objects inside keys must be serialised to a stable representation (sort keys + `JSON.stringify` or a dedicated canonicaliser). Avoid fresh inline objects in render bodies; prefer small helpers that always return the same shape for the same params.

Patterns:

* Session & permissions:

  * `['session']`
  * `['permissions', 'effective']`

* Workspaces:

  * `['workspaces']`
  * `['workspace', workspaceId]`
  * `['workspace', workspaceId, 'members']`
  * `['workspace', workspaceId, 'roles']`

* Documents:

  * `['workspace', workspaceId, 'documents', canonicaliseDocumentParams(params)]`
  * `['workspace', workspaceId, 'document', documentId]`
  * `['workspace', workspaceId, 'document', documentId, 'sheets']`

* Runs:

  * `['workspace', workspaceId, 'runs', canonicaliseRunsFilters(params)]` // lists from `/runs` endpoints
  * `['run', runId]`                                                     // canonical run detail via `/runs/{run_id}`
  * `['workspace', workspaceId, 'run', runId]`                           // optional workspace‑scoped variant
  * `['run', runId, 'outputs']`

* Configurations:

  * `['workspace', workspaceId, 'configurations']`
  * `['workspace', workspaceId, 'configuration', configurationId]`
  * `['workspace', workspaceId, 'configuration', configurationId, 'versions']`
  * `['workspace', workspaceId, 'configuration', configurationId, 'files']`

* System:

  * `['system', 'safe-mode']`
  * `['system', 'health']`

Filters and sort options go into a **canonicalised** params payload that is part of the key. A tiny factory keeps this predictable:

```ts
export const queryKeys = {
  workspaceRuns: (workspaceId: string, filters: RunsFilters) => [
    "workspace",
    workspaceId,
    "runs",
    canonicaliseRunsFilters(filters),
  ],
  run: (runId: string) => ["run", runId],
  documents: (workspaceId: string, params: DocumentFilters) => [
    "workspace",
    workspaceId,
    "documents",
    canonicaliseDocumentParams(params),
  ],
};
```

### 3.3 Query and mutation hooks

For each domain:

* API modules export **plain functions** (`listWorkspaceRuns`, `uploadDocument`, `activateConfiguration`).
* Features define **hooks** that wrap those functions in React Query:

  * Queries: `useWorkspaceRunsQuery(workspaceId, filters)`, `useDocumentsQuery(workspaceId, filters)`.
  * Mutations: `useCreateWorkspaceRunMutation(workspaceId)`, `useUploadDocumentMutation(workspaceId)`.

Hooks live near the screen components that use them (e.g. `features/workspace-shell/runs/useWorkspaceRunsQuery.ts`) and depend on the shared API modules.

---

## 4. Domain API modules

Domain API modules live under `src/shared/api/`. Each module owns a set of related endpoints and exposes typed functions.

Naming:

* Modules: `authApi`, `permissionsApi`, `rolesApi`, `workspacesApi`, `documentsApi`, `runsApi`, `configurationsApi`, `buildsApi`, `systemApi`, `apiKeysApi`.
* Functions: `<verb><Noun>` (e.g. `listWorkspaceRuns`, `createWorkspaceRun`, `activateConfiguration`).

Below we describe what each module covers and how it maps to backend routes.

### 4.1 Auth & session (`authApi`)

**Responsibilities**

* Initial setup.
* Login/logout (email/password and SSO).
* Session and current user.

**Key routes**

* Setup:

  * `GET  /api/v1/setup/status` – read initial setup status.
  * `POST /api/v1/setup`        – complete first admin setup.

* Session:

  * `POST   /api/v1/auth/session`         – create session.
  * `GET    /api/v1/auth/session`         – read session (canonical “who am I?”).
  * `POST   /api/v1/auth/session/refresh` – refresh session.
  * `DELETE /api/v1/auth/session`         – logout.

* Auth providers:

  * `GET /api/v1/auth/providers` – configured auth providers.
  * `GET /api/v1/auth/sso/login` – initiate SSO login (302 redirect).
  * `GET /api/v1/auth/sso/callback` – finish SSO login.

* User profile:

  * `GET /api/v1/users/me` or `GET /api/v1/auth/me` – authenticated user (name, email, id).

**Example functions**

* `readSetupStatus()`
* `completeSetup(payload)`
* `listAuthProviders()`
* `createSession(credentials)`
* `refreshSession()`
* `deleteSession()`
* `readSession()`
* `readCurrentUser()`

Hooks:

* `useSetupStatusQuery()`
* `useSessionQuery()`
* `useCurrentUserQuery()`
* `useLoginMutation()`, `useLogoutMutation()`

### 4.2 Permissions (`permissionsApi`)

**Responsibilities**

* Permission catalog.
* Effective permissions.
* Permission checks for specific operations.

**Key routes**

* Permissions:

  * `GET  /api/v1/permissions`             – permission catalog.
  * `GET  /api/v1/me/permissions`          – effective permissions.
  * `POST /api/v1/me/permissions/check`    – check specific permissions.

**Example functions**

* `listPermissions()`
* `readEffectivePermissions()`
* `checkPermissions(request)`

Hooks:

* `useEffectivePermissionsQuery()`
* `usePermissionCatalogQuery()`

### 4.3 Global roles & assignments (`rolesApi`)

Keep global roles distinct from permissions for searchability and parity with workspace‑scoped role handling.

**Responsibilities**

* Global roles.
* Global role assignments.

**Key routes**

* Global roles:

  * `GET    /api/v1/roles`
  * `POST   /api/v1/roles`
  * `GET    /api/v1/roles/{role_id}`
  * `PATCH  /api/v1/roles/{role_id}`
  * `DELETE /api/v1/roles/{role_id}`

* Global role assignments:

  * `GET    /api/v1/role-assignments`
  * `POST   /api/v1/role-assignments`
  * `DELETE /api/v1/role-assignments/{assignment_id}`

**Example functions**

* `listGlobalRoles()`
* `createGlobalRole(payload)`
* `readGlobalRole(roleId)`
* `updateGlobalRole(roleId, patch)`
* `deleteGlobalRole(roleId)`
* `listGlobalRoleAssignments()`
* `createGlobalRoleAssignment(payload)`
* `deleteGlobalRoleAssignment(assignmentId)`

Hooks:

* `useGlobalRolesQuery()`, `useGlobalRoleAssignmentsQuery()`

### 4.4 Workspaces & membership (`workspacesApi`)

**Responsibilities**

* Workspace lifecycle and metadata.
* Membership within a workspace.
* Workspace‑scoped roles and role assignments.
* Default workspace.

**Key routes**

* Workspaces:

  * `GET    /api/v1/workspaces`
  * `POST   /api/v1/workspaces`
  * `GET    /api/v1/workspaces/{workspace_id}`
  * `PATCH  /api/v1/workspaces/{workspace_id}`
  * `DELETE /api/v1/workspaces/{workspace_id}`
  * `POST   /api/v1/workspaces/{workspace_id}/default`

* Members:

  * `GET    /api/v1/workspaces/{workspace_id}/members`
  * `POST   /api/v1/workspaces/{workspace_id}/members`
  * `DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}`
  * `PUT    /api/v1/workspaces/{workspace_id}/members/{membership_id}/roles`

* Workspace roles & assignments:

  * `GET    /api/v1/workspaces/{workspace_id}/roles`
  * `GET    /api/v1/workspaces/{workspace_id}/role-assignments`
  * `POST   /api/v1/workspaces/{workspace_id}/role-assignments`
  * `DELETE /api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}`

**Example functions**

* Workspaces:

  * `listWorkspaces()`
  * `createWorkspace(payload)`
  * `readWorkspace(workspaceId)`
  * `updateWorkspace(workspaceId, patch)`
  * `deleteWorkspace(workspaceId)`
  * `setDefaultWorkspace(workspaceId)`

* Members:

  * `listWorkspaceMembers(workspaceId)`
  * `addWorkspaceMember(workspaceId, payload)`
  * `removeWorkspaceMember(workspaceId, membershipId)`
  * `updateWorkspaceMemberRoles(workspaceId, membershipId, roles)`

* Workspace‑scoped roles:

  * `listWorkspaceRoles(workspaceId)`
  * `listWorkspaceRoleAssignments(workspaceId)`
  * `createWorkspaceRoleAssignment(workspaceId, payload)`
  * `deleteWorkspaceRoleAssignment(workspaceId, assignmentId)`

Hooks:

* `useWorkspacesQuery()`
* `useWorkspaceQuery(workspaceId)`
* `useWorkspaceMembersQuery(workspaceId)`
* `useWorkspaceRolesQuery(workspaceId)`

### 4.5 Documents (`documentsApi`)

**Responsibilities**

* Document upload and listing per workspace.
* Document metadata and download.
* Sheet metadata for spreadsheet‑like inputs.

**Key routes**

* `GET  /api/v1/workspaces/{workspace_id}/documents`
* `POST /api/v1/workspaces/{workspace_id}/documents`
* `GET  /api/v1/workspaces/{workspace_id}/documents/{document_id}`
* `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`
* `GET  /api/v1/workspaces/{workspace_id}/documents/{document_id}/download`
* `GET  /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`

**Example functions**

* `listDocuments(workspaceId, params)`
* `uploadDocument(workspaceId, file, options?)`
* `readDocument(workspaceId, documentId)`
* `deleteDocument(workspaceId, documentId)`
* `downloadDocument(workspaceId, documentId)`
* `listDocumentSheets(workspaceId, documentId)`

Hooks:

* `useDocumentsQuery(workspaceId, filters)`
* `useDocumentQuery(workspaceId, documentId)`
* `useDocumentSheetsQuery(workspaceId, documentId)`

Mutations:

* `useUploadDocumentMutation(workspaceId)`
* `useDeleteDocumentMutation(workspaceId)`

### 4.6 Runs (`runsApi`)

**Responsibilities**

* Workspace run ledger (list of all runs in a workspace).
* Per‑run artifacts, outputs, and log files.
* Configuration‑initiated runs (e.g. from Config Builder).
* Run‑level event streams (NDJSON).
* Run‑centric API surface: once you have a `runId`, treat it as globally unique and use the global `/runs/{run_id}` detail/asset endpoints. Workspace IDs show up only when listing or creating runs.

Backend routes use the REST plural `/runs`; both workspace run ledger endpoints and configuration/global run endpoints represent the same **Run** concept in the frontend.

**Key routes: workspace run ledger (under `/runs`)**

* `GET  /api/v1/workspaces/{workspace_id}/runs` – list runs for workspace.
* `POST /api/v1/workspaces/{workspace_id}/runs` – submit new run.
* `GET  /api/v1/workspaces/{workspace_id}/runs/{run_id}` – optional workspace‑scoped detail if tenancy enforcement requires it.

Use these ledger endpoints for listing and creating runs; fetch detail, outputs, and logs from the global endpoints once a `runId` exists.

**Key routes: run detail & assets (global preferred)**

* `GET  /api/v1/runs/{run_id}` – read run detail (canonical).
* `GET  /api/v1/runs/{run_id}/artifact` – download artifact.
* `GET  /api/v1/runs/{run_id}/logfile` – download logs file.
* `GET  /api/v1/runs/{run_id}/logs` – stream the run NDJSON event stream.
* `GET  /api/v1/runs/{run_id}/outputs` – list outputs.
* `GET  /api/v1/runs/{run_id}/outputs/{output_path}` – download output.

**Key routes: configuration‑scoped triggers**

* `POST /api/v1/configurations/{configuration_id}/runs` – start a run for a given configuration.

**Example functions**

Workspace‑level:

* `listWorkspaceRuns(workspaceId, params)`
* `createWorkspaceRun(workspaceId, payload)`
* `readWorkspaceRun(workspaceId, runId)`           // optional when backend enforces workspace scopes

Run‑centric (canonical):

* `readRun(runId)`
* `listRunOutputs(runId)`
* `downloadRunOutput(runId, outputPath)`
* `downloadRunArtifact(runId)`
* `downloadRunLogFile(runId)`
* `streamRunLogs(runId)`                           // run event stream (NDJSON)

Configuration triggers:

* `createConfigurationRun(configurationId, payload)`      // wraps `/configurations/{configuration_id}/runs`

Hooks:

* `useWorkspaceRunsQuery(workspaceId, filters)`
* `useRunQuery(runId)`                          // preferred detail hook; runId assumed globally unique
* Optional: `useWorkspaceRunQuery(workspaceId, runId)` when a workspace‑scoped detail endpoint is required
* `useCreateWorkspaceRunMutation(workspaceId)`
* `useCreateConfigurationRunMutation(configurationId)`

Streaming hook:

* `useRunLogsStream(runId)` for the live run event stream and console.

### 4.7 Configurations & builds (`configurationsApi`, `buildsApi`)

**Responsibilities**

* Configuration entities and versions.
* Config file tree and file contents for the workbench.
* Build and validate operations.

**Key routes: configurations**

* `GET  /api/v1/workspaces/{workspace_id}/configurations`
* `POST /api/v1/workspaces/{workspace_id}/configurations`
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}`
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/versions`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/activate`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/deactivate`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/publish`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/validate`
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/export`

**Key routes: configuration files**

* `GET    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files`
* `GET    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
* `PUT    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
* `PATCH  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
* `POST   /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}`
* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}`

**Key routes: builds**

* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds`
* `GET  /api/v1/builds/{build_id}`
* `GET  /api/v1/builds/{build_id}/logs` – stream build logs (NDJSON).

**Example functions**

Configurations:

* `listConfigurations(workspaceId)`
* `createConfiguration(workspaceId, payload)`
* `readConfiguration(workspaceId, configurationId)`
* `listConfigurationVersions(workspaceId, configurationId)`
* `activateConfiguration(workspaceId, configurationId)`
* `deactivateConfiguration(workspaceId, configurationId)`
* `publishConfiguration(workspaceId, configurationId)`
* `validateConfiguration(workspaceId, configurationId, payload)`
* `exportConfiguration(workspaceId, configurationId)`

Config files:

* `listConfigurationFiles(workspaceId, configurationId)`
* `readConfigurationFile(workspaceId, configurationId, filePath)`
* `upsertConfigurationFile(workspaceId, configurationId, filePath, content, options?)`  // includes ETag preconditions.
* `renameConfigurationFile(workspaceId, configurationId, filePath, newPath)`
* `deleteConfigurationFile(workspaceId, configurationId, filePath)`
* `createConfigDirectory(workspaceId, configurationId, dirPath)`
* `deleteConfigDirectory(workspaceId, configurationId, dirPath)`

Builds:

* `createBuild(workspaceId, configurationId, options)`  // returns `buildId`.
* `readBuild(buildId)`
* `streamBuildLogs(buildId)`

Hooks:

* `useConfigurationsQuery(workspaceId)`
* `useConfigurationQuery(workspaceId, configurationId)`
* `useConfigurationVersionsQuery(workspaceId, configurationId)`
* `useConfigurationFilesQuery(workspaceId, configurationId)`
* `useCreateBuildMutation(workspaceId, configurationId)`
* `useBuildLogsStream(buildId)`

### 4.8 System & Safe mode (`systemApi`)

**Responsibilities**

* System health.
* Safe mode status and updates.

**Key routes**

* `GET /api/v1/health`
* `GET /api/v1/system/safe-mode`
* `PUT /api/v1/system/safe-mode`

**Example functions**

* `readHealth()`
* `readSafeMode()`
* `updateSafeMode(payload)`

Hooks:

* `useSafeModeQuery()`
* `useUpdateSafeModeMutation()`

### 4.9 Users & API keys (`usersApi`, `apiKeysApi`)

**Responsibilities**

* User directory (admin use).
* API key management for users.

**Key routes**

* Users:

  * `GET /api/v1/users` – list all users (admin only).

* API keys:

  * `GET    /api/v1/auth/api-keys`
  * `POST   /api/v1/auth/api-keys`
  * `DELETE /api/v1/auth/api-keys/{api_key_id}`

**Example functions**

* `listUsers(params?)`
* `listApiKeys()`
* `createApiKey(payload)`
* `revokeApiKey(apiKeyId)`

Hooks:

* `useUsersQuery()`
* `useApiKeysQuery()`
* `useCreateApiKeyMutation()`
* `useRevokeApiKeyMutation()`

---

## 5. Typed models and schemas

The data layer uses TypeScript types from two places:

1. **Generated types** (if present) in `src/generated-types/`.
2. **Domain models** in `src/schema/`.

### 5.1 Generated types

Generated types:

* Mirror backend schemas 1:1 (field names, nested structures).
* Are authoritative for the wire format.
* May expose internal details that we don’t want to leak into screens.

We typically consume them only in API modules and mapping functions.

### 5.2 Domain models

Domain models in `src/schema/` provide UI‑oriented shapes:

* `WorkspaceSummary`, `WorkspaceDetail`
* `DocumentSummary`, `DocumentDetail`
* `RunSummary`, `RunDetail`
* `Configuration`, `ConfigVersion`
* `SafeModeStatus`, etc.

API modules are responsible for mapping:

```ts
function toRunSummary(apiRun: ApiRun): RunSummary { /* ... */ }
```

Standard mappers in `schema/` keep snake_case out of features:

* `fromApiRun(apiRun: ApiRun): Run` – translates `run_id` → `runId` and normalises timestamps/status.
* `fromApiConfiguration(apiConfig: ApiConfiguration): Configuration` – translates `configuration_id` → `configurationId` and applies any presentation helpers.

Do this translation once so screens and hooks only ever see camelCase IDs.

This gives us:

* A stable surface for screens, even if backend fields change.
* A clear place to rename things (e.g. `run_id` → `runId` in the UI).

---

## 6. Streaming NDJSON logs

Some endpoints stream logs/events as NDJSON. We treat these as **event streams**, not as “queries”.

### 6.1 Streaming abstraction

A small module in `src/shared/ndjson/` provides a generic NDJSON reader, for example:

```ts
export interface NdjsonEvent {
  type?: string;
  [key: string]: unknown;
}

export function streamNdjson(
  path: string,
  options?: { signal?: AbortSignal },
  onEvent?: (event: NdjsonEvent) => void,
): Promise<void> {
  // open fetch, read chunks, split by newline, JSON.parse, call onEvent
}
```

Key characteristics:

* Accepts an `AbortSignal` so callers can terminate the stream.
* Parses each line as JSON; lines that fail to parse are either ignored or reported via an error callback.

### 6.2 Run and build streams

Used by:

* Config Builder:

  * `streamBuildLogs(buildId)` → `/api/v1/builds/{build_id}/logs` (build log stream).

* Run consoles:

  * `streamRunLogs(runId)` → `/api/v1/runs/{run_id}/logs` (run event stream).

Event format is determined by the backend. We expect at minimum:

* A `type` field (e.g. `"log"`, `"status"`, `"summary"`).
* A `timestamp`.
* Either a `message` or structured `data`.

UI code in the workbench or run detail screen:

* Appends log lines to a console buffer.
* Updates derived status (e.g. completed, failed) when a terminal event arrives.

### 6.3 Cancellation and errors

Streaming helpers:

* Always create an `AbortController` in the calling component.
* Cancel the stream on unmount or when the user closes the console.

Error handling:

* Network or server errors should be surfaced as a **console banner** (“Stream disconnected”) rather than thrown.
* The component may optionally allow manual retry.

We deliberately do **not** wrap NDJSON streams in React Query; they are long‑lived event flows, not snapshot fetches.

---

## 7. Error handling and retry

### 7.1 `ApiError` handling

Every endpoint that fails returns an `ApiError` from the HTTP client:

* `status` – HTTP status code.
* `message` – user‑friendly message when available.
* `code` – optional machine code from backend.
* `details` – optional structured payload.

API modules do not catch these errors; they are allowed to propagate to React Query.

### 7.2 Where to surface errors

Guidelines:

* **Mutations (buttons/forms)**:

  * Show a toast for “one‑off” actions (start run, save file).
  * Show inline error text for validation problems.

* **List/detail screens**:

  * Use an inline `Alert` in the main content area if loading fails.
  * For critical surfaces, show a full “something went wrong” state with a retry button.

* **Streaming consoles**:

  * Show a console‑local banner on stream errors.
  * Don’t crash the surrounding screen.

### 7.3 Retry policy

Default `retry: 1` is fine for most queries.

Override with `retry: false` when:

* Hitting permission endpoints that will not succeed without user state change (403).
* Calling validation endpoints where repeated attempts won’t help.

Mutations:

* Rely on explicit user retries (e.g. clicking “Run again”) rather than automatic retry.

---

## 8. Contracts, invariants, and adding endpoints

### 8.1 Invariants

To keep the data layer predictable:

* **Single owner per endpoint**

  * Each backend route is wrapped by exactly one function in one module.
  * Screens and hooks never embed raw URLs.

* **Explicit types**

  * No `any` for responses; map to domain models.
  * Backend changes should be reflected in `schema/` and, where needed, in mapping functions.

* **Stable query keys**

  * Params in keys are canonicalised (sorted keys + stable `JSON.stringify` or dedicated helper).
  * Use small `queryKeys` factories to avoid ad‑hoc objects created in render bodies.

* **No direct `fetch`**

  * Only the HTTP client talks to `fetch` / XHR.
  * This keeps auth, error handling, and logging consistent.

* **Run‑centric terminology**

  * All execution units are “runs” in frontend types, hooks, and screens.
  * Once you have a `runId`, use the global `/runs/{run_id}` endpoints for detail, logs, and outputs; workspace IDs are only needed to list or create runs.
  * API module mapping handles backend field names like `run_id` → `runId`.

* **Backend‑agnostic**

  * ADE Web depends on the *behaviour* and *shapes* described here, not on any specific backend implementation.
  * As long as `/api/v1/...` contracts are preserved, different backends can power the UI.

### 8.2 Adding a new endpoint

When a new backend route appears:

1. **Choose a module**

   * Workspaces, documents, runs, configurations, roles, auth, system, etc.
   * If it doesn’t fit, introduce a new module in `shared/api`.

2. **Add a typed function**

   * Implement `<verb><Noun>` in that module using `apiRequest`.
   * Map the wire shape into a domain model if needed.

3. **Add a hook**

   * Create `useXxxQuery` or `useXxxMutation` in the relevant feature folder.
   * Use a consistent query key pattern and invalidate affected keys on write.

4. **Update types**

   * Add or adjust domain types in `schema/`.
   * Wire in generated types if you have them.

5. **Update docs**

   * Add the route and function to the relevant section of this file.
   * If it introduces a new domain concept, update `01-domain-model-and-naming.md`.

6. **Add tests**

   * Unit tests for the API function (mocking `apiRequest`).
   * Integration tests for the feature, when appropriate.

Following these rules keeps the data layer small, obvious, and easy to navigate—for both humans and AI agents—while making it straightforward to evolve the ADE backend over time.
```

# apps/ade-web/docs/05-auth-session-rbac-and-safe-mode.md
```markdown
# 05 – Auth, Session, RBAC, and Safe Mode

ADE Web relies on the backend for:

- **Authentication** (setup, login, logout, SSO),
- The current **session** (who is the signed‑in user),
- **Roles & permissions** (RBAC),
- A global **Safe mode** kill switch that blocks new runs.

This document describes how the frontend models these concepts and how they are used to shape the UI.

For domain terminology (Workspace, Document, Run, Configuration, etc.), see  
[`01-domain-model-and-naming.md`](./01-domain-model-and-naming.md).

---

## 1. Goals and scope

**Goals**

- One clear, consistent mental model for auth, session, RBAC, and Safe mode.
- Make it obvious where to fetch identity and permissions, and how to check them.
- Ensure Safe mode behaviour is consistent everywhere runs can be started.
- Keep the frontend thin: permission decisions are made on the backend; the UI only consumes them.

**Non‑goals**

- Describing the backend’s full auth/RBAC implementation.
- Enumerating every possible permission key.

Only frontend‑relevant behaviour and contracts are covered here.

---

## 2. Core frontend models

### 2.1 Session (who is signed in)

The **Session** describes the current principal (signed‑in user) and their high‑level context.

```ts
export interface Session {
  readonly user: {
    readonly id: string;
    readonly name: string;
    readonly email: string;
    readonly avatarUrl?: string | null;
  };

  /** Optional "home" workspace used as a default landing. */
  readonly defaultWorkspaceId?: string | null;

  /** Lightweight view of where this user belongs. */
  readonly workspaceMemberships: readonly WorkspaceMembershipSummary[];
}

export interface WorkspaceMembershipSummary {
  readonly workspaceId: string;
  readonly workspaceName: string;
  /** Role ids/slugs in this workspace (for display and mapping to permissions). */
  readonly roles: readonly string[];
}
````

Characteristics:

* Fetched via `GET /api/v1/auth/session` (or `GET /api/v1/users/me` if that is the canonical endpoint).
* Cached with React Query.
* Treated as the **single source of truth** for “who am I?”; we do not duplicate user identity elsewhere.

We **do not** persist session data or tokens in `localStorage`. Auth is handled by the backend (typically via cookies). The frontend simply reads and reacts to the session.

### 2.2 Effective permissions

The frontend does not recompute permission graphs. Instead it consumes a pre‑computed set of permission keys from the backend.

```ts
export interface EffectivePermissions {
  /** Global permissions that apply regardless of workspace. */
  readonly global: readonly string[];

  /** Optional: per‑workspace permission keys. */
  readonly workspaces?: Record<string, readonly string[]>;
}
```

This is fetched via:

* `GET /api/v1/me/permissions`, optionally accompanied by:
* `POST /api/v1/me/permissions/check` for specific “does the caller have X?” questions.

Permissions are **string keys** like:

* `Workspaces.Create`
* `Workspace.Runs.Read`
* `Workspace.Runs.Run`
* `Workspace.Settings.ReadWrite`
* `System.SafeMode.Read`
* `System.SafeMode.ReadWrite`

The exact catalog is backend‑defined and discoverable via `GET /api/v1/permissions` for settings UIs.

### 2.3 Safe mode status

Safe mode is represented as:

```ts
export interface SafeModeStatus {
  readonly enabled: boolean;
  readonly detail: string | null;  // human-readable explanation
}
```

* Fetched from `GET /api/v1/system/safe-mode`.
* Cached via React Query with a moderate `staleTime`.
* Drives:

  * A persistent banner inside the workspace shell.
* Disabling all **run‑invoking** actions (starting new runs, configuration builds, validations, activations that trigger runs).
* Status is **system‑wide**; the toggle lives on a system‑level Settings screen that only appears for users with `System.SafeMode.*`.

---

## 3. Initial setup and authentication flows

### 3.1 First‑run setup

On first deployment, ADE may require a “first admin” to be created.

The entry strategy:

1. Call `GET /api/v1/setup/status`.
2. If `requires_setup == true`:

   * Navigate to `/setup`.
   * Render the first‑admin setup screen.
3. Otherwise:

   * Proceed to normal login/session checks.

The setup screen:

* Collects the first admin’s information (e.g. name, email, password).
* Calls `POST /api/v1/setup` to create the user and initial session.
* On success, redirects to:

  * The workspace directory (`/workspaces`), or
  * A validated `redirectTo` path, if present.

Setup endpoints are public but should be callable only while `requires_setup == true`. After setup, this flag becomes false and the `/setup` path should redirect to `/login` or `/workspaces`.

### 3.2 Email/password login

Email/password authentication uses:

* `POST /api/v1/auth/session` – create a session.
* `DELETE /api/v1/auth/session` – terminate the current session.
* `POST /api/v1/auth/session/refresh` – optional session refresh.

Flow:

1. On `/login`, render the login form.
2. On submit:

   * Call `createSession({ email, password })`.
   * On success:

     * Invalidate and refetch the `session` and `effectivePermissions` queries.
     * Redirect to `redirectTo` (if safe) or to the default route.
3. On invalid credentials:

   * Show an inline form error.
4. On other errors:

   * Show a generic error and keep the user on `/login`.

Logout:

* Initiated via “Sign out” in the profile menu.
* Calls `DELETE /api/v1/auth/session`.
* Clears the React Query cache and navigates to `/login`.

At no point are credentials or tokens written to `localStorage`.

### 3.3 SSO login

When SSO is enabled, providers are listed via:

* `GET /api/v1/auth/providers`.

SSO flow:

1. `/login` renders buttons for each provider.
2. Clicking a provider navigates to `GET /api/v1/auth/sso/login?provider=<id>&redirectTo=<path>`:

   * Backend responds with a redirect to the IdP.
3. After IdP authentication, the user is redirected to `GET /api/v1/auth/sso/callback`.
4. Backend verifies the callback, establishes a session, and then redirects to the ADE Web app (e.g. `/auth/callback`).

The `/auth/callback` screen:

* Optionally shows a “Signing you in…” loading state.
* Refetches the `session` and `effectivePermissions` queries.
* Redirects just like email/password login:

  * To a validated `redirectTo`, or
  * To the default route.

### 3.4 Redirect handling

`redirectTo` is used to send the user back to where they were going, for example:

* After login,
* After SSO callback,
* After first‑run setup.

Redirect safety rules:

* Accept only **relative paths**, e.g. `/workspaces/123/runs`.
* Reject any string that:

  * Contains a scheme (`://`),
  * Starts with `//`,
  * Resolves outside the current origin,
  * Starts with suspicious prefixes (`javascript:`, etc).

We centralise this logic in a helper, e.g.:

```ts
function resolveRedirectPath(raw?: string | null): string;
```

If validation fails or `redirectTo` is omitted:

* Fallback to:

  * The user’s default workspace (if `Session.defaultWorkspaceId` is set), or
  * The workspace directory (`/workspaces`).

---

## 4. Session lifecycle and caching

### 4.1 Fetching the session

On app startup and after any login/logout, ADE Web fetches the session:

* `GET /api/v1/auth/session` (or equivalent).

`useSessionQuery()`:

* Wraps the React Query call.
* Treats `401` as “no active session”; `403` is propagated so screens can render a permissions experience (see §4.4).

Behaviour:

* If the user navigates to an authenticated route and `useSessionQuery()` resolves as unauthenticated:

  * Redirect them to `/login` with an optional `redirectTo` back to the original path.

### 4.2 Refreshing the session

If the backend offers `POST /api/v1/auth/session/refresh`, it can be used to:

* Extend session lifetime without forcing the user back to `/login`.

The frontend should:

* Avoid implementing custom token logic.
* Trigger a refresh only when the backend’s contract requires it (e.g. via a small helper hook that calls refresh on certain error codes, then retries the failed request).

The exact refresh policy is backend‑driven; the frontend’s run is to re‑read `Session` and `EffectivePermissions` whenever the backend indicates that the session has changed.

### 4.3 Global vs workspace‑local data

We intentionally separate:

* **Global identity & permissions** (from `Session` and `EffectivePermissions`),
* **Workspace‑local context** (from workspace endpoints).

Workspace context comes from:

* `GET /api/v1/workspaces/{workspace_id}` – workspace metadata and membership summary.
* `GET /api/v1/workspaces/{workspace_id}/members` – detailed list of members and roles.
* `GET /api/v1/workspaces/{workspace_id}/roles` – workspace role definitions.

The UI uses:

* Session + membership summaries for top‑level decisions (what workspaces to show).
* Workspace‑specific endpoints for detailed management screens.

### 4.4 HTTP status semantics

Frontends treat auth‑related status codes consistently:

* `401` → **not logged in**. Redirect to `/login` (preserving a safe `redirectTo` where appropriate).
* `403` → **logged in but not allowed**. Keep the user on the current screen and surface a permissions experience (hide or disable actions with explanatory copy).

---

## 5. RBAC model and permission checks

### 5.1 Permission keys

Permissions are represented as strings and follow a descriptive pattern:

* `<Scope>.<Area>.<Action>`

Examples:

* `Workspaces.Create`
* `Workspace.Runs.Read` – view runs in a workspace.
* `Workspace.Runs.Run` – start new runs.
* `Workspace.Settings.Read`
* `Workspace.Settings.ReadWrite`
* `Workspace.Members.Read`
* `Workspace.Members.ReadWrite`
* `System.SafeMode.Read`
* `System.SafeMode.ReadWrite`

The full catalog is provided by `GET /api/v1/permissions` and is primarily used by the Roles/Permissions UIs.

### 5.2 Global and workspace roles

Roles are defined and assigned via the API; the frontend treats them as named bundles of permissions.

**Global roles**

* Endpoints:

  * `GET /api/v1/roles`
  * `POST /api/v1/roles`
  * `GET /api/v1/roles/{role_id}`
  * `PATCH /api/v1/roles/{role_id}`
  * `DELETE /api/v1/roles/{role_id}`

* Assignments:

  * `GET /api/v1/role-assignments`
  * `POST /api/v1/role-assignments`
  * `DELETE /api/v1/role-assignments/{assignment_id}`

**Workspace roles**

* Endpoints:

  * `GET /api/v1/workspaces/{workspace_id}/roles`
  * `GET /api/v1/workspaces/{workspace_id}/role-assignments`
  * `POST /api/v1/workspaces/{workspace_id}/role-assignments`
  * `DELETE /api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}`

* Membership:

  * `GET /api/v1/workspaces/{workspace_id}/members`
  * `POST /api/v1/workspaces/{workspace_id}/members`
  * `DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}`
  * `PUT /api/v1/workspaces/{workspace_id}/members/{membership_id}/roles`

The **Roles** and **Members** panels in Settings are thin UIs over these endpoints. The core run/document/configuration flows should not depend on the specifics of role assignment; they only consume effective permission keys.

### 5.3 Effective permissions query

We expose a dedicated query for permissions:

```ts
function useEffectivePermissionsQuery(): {
  data?: EffectivePermissions;
  isLoading: boolean;
  error?: unknown;
}
```

Implementation:

* Calls `GET /api/v1/me/permissions`.
* Returns at least:

  ```ts
  {
    global: string[];
    workspaces?: Record<string, string[]>;
  }
  ```

In many cases the global set is sufficient:

* Global actions like creating workspaces or toggling Safe mode are gated by global permissions.
* Workspace actions can either use `workspaces[workspaceId]` or derive workspace permissions from membership if the backend does not include them in `/me/permissions`.

### 5.4 Permission helpers and usage

Helpers in `shared/permissions` make checks uniform:

```ts
export function hasPermission(
  permissions: readonly string[] | undefined,
  key: string,
): boolean {
  return !!permissions?.includes(key);
}

export function hasAnyPermission(
  permissions: readonly string[] | undefined,
  keys: readonly string[],
): boolean {
  return !!permissions && keys.some((k) => permissions.includes(k));
}
```

Workspace helpers:

```ts
export function useWorkspacePermissions(workspaceId: string) {
  const { data: effective } = useEffectivePermissionsQuery();
  const workspacePerms =
    effective?.workspaces?.[workspaceId] ?? ([] as string[]);

  return { permissions: workspacePerms };
}

export function useCanInWorkspace(workspaceId: string, permission: string) {
  const { permissions } = useWorkspacePermissions(workspaceId);
  return hasPermission(permissions, permission);
}
```

Wrap raw permission keys in **domain helpers** to keep feature code declarative:

```ts
export function useCanStartRuns(workspaceId: string) {
  return useCanInWorkspace(workspaceId, "Workspace.Runs.Run");
}

export function useCanManageConfigurations(workspaceId: string) {
  return useCanInWorkspace(workspaceId, "Workspace.Configurations.ReadWrite");
}
```

Typical usage:

* **Navigation construction**

  ```ts
  const canSeeSettings = useCanInWorkspace(workspaceId, "Workspace.Settings.Read");

  const items = [
    { id: "runs", path: "/runs", visible: true },
    { id: "settings", path: "/settings", visible: canSeeSettings },
  ].filter((item) => item.visible);
  ```

* **Action buttons**

  ```tsx
  const canStartRuns = useCanInWorkspace(workspaceId, "Workspace.Runs.Run");

  <Button
    onClick={onStartRun}
    disabled={!canStartRuns || safeModeEnabled}
    title={
      !canStartRuns
        ? "You don't have permission to start runs in this workspace."
        : safeModeEnabled
        ? `Safe mode is enabled: ${safeModeDetail ?? ""}`
        : undefined
    }
  >
    Run
  </Button>;
  ```

### 5.5 Hide vs disable

We use a simple policy:

* **Hide** features that the user should not know exist:

  * Global Admin screens,
  * “Create workspace” action, if they lack `Workspaces.Create`.

* **Disable with explanation** for features the user understands conceptually but cannot execute *right now*:

  * Run buttons for users who can see runs but lack `Workspace.Runs.Run`.
  * Safe mode toggle for users with read but not write access.

Disabled actions should always have a tooltip explaining **why**:

* “You don’t have permission to start runs in this workspace.”
* “Only system administrators can toggle Safe mode.”

---

## 6. Safe mode

Safe mode is a system‑wide switch that stops new engine work from executing (workspace overrides are optional). ADE Web must:

* Reflect its current status to the user.
* Proactively block all run‑invoking actions at the UI layer.

### 6.1 Backend contract

Endpoints:

* `GET /api/v1/system/safe-mode`:

  ```json
  {
    "enabled": true,
    "detail": "Maintenance window – new runs are temporarily disabled."
  }
  ```

* `PUT /api/v1/system/safe-mode`:

  * Permission‑gated (e.g. requires `System.SafeMode.ReadWrite`).
  * Accepts:

    ```json
    {
      "enabled": true,
      "detail": "Reasonable, user-facing explanation."
    }
    ```

### 6.2 Safe mode hook

Frontend exposes:

```ts
function useSafeModeStatus(): {
  data?: SafeModeStatus;
  isLoading: boolean;
  error?: unknown;
  refetch: () => void;
}
```

Implementation details:

* Wraps `GET /api/v1/system/safe-mode` in a React Query query.
* Uses a `staleTime` on the order of tens of seconds (exact value configurable).
* Allows manual refetch (e.g. after toggling Safe mode).

### 6.3 What Safe mode blocks

When Safe mode is enabled (`enabled === true`), ADE Web must block **starting new runs** and any other action that causes the engine to execute.

Examples:

* Starting a new run from:

  * The Documents screen (“Run extraction”),
  * The Runs ledger (“New run”, if present),
  * The Config Builder workbench (“Run extraction” within the editor).

* Starting a **build** of a configuration environment.

* Starting **validate‑only** runs (validation of configurations or manifests).

* Activating/publishing configurations if that triggers background engine work.

UI behaviour:

* All such controls must:

  * Be disabled (not clickable),
  * Show a tooltip like:

    > “Disabled while Safe mode is enabled: Maintenance window – new runs are temporarily disabled.”

The backend may still reject blocked operations; the UI’s run is to make the state obvious and avoid a confusing “click → no‑op” experience.

### 6.4 Safe mode banner

When Safe mode is on:

* Render a **persistent banner** inside the workspace shell:

  * Located just below the global top bar, above section content.
  * Present in all workspace sections (Runs, Documents, Config Builder, Settings, etc.).

* Recommended copy:

  ```text
  Safe mode is enabled. New runs, builds, and validations are temporarily disabled.
  ```

* If `detail` is provided by the backend, append or incorporate it:

  ```text
  Safe mode is enabled: Maintenance window – new runs are temporarily disabled.
  ```

The banner should be informational only; it does not itself contain primary actions.

### 6.5 Toggling Safe mode

Toggling Safe mode is an administrative action performed on a **system‑level Settings screen** (not per‑workspace). The screen is visible only to users with `System.SafeMode.Read`/`System.SafeMode.ReadWrite`.

UI pattern:

* Show current state (`enabled` / `disabled`) and editable `detail` field.

* Require:

  * `System.SafeMode.Read` to view current status.
  * `System.SafeMode.ReadWrite` to change it.

* The toggle workflow:

  1. User edits the switch and/or message.
  2. UI calls `PUT /api/v1/system/safe-mode`.
  3. On success:

     * Refetch Safe mode status.
     * Show a success toast (“Safe mode enabled”/“Safe mode disabled”).
  4. On 403:

     * Show an inline error `Alert` (“You do not have permission to change Safe mode.”).

---

## 7. Security considerations

### 7.1 Redirect safety

Any time `redirectTo` is used (login, SSO, setup), we must:

* Accept only relative URLs (starting with `/`).
* Reject:

  * Absolute URLs (`https://…`),
  * Protocol‑relative URLs (`//…`),
  * `javascript:` or similar schemes.

Safe logic belongs in a single helper (`resolveRedirectPath`) that is used by:

* The login flow.
* The SSO callback screen.
* The setup screen.

If `redirectTo` is unsafe or missing:

* Redirect to `/workspaces` or to the user’s default workspace path.

### 7.2 Storage safety

We **never** store:

* Passwords,
* Tokens,
* Raw session objects,

in `localStorage` or `sessionStorage`.

We **do** store:

* UI preferences such as:

  * Left nav collapsed/expanded,
  * Workbench layout,
  * Editor theme,
  * Per‑document run defaults,

under namespaced keys like:

* `ade.ui.workspace.<workspaceId>.nav.collapsed`
* `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.console`
* `ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences`

All such values are:

* Non‑sensitive,
* Safe to clear at any time,
* Derived from information already visible in URLs or UI.

See `10-ui-components-a11y-and-testing.md` for the full list of persisted preferences.

### 7.3 CSRF and CORS

CSRF and CORS are primarily backend concerns, but ADE Web should:

* Use `credentials: "include"` when the backend uses cookie‑based auth.
* Use the Vite dev server’s `/api` proxy in development to avoid CORS headaches locally.
* Avoid manually setting auth headers unless explicitly required by the backend design.

Cookies should be configured with appropriate `Secure` and `SameSite` attributes; this is out of scope for the frontend but the assumptions should be documented in backend configuration.

---

## 8. Checklist for new features

When adding a feature that touches auth, permissions, or runs:

1. **Define the permission(s)**

   * Which permission key(s) gate the feature?
   * Are they global (`Workspaces.Create`) or workspace‑scoped (`Workspace.Runs.Run`)?

2. **Wire into helpers**

   * Use `hasPermission` / `useCanInWorkspace` instead of checking raw strings in multiple places.
   * Prefer a small domain helper (e.g. `canStartRuns(workspaceId)`).

3. **Respect Safe mode**

  * If the feature starts or schedules new runs or builds, disable it when `SafeModeStatus.enabled === true`.
  * Add an explanatory tooltip mentioning Safe mode.

4. **Handle unauthenticated users**

   * Do not assume `useSessionQuery().data` is always present.
   * Redirect to `/login` when required.

5. **Avoid leaking information**

   * Hide admin‑only sections entirely if the user lacks the relevant read permissions.
   * Disable rather than hide when the existence of the feature is already obvious from the context.

With these patterns, auth, RBAC, and Safe mode remain predictable and easy to extend as ADE evolves.
```

# apps/ade-web/docs/06-workspace-layout-and-sections.md
```markdown
# 06 – Workspace layout and sections

This document describes the **workspace‑level UI layout** in ADE Web:

- The **Workspace directory** (`/workspaces`) – where users discover and select workspaces.
- The **Workspace shell** (`/workspaces/:workspaceId/...`) – the frame around a single workspace.
- The **sections inside a workspace** (Documents, Runs, Configurations / Config Builder, Settings, Overview) and how they plug into the shell.
- Where **banners**, **Safe mode messaging**, and **notifications** appear.

It focuses on **layout and responsibilities**, not API details or low‑level component props.

> Related docs:
> - [`01-domain-model-and-naming.md`](./01-domain-model-and-naming.md) – definitions of Workspace, Document, Run, Configuration, etc.
> - [`03-routing-navigation-and-url-state.md`](./03-routing-navigation-and-url-state.md) – route structure and navigation helpers.
> - [`07-documents-and-runs.md`](./07-documents-and-runs.md) – detailed behaviour of the Documents and Runs sections.
> - [`08-configurations-and-config-builder.md`](./08-configurations-and-config-builder.md) and [`09-workbench-editor-and-scripting.md`](./09-workbench-editor-and-scripting.md) – Config Builder internals.
> - [`10-ui-components-a11y-and-testing.md`](./10-ui-components-a11y-and-testing.md) – UI primitives, accessibility, and keyboard patterns.
>
> Instant understanding: section names, routes, and folders stay in lockstep—`/documents`, `/runs`, `/config-builder`, `/settings` map to `screens/workspace-shell/sections/{documents|runs|config-builder|settings}` and route builders in `@shared/nav/routes`. Section filters reuse the canonical query param helpers described in `docs/07`.

---

## 1. UX layers: directory vs shell

ADE Web has two distinct workspace layers:

1. **Workspace directory**  
   - Route: `/workspaces` (+ `/workspaces/new`).  
   - Shows all workspaces the user can access.  
   - Lets users **select** or **create** workspaces.  
   - Does *not* render the workspace shell.

2. **Workspace shell**  
   - Routes: `/workspaces/:workspaceId/...`.  
   - Wraps all activity **inside a single workspace**.  
   - Provides a stable frame: top bar, left nav, banners.  
   - Hosts section screens: Documents, Runs, Configurations (Config Builder), Settings, Overview.

The rule:

- `/workspaces` → **directory only**.  
- `/workspaces/:workspaceId/...` → **shell + section**.

---

## 2. Global top bar (`GlobalTopBar`)

The **global top bar** is shared between the directory and the shell. It is the horizontal frame that indicates *where you are* and exposes *what you can do next*.

### 2.1 Responsibilities

- Show **context** (directory vs specific workspace).
- Host **primary actions** for the current surface.
- Provide a **search** field (scope depends on view).
- Expose the **profile menu**.
- Provide an anchor for **global banners** directly beneath it.

### 2.2 Layout slots

`GlobalTopBar` is a layout component with named slots:

- `brand` – left‑aligned:
  - Directory: “Workspace directory” + ADE product label.
  - Shell: workspace name + optional environment label.
- `leading` – breadcrumbs or lightweight context.
- `actions` – main buttons (e.g. “Create workspace”, “Upload document”, “Run extraction”).
- `trailing` – profile / user menu (`ProfileDropdown`).
- `secondaryContent` – optional row underneath for filters, breadcrumbs, tabs.

The top bar may contain a `GlobalSearchField` in its main row.

### 2.3 Behaviour per layer

- **Directory (`/workspaces`)**
  - `brand`: static label + product name.
  - `actions`: “Create workspace” if user has permission.
  - `secondaryContent`: may hold workspace search and guidance text.
  - Search: filters workspace cards (name/slug); bound to `⌘K` / `Ctrl+K`.

- **Workspace shell (`/workspaces/:workspaceId/...`)**
  - `brand`: workspace name + environment label (e.g. `Acme · Production`).
  - `leading`: optional section name or breadcrumbs.
  - `actions`: section‑specific actions (e.g. “Upload document”, “Run extraction”, “New configuration”).
  - `trailing`: `ProfileDropdown`.
  - `secondaryContent`: often used for section filters or tabs.
  - Search: workspace‑scoped, usually **section‑aware**:
    - Documents: filters documents.
    - Runs: filters runs.
    - Other sections: workspace‑wide search surface.

From a layout standpoint, the top bar’s **height and structure** are stable; only the slot content changes between screens.

---

## 3. Workspace directory (`/workspaces`)

The Workspace directory is the first stop after sign‑in for most users.

### 3.1 Responsibilities

- List workspaces the user has access to.
- Provide search / quick jump to a workspace.
- Allow workspace creation (if the user has permission).
- Offer light guidance on how to structure workspaces.

### 3.2 Layout & structure

The directory screen is typically structured as:

- **GlobalTopBar** configured for “directory”.
- **Main content**:
  - Header section with title and brief description.
  - Workspace search field.
  - Workspace list (cards) or an empty‑state panel.
  - Optional right‑hand guidance column.

On small viewports, the right‑hand guidance collapses below or is omitted; the list remains the focus.

### 3.3 Workspace search

- Implemented via `GlobalSearchField` configured for workspaces.
- Behaviours:
  - Filters workspace cards by **name** and **slug**.
  - `⌘K` / `Ctrl+K` focuses the search when the directory is active.
  - Pressing Enter with a clearly best match may jump directly to that workspace.

Search is **purely client‑side** over the current list in typical deployments, but nothing in the layout assumes that.

### 3.4 Actions and permissions

- “Create workspace” appears only if the user has the relevant permission (e.g. `Workspaces.Create`).
- If the user lacks this permission and has no workspaces:
  - The screen explains that they must be **invited**.
  - Suggest linking to admin contact or documentation if available.

### 3.5 Empty and loading states

Common states:

- **Loading**: skeleton workspace cards and disabled actions while queries are in flight.
- **No workspaces & can create**:
  - Headline: “You don’t have any workspaces yet.”
  - Description: short explanation of what workspaces are for.
  - Primary CTA: “Create your first workspace”.
- **No workspaces & cannot create**:
  - Headline: “You’re not a member of any workspaces yet.”
  - Body: “Ask an administrator to invite you.”

### 3.6 Workspace cards

Each workspace is represented by a card that includes:

- Name.
- Slug or human‑friendly short ID.
- Optional **environment label** (e.g. Production, Staging).
- Optional indication that this is the user’s **default workspace**.
- Compact summary of the user’s roles/permissions (e.g. “Owner”, “Editor”).

Clicking a card:

- Navigates to `/workspaces/:workspaceId/documents` (or another chosen default section) inside the **Workspace shell**.

The optional right‑hand panel can include:

- Examples of workspace organisation (per client, per environment, etc.).
- A short checklist for new deployments (invite admins, configure roles, set default workspace).

---

## 4. Workspace shell (`/workspaces/:workspaceId/...`)

The Workspace shell renders everything inside a single workspace. It owns the frame; sections own their content.

### 4.1 Responsibilities

- Load and expose **workspace context**:
  - Name, slug, environment label.
  - Membership and permissions.
  - Safe mode status (via shared query).
- Render stable **shell chrome**:
  - Left navigation (section switcher).
  - Workspace‑specific top bar.
  - Banner strip (Safe mode, connectivity).
- Host **section screens** inside the main content area.
- Handle shell‑level loading/error states (e.g. workspace not found).

The shell is implemented by a dedicated screen component, e.g. `WorkspaceShellScreen`.

### 4.2 Route boundary

All routes under `/workspaces/:workspaceId` are expected to be rendered inside the shell. Examples:

- `/workspaces/:workspaceId/documents`
- `/workspaces/:workspaceId/runs`
- `/workspaces/:workspaceId/config-builder`
- `/workspaces/:workspaceId/settings`
- `/workspaces/:workspaceId/overview` (optional)

The shell:

- Fetches workspace metadata once.
- Renders a **workspace‑level error state** if the workspace cannot be loaded (e.g. 404, permission denied).
- Then resolves the section based on the first path segment after `:workspaceId`.

If a user visits `/workspaces/:workspaceId` with **no section segment**, the shell immediately redirects to the configured default section (currently **Documents**). The default lives alongside the route helpers (e.g. `shared/nav/routes.ts`) and is consumed by `WorkspaceShellScreen`.

### 4.3 Layout regions (desktop)

Conceptually, the shell layout on desktop is:

- **Top bar** – `GlobalTopBar` in “workspace” mode.
- **Banner strip** – cross‑cutting banners (Safe mode, connectivity).
- **Body**:

  - Left: `WorkspaceNav` (vertical).
  - Right: `WorkspaceContent` (section content).

- **Overlay layer** – modals, maximised workbench, mobile nav, toasts.

Sections render only inside `WorkspaceContent`. They must not duplicate the top bar or left nav.

---

## 5. Left navigation (desktop)

The left nav is the primary way to navigate between sections within a workspace.

### 5.1 Contents and ordering

Typical ordering:

1. **Workspace identity**
   - Avatar/initials computed from workspace name.
   - Workspace name.
   - Environment label if present.
   - “Switch workspace” action (e.g. link back to `/workspaces` or a quick switcher dialog).

2. **Section links**
   - Documents.
   - Runs.
   - Configurations (Config Builder).
   - Settings.
   - Overview (if enabled).

Section links use `NavLink` so they reflect active state based on the current path.

### 5.2 Behaviour & permissions

- **Active styling** is derived from the current path segment; for example, `/workspaces/:workspaceId/runs/...` marks the Runs item active.
- **Permissions** determine what appears:
  - Some sections may be completely hidden if the user cannot view them.
  - Alternatively, a section can be visible but disabled with a tooltip explaining the missing permission.

The shell decides the hiding strategy; individual sections should not second‑guess it.

### 5.3 Collapse and persistence

On larger screens, the nav can be collapsed to icon‑only mode:

- When collapsed:

  - Icons remain visible.
  - Workspace name and section labels are hidden or reduced.

- Collapse state is persisted **per workspace** with a key such as:

  - `ade.ui.workspace.<workspaceId>.nav.collapsed`

Rules:

- Default = expanded.
- Manual user choice should be honoured on subsequent visits.
- Auto‑collapse on very narrow viewports is allowed but should be treated as separate from the stored preference.

---

## 6. Mobile navigation

On smaller viewports, the left nav is presented as a **slide‑in drawer**.

### 6.1 Trigger and layout

- A menu button (usually in the top bar) opens the workspace nav.
- The nav slides in from the left and covers or pushes the content.
- A semi‑transparent background overlay (scrim) appears behind the nav.

### 6.2 Behaviour and closing rules

When the nav is open:

- **Body scroll is locked** so the background content does not scroll.
- Focus is moved into the nav and should remain there until the nav closes.

The nav closes when:

- A section link is selected.
- The user taps on the scrim outside the nav.
- The user presses the Escape key.
- The user activates an explicit close button (if present).

These behaviours keep mobile navigation predictable and prevent layout jitter when switching sections.

---

## 7. Workspace sections (overview)

Each section is a dedicated screen inside the shell’s main content area. This section defines their **responsibilities and relationships** to the shell; detailed workflows live in other docs.

### 7.1 Documents

- **Route:** `/workspaces/:workspaceId/documents`  
- **Screen:** `DocumentsScreen`  
- **Persona:** analysts/operators.

Responsibilities:

- List and filter documents in the workspace.
- Provide upload capabilities.
- Show each document’s status and **last run** summary.
- Offer actions such as “Run extraction”, “Download source file”, “Delete/archive”.

Shell integration:

- Top bar `actions` typically include “Upload document”.
- `GlobalSearchField` filters visible documents by name and additional criteria.
- Section banners (e.g. validation warnings) appear below the shell’s banner strip.

Detailed behaviour is in [`07-documents-and-runs.md`](./07-documents-and-runs.md).

### 7.2 Runs

- **Route:** `/workspaces/:workspaceId/runs`  
- **Screen:** `RunsScreen`  
- **Persona:** analysts/operators/engineers.

Responsibilities:

- Show a **workspace‑wide ledger of runs**.
- Allow filtering by status, configuration, initiator, date range, and possibly document.
- Provide links to:
  - Run detail view.
  - Logs and telemetry (via NDJSON streams).
  - Output artifacts and individual output files.

Shell integration:

- Top bar `leading` may display “Runs” with time range or filter summary.
- Top bar `actions` are often empty; run creation usually starts from Documents or Configurations/Config Builder.
- `GlobalSearchField` can search by run id, document name, or initiator depending on configuration.

Detailed behaviour is in [`07-documents-and-runs.md`](./07-documents-and-runs.md).

### 7.3 Config Builder

- **Route:** `/workspaces/:workspaceId/config-builder`  
- **Screen:** `ConfigBuilderScreen`  
- **Persona:** workspace owners/engineers.

Responsibilities:

- Show configurations available in the workspace.
- Provide actions: create/clone/export configurations, activate/deactivate versions.
- Host the **Config Builder workbench** for editing configuration code and manifest.
- Manage the “return path” so users can exit the workbench back to where they came from.

Naming stays consistent: the nav label is **Config Builder**, the route segment is `/workspaces/:workspaceId/config-builder`, and the feature folder is `features/workspace-shell/sections/config-builder` (hosting the Config Builder workbench). The section always includes both the configurations list and the workbench editing surface.

Shell integration:

- Top bar `actions` may include “New configuration”.
- Workbench can be **embedded** or **maximised** (immersive); see §9.

Details:

- Configuration list: [`08-configurations-and-config-builder.md`](./08-configurations-and-config-builder.md).
- Workbench/editor: [`09-workbench-editor-and-scripting.md`](./09-workbench-editor-and-scripting.md).

### 7.4 Settings

- **Route:** `/workspaces/:workspaceId/settings`  
- **Screen:** `WorkspaceSettingsScreen`  
- **Persona:** workspace admins/owners.

Responsibilities:

- Manage workspace metadata (name, slug, environment label).
- Manage members and workspace‑scoped roles.
- Optionally surface Safe mode **status** with a link to the system‑level Settings screen where it is toggled (requires `System.SafeMode.*`).

Shell integration:

- Often uses `secondaryContent` in the top bar to place tab controls (e.g. General, Members, Roles).
- Section content is tabbed and controlled by a `view` query parameter.

RBAC and Safe mode are described in [`05-auth-session-rbac-and-safe-mode.md`](./05-auth-session-rbac-and-safe-mode.md).

### 7.5 Overview (optional)

- **Route:** `/workspaces/:workspaceId/overview`  
- **Screen:** `WorkspaceOverviewScreen` (if implemented).

Responsibilities:

- Provide a **summary** surface for the workspace:
  - Recent runs.
  - Documents that need attention.
  - Current configuration status.
  - Safe mode state.

Shell integration:

- Typically appears as the first item in the nav or clearly marked as “Home”.
- Primarily read‑only; actions are delegated to other sections.

---

## 8. Banners and notifications

The shell defines **where** banners and notifications appear so sections behave consistently.

### 8.1 Banner strip

Immediately beneath `GlobalTopBar` is a **banner strip** reserved for:

- **Safe mode banner**:
  - Always present when Safe mode is enabled.
  - Contains the human‑readable message from the Safe mode endpoint.
  - Appears on all workspace sections.

- **Other cross‑cutting banners**:
  - Connectivity issues (“Lost connection; retrying…”).
  - Global warnings (e.g. “Using a deprecated configuration version”).

Ordering is:

1. Safe mode (highest priority).
2. Connectivity / critical issues.
3. Informational environment messages.

Section‑local banners (e.g. “Filters could not be applied”) should be rendered **inside the section**, below this strip.

### 8.2 Toast notifications

Toast notifications are transient messages, rendered in a global container (typically top‑right or bottom‑right):

- Used for:
  - Successful actions (saved, uploaded, run started).
  - Minor failures that don’t block the flow.
- Not used for:
  - Long‑lived states or critical errors that require user decisions.

The shell ensures toasts sit **above** content and banners in the z‑order but does not itself decide when to show them; sections and shared hooks trigger them.

---

## 9. Immersive layouts and special cases

Most sections are standard list/detail pages, but some flows use **immersive** layouts that temporarily emphasise content over shell chrome.

### 9.1 Config Builder workbench (immersive mode)

The Config Builder workbench supports window states (see [`09-workbench-editor-and-scripting.md`](./09-workbench-editor-and-scripting.md)):

- **Restored**:
  - Appears embedded in the Config Builder section.
  - Shell (top bar + nav + banners) fully visible.

- **Maximised**:
  - Workbench expands to fill the viewport.
  - Nav and possibly the banner strip may be visually hidden.
  - Top bar may be reduced to a thin chrome or hidden entirely.

- **Docked/minimised**:
  - Workbench is hidden; a dock control allows restoring it.

Layout rules:

- Immersive mode must provide an obvious **“Exit”** control to return to standard layout.
- Even if banners are visually collapsed, Safe mode and other important states should remain one click away.
- Window state is part of presentation; routes remain under `/workspaces/:workspaceId/config-builder`.

### 9.2 Workspace‑local “Section not found”

The shell deliberately owns the “unknown section” experience. If the path segment after `/workspaces/:workspaceId/` does not map to a known section, `WorkspaceShellScreen` renders its **UnknownSection** state *inside the shell* instead of returning the global 404. This keeps the valid workspace context alive so the user can recover by choosing a known section (e.g. “Documents” or “Runs”) without being kicked back to the directory.

---

## 10. Guidelines for new sections

When adding new workspace sections, apply these rules:

1. **Section lives under the shell**  
   - Route: `/workspaces/:workspaceId/<sectionSlug>`.  
   - Nav item in `WorkspaceNav`.  
   - Screen component in `features/workspace-shell/<section>/`.

2. **Use top bar slots rather than custom headers**  
   - `brand` and `leading` communicate where you are.  
   - `actions` hosts your primary call‑to‑action.  
   - `secondaryContent` is the place for section‑level tabs or filters.

3. **Respect banner and toast conventions**  
   - Global banners always sit in the shell’s banner strip.  
   - Section‑local banners go **inside** section content.  
   - Use toasts for short‑lived feedback, not persistent states.

4. **Re‑use list/detail patterns**  
   - For collections: list/table + filter toolbar.  
   - For individual items: detail view, often linked from a list row.

5. **Keep navigation predictable**  
   - Don’t invent new global nav elements; plug into `WorkspaceNav`.  
   - Use `NavLink` so active state follows the URL.

By keeping a clear separation between **shell responsibilities** (context, navigation, banners) and **section responsibilities** (data, workflows), the workspace experience stays predictable and easy to extend, even as we add new run types or features in the future.
```

# apps/ade-web/docs/07-documents-and-runs.md
```markdown
# 07 – Documents and Runs

This document describes how ADE Web models and implements:

- **Documents** – immutable input files inside a workspace.
- **Runs** – executions of the ADE engine against one or more documents.
- The **Documents** and **Runs** sections of the workspace shell.
- **Run options** and **per‑document run preferences**.

It is written for frontend engineers and backend integrators. For canonical terminology (Workspace, Document, Run, Configuration, Safe mode, etc.) see `01-domain-model-and-naming.md`.

> **Terminology note**  
> Backend paths still use `/runs`; in the UI and TS types we refer to the same entity as **Run** with ID field `runId`.

---

## 1. Conceptual model

At a high level:

- A **document** is an immutable input file that belongs to a workspace.
- A **Run** is one execution of ADE against a set of documents using a particular configuration and options.
- ADE Web exposes:
  - A **Documents** section for managing inputs.
  - A **Runs** section for the workspace‑wide run ledger.
  - Run entry points from **Documents** and **Config Builder**.

### 1.1 Relationships

- A **workspace** owns many **documents**.
- A **workspace** owns many **runs**.
- A **Run** references:
  - One workspace.
  - One configuration and version (when applicable).
  - One or more input documents.
  - Optional run‑time options (dry run, validate only, sheet selection, …).

Documents and Runs are **loosely coupled**:

- Documents are immutable and never edited by runs.
- Runs always refer to documents by ID; they do not mutate document content.

### 1.2 Execution terminology

ADE Web distinguishes three related concepts:

- **Build** – prepares or refreshes the environment for a configuration version. Build entities live under `/builds` endpoints and are represented by the `Build` type.
- **Run** – executes the engine against documents, represented by the `Run` type. Runs never mean “build”.
- **Run modes** – view‑model labels derived from run options to disambiguate validation vs test runs.

Canonical run options:

```ts
type RunMode = "normal" | "validation" | "test";

interface RunOptions {
  dryRun?: boolean;
  validateOnly?: boolean;
  inputSheetNames?: string[];
  mode?: RunMode; // view-model convenience derived from the flags above
}
```

- **Validation run** – a run with `validateOnly: true` (and often `mode: "validation"`) that checks configuration correctness without full extraction.
- **Test run** – a run against a sample document, typically with `mode: "test"` and optionally `dryRun: true`.
- Backend payloads use snake_case equivalents: `dry_run`, `validate_only`, `input_sheet_names`. The `mode` helper is UI‑only.

---

## 2. Documents

### 2.1 Data model

Frontend view of a document in lists:

```ts
export interface DocumentSummary {
  id: string;
  workspaceId: string;

  name: string;              // usually original filename
  contentType: string;       // e.g. "application/vnd.ms-excel"
  sizeBytes: number;

  status: DocumentStatus;    // uploaded | processing | processed | failed | archived
  createdAt: string;         // ISO 8601 string
  uploadedBy: UserSummary;

  lastRun?: DocumentLastRunSummary | null;
}

export interface DocumentLastRunSummary {
  runId: string;
  status: RunStatus;
  finishedAt?: string | null;
  message?: string | null;   // optional human‑readable note
}
````

A separate `DocumentDetail` type can extend this if the detail endpoint returns more metadata.

**Immutability:**

* Uploading a revised version produces a **new** `document.id`.
* All run APIs use document IDs; they never modify the underlying file.

### 2.2 Status lifecycle

`DocumentStatus` is defined centrally; ADE Web does not derive it from runs. The canonical union lives in `@schema/document`; import it instead of re‑declaring per feature.

Conceptually:

* `uploaded` – file is stored, no run yet.
* `processing` – at least one active run includes this document.
* `processed` – the last relevant run succeeded.
* `failed` – the last relevant run failed.
* `archived` – document is retained for history but excluded from normal interactions.

Typical transitions:

* `null` → `uploaded` when upload completes.
* `uploaded | processed | failed` → `processing` when a run starts.
* `processing` → `processed` on successful completion.
* `processing` → `failed` on error.
* Any → `archived` via explicit user action.

The UI:

* Displays `status` as a badge in the Documents list.
* Shows `lastRun` as a secondary indicator (“Last run: succeeded 2 hours ago”).
* Only changes status by refetching from the backend.

---

## 3. Documents screen architecture

**Route:** `/workspaces/:workspaceId/documents`
**Responsibilities:**

1. List and filter documents in the workspace.
2. Provide upload and download actions.
3. Provide “Run extraction” entry points.
4. Surface last run status and key metadata.

### 3.1 Data sources and hooks

Typical hooks used by `DocumentsScreen`:

```ts
const [searchParams, setSearchParams] = useSearchParams();
const filters = parseDocumentFilters(searchParams);

const documentsQuery = useDocumentsQuery(workspaceId, filters);
const uploadMutation = useUploadDocumentMutation(workspaceId);
```

* `useDocumentsQuery` → `GET /api/v1/workspaces/{workspace_id}/documents`
* `useUploadDocumentMutation` → `POST /api/v1/workspaces/{workspace_id}/documents`
* `useDocumentSheetsQuery` (lazy) → `GET /documents/{document_id}/sheets`

These hooks live in the Documents feature folder and delegate HTTP details to `shared` API modules.

### 3.2 Filters, search, and sorting

Documents URL state is encoded via query parameters:

* `q` – free‑text search (by name, possibly other fields).

* `status` – comma‑separated list of document statuses.

* `sort` – sort key, e.g.:

  * `-created_at` (newest first)
  * `-last_run_at` (recent runs first)

* `view` – optional preset (e.g. `all`, `mine`, `attention`, `recent`).

Rules:

* Filter changes are reflected in the URL using `setSearchParams`.
* For small, frequent adjustments (toggling a status pill), we call `setSearchParams` with `{ replace: true }` to avoid polluting history.
* These parameter names are canonical for Documents; add or change keys via the filter helpers (`parseDocumentFilters` / `buildDocumentSearchParams`) so deep links stay consistent across screens and docs.

### 3.3 Upload flow

User flow:

1. User clicks “Upload documents” or presses `⌘U` / `Ctrl+U`.
2. A file picker opens (or a drag‑and‑drop zone is available).
3. For each selected file, `uploadMutation.mutate({ file })` is called.
4. During upload:

   * Show progress (if easily available).
   * Disable duplicate submissions of the same file selection.
5. On success:

   * Show a success toast (“Uploaded 3 documents”).
   * Invalidate the documents query to refresh the list.
6. On failure:

   * Show an error toast and/or inline `Alert` with backend error text.

Implementation guidelines:

* Keep upload UX optimistic but let the documents query be the source of truth for final status.
* Handle duplicate file names gracefully; they are not required to be unique.

### 3.4 Row actions

Each `DocumentRow` typically exposes:

* **Download** – invokes `GET /documents/{document_id}/download`.
* **Run extraction** – opens the run dialog (section 8).
* **Archive/Delete** – invokes `DELETE /documents/{document_id}` (usually soft delete).

Run‑related actions must be:

* **Permission‑gated** – hidden/disabled if the user cannot start runs.
* **Safe‑mode‑aware** – disabled with a clear tooltip when Safe mode is enabled.

---

## 4. Document sheets

For multi‑sheet spreadsheets, the user can choose which worksheets to process.

### 4.1 API contract

Endpoint:

```text
GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets
```

Expected shape:

```ts
export interface DocumentSheet {
  name: string;
  index: number;
  isActive?: boolean;  // optional “active”/default sheet signal
}
```

Errors and unsupported types:

* If the backend can’t list sheets (unsupported format, parse failure, etc.), it may return an error or an empty list.
* The frontend must gracefully fall back to a “use all sheets” mode.

### 4.2 Use in run dialogs

`useDocumentSheetsQuery(workspaceId, documentId)` is called:

* Lazily when a run dialog opens **and** the document looks like a spreadsheet.
* Or on demand when the user expands a “Sheets” section.

UI behaviour:

* If sheets are returned:

  * Show a multi‑select checklist of worksheet names.
  * Default selection:

    * All sheets, or
    * Only `isActive` sheets if the backend provides that signal.

* If sheets cannot be loaded:

  * Show a small inline warning (“Couldn’t load worksheets; running on all sheets.”).
  * Omit `inputSheetNames` from the run request.

Selected sheet names are passed to the run API as `input_sheet_names`.

---

## 5. Runs

A **Run** is one execution of the ADE engine. ADE Web exposes two main perspectives on Runs:

* The **Runs** ledger – workspace‑wide history (`/workspaces/:workspaceId/runs`, REST plural `/runs`).
* **Configuration‑scoped runs** – initiated from Config Builder against a specific configuration.

### 5.1 Run data model

Workspace‑level run summary:

```ts
export interface RunSummary {
  runId: string;
  workspaceId: string;
  status: RunStatus;        // queued | running | succeeded | failed | cancelled

  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;

  initiatedBy: UserSummary | "system";

  configurationId?: string | null;
  configurationVersionId?: string | null;

  inputDocuments: {
    count: number;
    examples: Array<{ id: string; name: string }>;
  };

  options?: RunOptions;
  message?: string | null;
}

type RunMode = "normal" | "validation" | "test";

export interface RunOptions {
  dryRun?: boolean;
  validateOnly?: boolean;
  inputSheetNames?: string[];
  mode?: RunMode; // View-model convenience; API payload uses snake_case flags
}
```

A `RunDetail` type extends this with:

* Full document list.
* Links to outputs (artifact + individual files).
* Optional telemetry summary.
* Log/console linkage.

### 5.2 Run status

`RunStatus` values:

* `queued` – accepted, waiting to start.
* `running` – currently executing.
* `succeeded` – completed successfully.
* `failed` – completed with error.
* `cancelled` – terminated early by user/system.

The canonical `RunStatus` union lives in `@schema/run`; reuse it instead of introducing feature‑local enums.

Status semantics are the same whether the run came from:

* Documents screen.
* Runs screen.
* Config Builder (test runs).

ADE Web never infers status; it shows what the backend reports. Regardless of which endpoint created it (`/workspaces/{workspace_id}/runs` or `/configurations/{configuration_id}/runs`), each run is persisted into the workspace ledger and accessible by `runId` via `/runs/{run_id}`.

---

## 6. Runs ledger screen

Conceptually: **Runs** is the workspace‑wide ledger of engine activity.

**Route:** `/workspaces/:workspaceId/runs`
**Responsibilities:**

1. Show all runs in a workspace.
2. Allow filtering/sorting by status, configurationId, initiator, and time.
3. Provide access to logs, telemetry, and outputs.

### 6.1 Data and filters

Hook:

```ts
const filters = parseRunFilters(searchParams);
const runsQuery = useRunsQuery(workspaceId, filters);
// internally calls GET /api/v1/workspaces/{workspace_id}/runs
```

Typical filters encoded in the URL:

* `status` – comma‑separated `RunStatus` values.
* `configurationId` – configuration id or version.
* `initiator` – user id or `system`.
* `from`, `to` – created‑at time window.

`parseRunFilters` / `buildRunSearchParams` own these query keys; add new filters there so links, docs, and components stay aligned.

### 6.2 Run list UI

Each row shows:

* Run ID (short display form).
* Status badge.
* Configuration name/version (if present).
* Input document summary (“3 documents”, with tooltip listing examples).
* Initiator.
* Created time and duration.

Row interaction:

* Clicking a row opens a **Run detail** view, either:

  * As its own route: `/workspaces/:workspaceId/runs/:runId`, or
  * As a side panel/dialog anchored on the list.

### 6.3 Run detail and logs

Run detail view composes:

* **Header:**

  * Run ID, status, configuration, initiator.
  * Timestamps and duration.

* **Logs/console:**

  * Either the run event stream (NDJSON) or a loaded log file.
  * Rendered similarly to the Config Builder console.

* **Telemetry summary:**

  * Rows processed, warnings, errors, per‑table counts, etc. (when available).

* **Outputs:**

  * Link to combined artifact download.
  * Table of individual output files.

Data sources:

* `useRunQuery(workspaceId, runId)` → `GET /runs/{run_id}`.
* `useRunOutputsQuery(workspaceId, runId)` → `/runs/{run_id}/outputs`.
* `useRunLogsStream(runId)`:

  * Connects to `/runs/{run_id}/logs`.
  * Parses NDJSON events.
  * Updates console output incrementally.

While a run is `queued` or `running`:

* The detail view holds an active log stream.
* The Runs ledger may poll or simply rely on detail views to trigger refreshes.

### 6.4 “Run again” semantics

Runs are append‑only. A “Run again” affordance in the ledger always **creates a new run** that reuses the prior run’s context by default:

- **Configuration version** – same version as the source run unless the user picks another.
- **Document set** – the same input documents as the source run.
- **RunOptions** – copied (dryRun, validateOnly, sheet selection) unless explicitly overridden.

This mirrors the per‑run preference pattern used in document‑scoped run dialogs: defaults are helpful hints, not authoritative configuration.

---

## 7. Starting runs

Users can start new runs from multiple surfaces:

* **Documents** section: “Run extraction” for a specific document.
* **Runs** section: “New run” (if you support multi‑document runs).
* **Config Builder**: “Run extraction” against a sample document (configuration‑scoped).

### 7.1 Run options in the UI

ADE Web exposes run options via the `RunOptions` shape (camelCase in the UI, converted to snake_case for the API):

* **Dry run**

  * Label: “Dry run (don’t write outputs)”.
  * Intended for testing.

* **Validate only**

  * Label: “Run validators only”.
  * Skip full extraction; sets `validateOnly: true` and usually `mode: "validation"`.

* **Sheet selection**

  * Label and UI: “Worksheets”.
  * Uses sheet metadata described in section 4.

* **Mode (optional view‑model helper)**

  * UI helper derived from the flags above (`"normal" | "validation" | "test"`).
  * Not required by the backend but clarifies intent in components and tests.

General rules:

* Options live under an “Advanced settings” expander in run dialogs.
* Defaults are product decisions and may be remembered per document (see next section).

### 7.2 Workspace‑level run creation (Documents & Runs)

From the **Documents** screen:

1. User clicks “Run extraction” on a document row.

2. ADE Web opens `RunDocumentDialog` with:

   * Selected document prefilled.
   * Preferred configuration/version and sheet subset loaded from per‑document preferences (if any).

3. On submit:

   * ADE Web calls `POST /api/v1/workspaces/{workspace_id}/runs` (REST plural for Runs).
   * Payload includes:

     * `input_document_ids: [documentId]`
     * Optional `input_sheet_names`
     * Optional run options mapped from `RunOptions` to snake_case (`dry_run`, `validate_only`)
     * Selected configuration/version identifiers.

4. On success:

   * Show a success toast.
   * Optionally navigate to the Run detail view.
   * Invalidate runs and documents queries.

From the **Runs** screen:

* A “New run” action could open a similar dialog allowing multiple documents to be selected.

### 7.3 Configuration‑scoped runs (Config Builder)

Config Builder uses **configuration‑scoped runs** primarily for **validation runs** and **test runs**:

* `POST /api/v1/configurations/{configuration_id}/runs` with a similar payload.
* Response provides a `run_id`.
* ADE Web streams that run’s events into the workbench console via `/api/v1/runs/{run_id}/logs`.

The semantics (status, options, outputs) are identical; only the entry point and visual context differ. Full details live in `09-workbench-editor-and-scripting.md`.

---

## 8. Per‑document run preferences

To make repeated runs smoother, ADE Web remembers per‑document, per‑workspace, per‑user preferences.

### 8.1 What is persisted

For each `(workspaceId, documentId, user)` we may store:

```ts
export interface DocumentRunPreferences {
  configurationId?: string;
  configurationVersionId?: string;
  inputSheetNames?: string[];
  options?: Pick<RunOptions, "dryRun" | "validateOnly">;
  version: 1;
}
```

Fields are optional; missing fields fall back to sensible defaults.

### 8.2 Storage and keying

Preferences live in browser `localStorage` via a shared helper, not direct calls from components.

Key pattern:

```text
ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences
```

Invariants:

* **Per‑user** and **per‑workspace** (keys include `workspaceId`).
* Never contain secrets; safe to clear.
* Backend remains the source of truth for configuration availability.

### 8.3 Read/write strategy

**Reading on dialog open:**

* When a run dialog opens for a document:

  1. Load preferences with `getDocumentRunPreferences(workspaceId, documentId)`.
  2. Check that referenced configuration/version still exists:

     * If not, drop those fields from the loaded preferences.
  3. Use the remaining fields to pre‑fill configuration, version, sheet selection, and advanced options.

**Writing on successful submit:**

* After a run is successfully submitted from the Documents screen:

  * Merge the final dialog choices into `DocumentRunPreferences`.
  * Save using `setDocumentRunPreferences(...)`.

**Reset:**

* Run dialog may expose “Reset to defaults”, which:

  * Clears the `run-preferences` entry for that document.
  * Reverts to system defaults on next open.

Implementation detail:

* All logic should live in a small module (e.g. `shared/runPreferences.ts`) and a feature hook (`useDocumentRunPreferences`), so changing key patterns or versioning is centralised.

---

## 9. Backend contracts (summary)

The Documents and Runs features depend on the following backend endpoints. Detailed typings and error semantics are documented in `04-data-layer-and-backend-contracts.md`.

### 9.1 Documents

* `GET /api/v1/workspaces/{workspace_id}/documents`
  List documents (supports `q`, `status`, `sort`, `view`).

* `POST /api/v1/workspaces/{workspace_id}/documents`
  Upload a document.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}`
  Retrieve document metadata.

* `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`
  Soft delete / archive.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/download`
  Download original file.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`
  List worksheets (optional, spreadsheet only).

### 9.2 Workspace runs (ledger)

* `GET /api/v1/workspaces/{workspace_id}/runs`
  List runs for the workspace (filters by status, configurationId, initiator, date).

* `POST /api/v1/workspaces/{workspace_id}/runs`
  Start a new workspace run (used by Documents / Runs).

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}`
  Run detail.

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}/artifact`
  Download combined outputs.

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}/outputs`
  List individual output files.

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}/outputs/{output_path}`
  Download a single output.

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}/logs`
  Run event stream (NDJSON preferred; log file acceptable fallback).

### 9.3 Configuration‑scoped runs

Used by Config Builder:

* `POST /api/v1/configurations/{configuration_id}/runs`
  Start a configuration‑scoped run.

* `GET /api/v1/runs/{run_id}`
  Run detail.

* `GET /api/v1/runs/{run_id}/artifact` (if provided).

* `GET /api/v1/runs/{run_id}/outputs` + `/outputs/{output_path}`.

* `GET /api/v1/runs/{run_id}/logs`
  NDJSON event stream.

All run endpoints should share consistent `RunStatus` values and event semantics.

---

## 10. Safe mode interactions

Safe mode (see `05-auth-session-rbac-and-safe-mode.md`) acts as a kill switch for engine execution.

In the context of Documents and Runs:

* When **Safe mode is enabled**:

  * Run dialogs cannot submit.
  * “Run extraction” buttons are disabled.
  * Any “New run” actions are disabled.
* Read‑only operations still work:

  * Listing documents and runs.
  * Viewing run details.
  * Downloading artifacts, outputs, and logs.

UI behaviour:

* A workspace‑level Safe mode banner is shown inside the shell.
* Disabled controls show a tooltip such as:

  > “Safe mode is enabled: <backend message>”

Server‑side checks remain authoritative; UI disabling is a convenience to avoid surprises.

---

## 11. Design invariants

To keep this surface easy to reason about (for humans and AI agents), we rely on a few invariants:

1. **Documents show backend status.**
   ADE Web never infers document status from run history; it merely displays what the backend reports.

2. **Run semantics are consistent everywhere.**
   Status values, `RunOptions` fields (`dryRun`, `validateOnly`, `inputSheetNames`, `mode`), and timestamps mean the same thing in:

   * Documents last‑run summaries,
   * Runs ledger,
   * Config‑scoped runs.

3. **Runs are append‑only.**
   Runs are created, progress, and complete; they are not edited after creation. “Run again” always creates a new run using the same configuration version, document set, and RunOptions unless the user explicitly overrides them.

4. **Per‑document run preferences are hints, not configuration.**
   They influence UI defaults only. If configurations disappear or change, preferences are safely ignored.

5. **Safe mode always wins.**
   If Safe mode is on, the UI never attempts to create new runs, and the backend enforces that rule.

With these invariants respected, the Documents and Runs features remain predictable and easy to extend, and the mapping between frontend behaviour and backend APIs stays clear.
```

# apps/ade-web/docs/08-configurations-and-config-builder.md
```markdown
# 08 – Configurations and Config Builder

This document explains how **configurations** work in ADE Web and how the
**Config Builder** section is structured.

It focuses on:

- The **Configuration** domain model and version lifecycle.
- The **Configurations** workspace section (Config Builder)  
  (`/workspaces/:workspaceId/config-builder`).
- How configuration metadata (including the manifest) flows between frontend and
  backend.
- How environment builds, validation runs, and test runs are represented in the
  UI.
- How we enter and exit the **Config Builder workbench** (the editing surface
  described in `09-workbench-editor-and-scripting.md`).

Definitions for terms like *Configuration*, *Config version*, *Draft*, *Active*,
*Inactive*, and *Run* are established in
`01-domain-model-and-naming.md`. This doc assumes that vocabulary.

Naming: the **Config Builder** is the workspace section that lists configurations and launches editing. The **Config Builder workbench** is the dedicated window for editing a single configuration version. Use “Config Builder workbench” on first mention and “workbench” afterwards; use “editor” only for the Monaco instance inside that window.

---

## 1. Scope and mental model

From ADE Web’s perspective:

- A **Configuration** is a *workspace‑scoped* unit backed by a **configuration
  package** (Python package + manifest + supporting files).
- Each Configuration has **multiple versions** over time (drafts and immutable
  snapshots).
- The **Configurations** section (home of the Config Builder) is where users:
  - View and manage configurations for a workspace.
  - Inspect version history and status.
  - Open a specific configuration version in the **workbench** to edit code,
    build the environment, run validation runs, and perform test runs.

Backend implementations may have more nuanced state machines, but ADE Web
presents a **simple, stable model**:

- Configuration (high‑level object)
- Configuration version (Draft / Active / Inactive)

Runs themselves are described in `07-documents-and-runs.md`. This doc focuses
on how configurations feed into those runs.

---

## 2. Configuration domain model

### 2.1 Configuration

A **Configuration** is the primary row in the Config Builder list.

Conceptually:

- **Scope**
  - Belongs to exactly one workspace.
- **Identity**
  - `id: string` – stable identifier.
  - `name: string` – human‑friendly display name.
- **Metadata**
  - `description?: string` – optional description for humans.
- **Version summary**
  - A pointer to an **active** version (if any).
  - Counts of versions and drafts.
  - Timestamps for last relevant change.

Example conceptual shape:

```ts
interface ConfigurationSummary {
  id: string;
  name: string;
  description?: string | null;

  // Active configuration version, if any
  activeVersion?: ConfigurationVersionSummary | null;

  // Aggregated metadata
  totalVersions: number;
  draftVersions: number;
  lastUpdatedAt?: string | null;
}
````

Wire types may include additional backend‑specific fields; this is the
frontend’s mental model.

### 2.2 Configuration versions

Each Configuration has many **configuration versions**. A configuration version is treated as
an immutable snapshot.

Key properties:

* **Identity**

  * `id: string` – version id.
  * `label: string` – human‑friendly label (e.g. `v4 – Q1 tweaks`).
* **Lifecycle**

  * `status: "draft" | "active" | "inactive"`.
* **Environment & validation health**

  * `lastBuildStatus?: "ok" | "error" | "pending" | "unknown"`.
  * `lastBuildAt?: string | null`.
  * `lastValidationStatus?: "ok" | "error" | "pending" | "unknown"`.
  * `lastValidationAt?: string | null`.
* **Provenance**

  * `createdAt: string`.
  * `createdBy: string`.
  * `derivedFromVersionId?: string` (if cloned).

Example conceptual interface:

```ts
type ConfigurationVersionStatus = "draft" | "active" | "inactive";

interface ConfigurationVersionSummary {
  id: string;
  label: string;
  status: ConfigurationVersionStatus;

  createdAt: string;
  createdBy: string;

  lastBuildStatus?: "ok" | "error" | "pending" | "unknown";
  lastBuildAt?: string | null;

  lastValidationStatus?: "ok" | "error" | "pending" | "unknown";
  lastValidationAt?: string | null;
}
```

Runs record the **configuration version id** they used, so historical runs are always
traceable to the code that produced them.

---

## 3. Version lifecycle

### 3.1 Lifecycle states

At the ADE Web level, every configuration version is presented as one of:

* **Draft**

  * Editable.
  * Used for development, environment builds, validation runs, and test runs.
* **Active**

  * Exactly **one** active version per Configuration.
  * Read‑only in the UI (no direct edits to files).
  * Used as the default version for “normal” runs that reference this
    Configuration.
* **Inactive**

  * Older or superseded versions.
  * Not used by default for new runs.
  * Kept for audit, comparison, and cloning.

Backend‑specific states (e.g. `published`, `archived`) are normalised into one
of these three for display.

### 3.2 Allowed transitions

From the **UI’s perspective**, we support:

* **Draft → Active**

  * User activates a draft version.
  * That version becomes **Active**.
  * The previous active version (if any) becomes **Inactive**.

* **Active → Inactive**

  * User deactivates the active version, leaving the Configuration with no
    active version (if the backend supports this).

* **Any → Draft (via clone)**

  * User clones any existing version (Active or Inactive).
  * The clone is a new **Draft** version.

We avoid arbitrary state jumps; to “revive” an inactive version, users clone it
into a new draft and then activate that draft.

### 3.3 Configuration vs workspace defaults

A few important invariants:

* **Per Configuration**, at most one active version.
* A workspace may have many Configurations, each with its own active version.
* When creating a **run**:

  * From the **Documents** screen, the UI selects a Configuration + version
    (typically the active version of the chosen Configuration).
  * From the **Config Builder workbench**, the run is tied to the version that
    workbench is editing (often a draft), unless explicitly overridden.

Any workspace‑level “default configuration for new runs” is an additional layer
on top of this model and should be described separately if introduced.

---

## 4. Configurations section architecture (Config Builder)

The Configurations section (home of the Config Builder) is the workspace‑local section at:

```text
/workspaces/:workspaceId/config-builder
```

It has two main responsibilities:

1. **Configuration list / overview**
   Show all configurations in the workspace, with high‑level status.
2. **Workbench launcher**
   Provide clear entry points into the workbench for a particular Configuration +
   version.

High‑level behaviour:

* On load, we fetch the configurations list for the current workspace.
* Users can:

  * Create new configurations.
  * Clone existing configurations.
  * Inspect version summaries.
  * Export configurations.
  * Open a configuration version in the workbench.

Safe mode and permissions determine which actions are enabled (see §9).

---

## 5. Configuration list UI

### 5.1 Columns and content

Each row represents a Configuration. Typical columns:

* **Name** – display name.
* **Active version** – label for the active version or “None”.
* **Drafts** – count of draft versions.
* **Last updated** – when any version was last changed (creation, build, or
  validation).
* **Health** (optional) – a compact “Build / Validation” indicator.
* **Actions** – inline buttons or a context menu.

Empty states:

* No configurations + user can create → short explanation of what a
  configuration is + a “Create configuration” button.
* No configurations + user cannot create → read‑only explanation and guidance to
  contact an admin.

### 5.2 Actions from the list

Per Configuration, we surface:

* **Open in workbench**

  * Opens the workbench on a reasonable starting version (see §5.3).
* **View versions**

  * Opens a panel or detail view listing all configuration versions.
* **Create draft**

  * Create a new draft version from:

    * The active version (default), or
    * A chosen version (if user selects one).
* **Clone configuration**

  * Create a new Configuration, seeded from this one.
* **Export**

  * Download an export of the backing configuration package.
* **Activate / Deactivate**

  * Promote a draft to Active or deactivate the currently active version.

All of these actions are permission‑gated and safe‑mode‑aware.

### 5.3 Which version opens in the workbench?

When a user clicks **Open in workbench**:

* If there is at least one **draft**:

  * Open the **latest draft** (most recently created).
* Else if there is an **active** version:

  * Open the active version in read‑only mode.
* Else:

  * Create a **new draft** (from template or empty skeleton) and open that.

Users can switch versions inside the workbench (if a version selector is
available), but the initial choice must be consistent and unsurprising.

---

## 6. Version management UI

When a user drills into a Configuration, we show its **versions** explicitly.

### 6.1 Versions view

The versions list can be presented as:

* A **side drawer** attached to the Configuration row, or
* A dedicated **detail view** (`ConfigDetailPanel`) for that Configuration.

Each version row shows:

* Label.
* Status (`Draft`, `Active`, `Inactive`).
* `createdAt` / `createdBy`.
* Last build status and timestamp.
* Last validation status and timestamp.
* Optional “derived from” information.

### 6.2 Version‑level actions

Allowed actions depend on status:

* **Draft**

  * Open in workbench (for code editing).
  * Trigger environment build / validation run (usually via workbench controls).
  * Activate (if permitted and Safe mode is off).
  * Delete (if supported by backend and no runs depend on it).

* **Active**

  * Open in workbench (read‑only).
  * Clone into draft.
  * Deactivate (optional, if backend supports “no active version”).

* **Inactive**

  * Open in workbench (read‑only).
  * Clone into draft.

The versions view should make it obvious which version is currently active and
encourage “clone → edit → activate” as the main flow rather than direct edits.

### 6.3 Normalisation of backend states

Backends might expose states like `published`, `deprecated`, `archived`, etc.

We centralise a normalisation function, e.g.:

```ts
function normalizeConfigurationVersionStatus(
  raw: BackendVersionStatus,
): ConfigurationVersionStatus;
```

All views (Config list, versions drawer, workbench chrome) use this normalised
status, so the UI can evolve independently of backend nomenclature.

---

## 7. Manifest and schema integration

Each configuration version exposes a **manifest** (`manifest.json`) describing:

* Output tables and their schemas.
* Column metadata (keys, labels, ordinals, required/enabled).
* Links to transforms, validators, and detectors.

### 7.1 Discovering the manifest

The manifest is treated as just another file in the configuration file tree:

* Backend file listing includes `manifest.json`.
* The workbench’s file loading APIs fetch it like any other file.

The details of file listing and workbench integration are described in
`09-workbench-editor-and-scripting.md`. This section describes **how we use**
manifest data at the Config Builder level.

### 7.2 Manifest‑driven UI

ADE Web uses the manifest to:

* Render a **schema view** (if implemented):

  * Per‑table summary.
  * Per‑column fields: `key`, `label`, `required`, `enabled`, `depends_on`.

* Drive **column ordering**:

  * Sort columns by `ordinal` when rendering sample data or schema previews.

* Attach **script affordances**:

  * For example, show “Edit transform” or “Edit validator” buttons for entries
    that reference specific script paths.

* Improve **validation UI**:

  * Map validation messages to table/column paths from the manifest.

The schema view is intentionally **read‑focused** by default; any editing
capabilities (e.g. reordering columns or toggling `enabled`) must preserve
unknown manifest fields.

### 7.3 Patch model and stability

Manifest updates must be conservative:

* ADE Web should **not** rewrite `manifest.json` wholesale.

* Instead, it should:

  1. Read the manifest as JSON.
  2. Apply a narrow patch (e.g. update a column’s `enabled` flag).
  3. Send the updated document back (or call a dedicated “update manifest”
     API).

* Unknown keys and sections must be preserved.

This makes the Config Builder resilient to backend schema evolution.

---

## 8. Builds, validation runs, and test runs

Config Builder exposes one build action and two run modes. The names are
intentional to avoid “is this a build or a run?” confusion:

1. **Build** – prepare or rebuild the configuration **environment** (reusing it
   when possible). This is a `Build` entity and uses `/builds` endpoints.
2. **Validation run** – execute validators only to check configuration
   correctness (no full extraction). Implemented as a `Run` with
   `RunOptions.validateOnly: true` and usually `mode: "validation"`.
3. **Test run** – execute ADE on a sample document with the chosen configuration
   version, streaming logs into the workbench. Often sets `mode: "test"` and
   may use `dryRun: true`.

Run creation uses the canonical `RunOptions` shape
(`dryRun`/`validateOnly`/`inputSheetNames`/`mode`) in camelCase and converts
those to backend snake_case fields (`dry_run`, `validate_only`,
`input_sheet_names`). The **workbench chrome** exposes buttons and keyboard
shortcuts for each action.

### 8.1 Build

Goal:

> Ensure the environment for this configuration version is ready and in sync
> with the latest files.

Behaviour:

* User triggers a build via the workbench:

  * Button (e.g. “Build environment”).
  * Shortcuts (`⌘B` / `Ctrl+B`, or `⇧⌘B` / `Ctrl+Shift+B` for force rebuild).

* Frontend calls a build endpoint, for example:

  ```http
  POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds
  ```

* Backend returns a `build_id`.

* Workbench subscribes to:

  ```http
  GET /api/v1/builds/{build_id}/logs
  ```

  as an NDJSON stream.

* Final build status updates:

  * `ConfigurationVersionSummary.lastBuildStatus` / `lastBuildAt`.
  * Configuration list and versions view.

### 8.2 Validation runs

Goal:

> Check that the configuration on disk is consistent without running a full
> extraction.

Behaviour:

* Triggered via a “Validation run” action in workbench controls.

* Frontend calls something like:

  ```http
  POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/validate
  ```

* Backend may stream logs; ADE Web treats this as a `Run`:

  * Writes textual logs to the console.
  * Populates the **Validation** panel with structured issues (severity,
    location, message).
  * Sends run options with `validate_only: true` (and optionally `mode:
    "validation"` in UI state).

* `lastValidationStatus` / `lastValidationAt` are updated for the version.

In Config Builder overview, these statuses can be summarised as simple badges
(“Build OK”, “Validation failed”, etc.).

### 8.3 Test runs (run extraction from builder)

Goal:

> Execute ADE on a sample document using a particular configuration version,
> while seeing logs and summary in the workbench.

Behaviour:

1. User clicks **Run extraction** in the workbench.

2. A **Run extraction dialog** appears where they:

   * Choose a document (e.g. from recent workspace documents).
   * Optionally limit worksheets (for spreadsheets).

3. Frontend creates a run via the backend’s run creation endpoint:

   * This may be a configuration‑scoped route (e.g.
     `/configurations/{configuration_id}/runs`) or a workspace‑scoped route that accepts
     `config_version_id`. Payload uses `RunOptions` (camelCase → snake_case) and
     can set `mode: "test"` for clarity.

4. Workbench subscribes to the run’s event/log stream:

   * Console updates live as the run progresses.
   * A **Run summary** card appears at the end, with:

     * Run ID and status.
     * Document name.
     * Output artifact links (if provided).

5. The run also appears in the global **Runs** history view (see
   `07-documents-and-runs.md`), which may still be backed by `/runs` endpoints
   server‑side.

---

## 9. Safe mode and permissions

Config Builder is tightly integrated with **Safe mode** and **RBAC** (see
`05-auth-session-rbac-and-safe-mode.md`).

### 9.1 Safe mode

When Safe mode is **enabled**:

* The following actions are **blocked**:

  * Environment builds.
  * Validation runs (configuration validation).
  * Test runs (“Run extraction”).
  * Activate/publish configuration versions.

* The following remain available:

  * Viewing configurations, versions, manifest, and schema views.
  * Exporting configurations.
  * Viewing historical logs and validation results.

UI behaviour:

* The workspace shell shows a **Safe mode banner** with the backend‑provided
  `detail` message.
* Buttons for blocked actions are disabled and show a tooltip, e.g.:

  > “Safe mode is enabled: <detail>”

Config Builder does **not** attempt to perform these actions and then interpret
 errors; it reads Safe mode state and proactively disables them.

### 9.2 Permissions

Configuration operations are governed by workspace permissions, for example:

* `Workspace.Configurations.Read`
* `Workspace.Configurations.ReadWrite`
* `Workspace.Configurations.Activate`

Patterns:

* **View list / versions** → `Read`.
* **Create / clone configuration** → `ReadWrite`.
* **Edit files / build / validate / test run** → `ReadWrite` and Safe mode off.
* **Activate / deactivate version** → `Activate`.

Helpers in `shared/permissions` are used to:

* Decide which actions to show.
* Decide which actions are disabled with a tooltip vs hidden entirely.

---

## 10. Backend contracts (summary)

This section maps the conceptual model to backend routes. Names may evolve; keep
this in sync with the actual OpenAPI spec.

### 10.1 Configuration metadata

Under a workspace:

```http
GET  /api/v1/workspaces/{workspace_id}/configurations
POST /api/v1/workspaces/{workspace_id}/configurations

GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}
GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/export
```

* `GET /configurations` → list configurations for the workspace.
* `POST /configurations` → create new configuration (optionally from a template
  or existing configuration).
* `GET /configurations/{configuration_id}` → configuration detail.
* `GET /configurations/{configuration_id}/export` → export the backing configuration package.

### 10.2 Version lifecycle

```http
GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/versions
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/publish
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/activate
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/deactivate
```

* `GET /versions` → list all versions for a Configuration.
* `POST /publish` → (if present) mark a draft as “published” internally.
* `POST /activate` → mark version as active.
* `POST /deactivate` → clear active status (if supported).

Frontend responsibilities:

* Treat these endpoints as **actions** (no hand‑built state machine).
* Refresh Configuration + versions after each call.
* Apply `normalizeConfigurationVersionStatus` to map backend state into
  `draft/active/inactive`.

### 10.3 Files, manifest, and directories

File and directory operations:

```http
GET    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files
GET    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}
PUT    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}
PATCH  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}
DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}

POST   /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}
DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}
```

These underpin:

* The workbench file tree.
* Code editing (open/save).
* Manifest reads and writes.

Manifest is treated as `manifest.json` in the file tree unless a dedicated API
is introduced.

### 10.4 Build and validate

Build endpoints:

```http
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds
GET  /api/v1/builds/{build_id}
GET  /api/v1/builds/{build_id}/logs   # NDJSON stream
```

Validation endpoint:

```http
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/validate
```

Frontend wraps these in domain‑specific hooks, e.g.:

* `useTriggerConfigBuild`
* `useConfigBuildLogsStream`
* `useValidateConfiguration`

Streaming details and React Query integration are described in
`04-data-layer-and-backend-contracts.md` and `09-workbench-editor-and-scripting.md`.

---

## 11. End‑to‑end flows

This section ties everything together in concrete scenarios.

### 11.1 Create and roll out a new configuration

1. User opens the **Configurations** section / Config Builder (`/workspaces/:workspaceId/config-builder`).
2. Clicks **Create configuration**.
3. Fills in name and optional template.
4. Frontend calls `POST /configurations`.
5. Backend returns a Configuration with an initial **draft** version.
6. UI opens the workbench on that draft.
7. User edits files, runs an environment **build**, performs a **validation
   run**, and executes **test runs** against sample documents.
8. When ready, user clicks **Activate** on the draft version.
9. The new version becomes **Active**; it becomes the default for new runs
   using this Configuration.

### 11.2 Evolve an existing configuration safely

1. From the Config Builder list, user selects an existing Configuration.
2. In the versions view, user **clones** the current active version → new
   **draft**.
3. Workbench opens on the draft.
4. User makes changes, builds the environment, runs **validation runs**, and
   test‑runs against sample documents.
5. When satisfied, user **activates** this draft.
6. The previously active version becomes **Inactive**.
7. The next runs referencing this Configuration use the new active version,
   while historical runs remain tied to the old version.

### 11.3 Debug a run and patch configuration

1. A run fails or produces unexpected results (seen in the **Runs** history
   view).

2. From the run detail, the user follows a link to **view the configuration and
   version** used for that run.

3. ADE Web opens the workbench on that version:

   * If it is a draft or inactive → read‑only.
   * User can **clone** it into a new draft to make changes.

4. User edits, validates, and test‑runs against similar documents.

5. Once fixed, user activates the new version.

6. Future runs use the corrected configuration; the problematic run remains
   traceable to the original version.

---

This document provides the architectural and UX model for **Configurations** and
the **Config Builder** in ADE Web: how configurations and their versions are
structured, how users interact with them, how they map to backend APIs, and how
they feed into runs across the rest of the app.
```

# apps/ade-web/docs/09-workbench-editor-and-scripting.md
```markdown
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
```

# apps/ade-web/docs/10-ui-components-a11y-and-testing.md
```markdown
# 10. UI components, accessibility, and testing

This document describes the UI component layer in `ade-web`: what lives in `src/ui`, how components are designed, the accessibility and keyboard conventions they follow, how user preferences are persisted, and how we test UI behaviour.

It assumes you’ve read:

* [`01-domain-model-and-naming.md`](./01-domain-model-and-naming.md) for terminology (e.g. *run*, *document*, *workspace*).
* [`06-workspace-layout-and-sections.md`](./06-workspace-layout-and-sections.md) for the high‑level layout.

---

## 1. Scope of the UI layer

All reusable UI components live in `src/ui`. The layer has a narrow, intentional scope:

* **Responsibilities**

  * Provide **presentational primitives** (buttons, form controls, alerts, layout scaffolding).
  * Provide **composite widgets** that are UI‑heavy but domain‑agnostic (tabs, context menus, top bar, search field, code editor wrapper).
  * Encode **accessibility and keyboard patterns** so features don’t have to re‑implement them.
  * Offer **stable, predictable APIs** for feature code to compose.

* **Non‑responsibilities**

  * No HTTP or React Query calls.
  * No knowledge of ADE concepts (no runs/documents/workspaces inside `src/ui`).
  * No permission checks or business rules.
  * No direct `localStorage` or routing logic.

If a component needs to know *which* run to start, *who* the user is, or *whether* an action is allowed, that logic belongs in `src/features`, not `src/ui`.

---

## 2. Structure of `src/ui`

The UI library is organised by function, not by domain:

```text
src/ui/
  button/
    Button.tsx
    SplitButton.tsx
  form/
    Input.tsx
    TextArea.tsx
    Select.tsx
    FormField.tsx
  feedback/
    Alert.tsx
  identity/
    Avatar.tsx
    ProfileDropdown.tsx
  navigation/
    TabsRoot.tsx
    TabsList.tsx
    TabsTrigger.tsx
    TabsContent.tsx
    ContextMenu.tsx
  shell/
    GlobalTopBar.tsx
    GlobalSearchField.tsx
  code-editor/
    CodeEditor.tsx
  ...
```

Conventions:

* One **main component per file** (e.g. `Button.tsx` exports `Button`).
* Optional small helper components may live next to the main one if they are tightly coupled.
* Barrels (`index.ts`) are allowed but not required; they should not hide important component names.

### 2.1 Design constraints

All `src/ui` components follow a few design rules:

* **Presentational**
  They receive data and callbacks via props; they don’t fetch or derive it from global state.

* **Minimal internal state**
  Local state is used only for UI concerns (open/closed, focus, hover), never for domain state.

* **Tailwind for styling**
  Styling is implemented with Tailwind classes. Shared class helpers are fine where they improve reuse.

* **Theme‑agnostic**
  Components derive colours from Tailwind theme tokens rather than hard‑coding values so a light/dark app‑wide theme remains possible without refactors.

* **Predictable APIs**

  * Components are PascalCase (`Button`, `GlobalTopBar`).
  * Boolean props are `isX`/`hasX` (e.g. `isLoading`).
  * Event handlers are `onX` (e.g. `onClick`, `onSelect`).

---

## 3. Component categories

This section summarises the main component families and their expected usage patterns.

### 3.1 Buttons

#### `Button`

Generic clickable action.

* **Variants**

  * `"primary"` – main call‑to‑action in a view (e.g. “Start run”, “Upload document”).
  * `"secondary"` – important but secondary actions (e.g. “Cancel”, “Back”).
  * `"ghost"` – low‑emphasis actions (e.g. “View logs”, “More details”).
  * `"danger"` – destructive actions (e.g. “Delete configuration”).

* **Sizes**
  `"sm"`, `"md"`, `"lg"` (default is `"md"`).

* **Loading state**

  * `isLoading` disables the button and shows an inline spinner.
  * Clicks are ignored while `isLoading` is true.

Example:

```tsx
<Button variant="primary" isLoading={isSubmitting} onClick={handleStartRun}>
  Start run
</Button>
```

#### `SplitButton`

Primary action plus a small dropdown of related actions. The canonical example is the Config Builder **Build environment** control.

* Left segment: calls `onPrimaryClick` (e.g. “Build / reuse environment”).
* Right segment: opens a dropdown (often backed by `ContextMenu`) with secondary options (e.g. “Force rebuild now”).

Guidelines:

* Use when there is **one obvious default** and 1–3 related expert options.
* The primary action should correspond to the “safe, common” behaviour.

---

### 3.2 Form controls

#### `Input`

Single‑line text input.

* Props: `value`, `onChange`, `type`, `placeholder`, etc.
* `invalid` prop applies error styling and sets `aria-invalid="true"`.

#### `TextArea`

Multi‑line text input.

* Shares styling and error handling with `Input`.

#### `Select`

Styled wrapper around a native `<select>`.

* Visual alignment with `Input` and `TextArea`.
* Optional disabled placeholder option for “no selection”.

#### `FormField`

Wrapper that connects a control to a label, hint, and error message.

* Props:

  * `label: string`
  * `hint?: string`
  * `error?: string`
  * `fieldId?: string`
  * `children: ReactNode` (exactly one form control)

Behaviour:

* Ensures a `<label>` is associated with the control (`htmlFor` / `id`).
* Sets `aria-describedby` to hint and/or error elements.
* Sets `aria-invalid` when `error` is present.

Example:

```tsx
<FormField label="Workspace name" hint="Shown in the sidebar" error={errors.name}>
  <Input
    value={name}
    onChange={e => setName(e.target.value)}
    invalid={Boolean(errors.name)}
  />
</FormField>
```

---

### 3.3 Feedback

#### `Alert`

Inline, non‑modal message.

* Props:

  * `tone: "info" | "success" | "warning" | "danger"`
  * Optional `heading`
  * Optional icon (chosen based on tone)

Usage:

* Section‑level issues or guidance.
* Long‑lived success messages (“This configuration is now active.”).
* Local warnings (“This run used an older configuration version.”).

Global banners and toasts are composed using `Alert` styles at higher layers (see § 5).

---

### 3.4 Identity

#### `Avatar`

Text‑based avatar.

* Derives initials from `name` (preferred) or `email`.
* Sizes: `"sm"`, `"md"`, `"lg"`.

Used for:

* Users in the top bar and member lists.
* Workspaces in nav and cards (workspaces may use first letter or initials of their name).

#### `ProfileDropdown`

User menu in the top bar.

* Shows:

  * Display name.
  * Email address.
* Offers actions such as:

  * “Sign out”
  * Links to profile/account settings (if present).

Behaviour:

* Opens on click.
* Closes on:

  * Outside click.
  * Escape key.
  * Selecting an item.
* Manages focus so keyboard users can open, move within, and close the menu without getting “lost”.

---

### 3.5 Navigation widgets

#### Tabs (`TabsRoot`, `TabsList`, `TabsTrigger`, `TabsContent`)

Accessible tab system:

* `TabsRoot` owns state (selected tab).
* `TabsList` wraps triggers, sets `role="tablist"`.
* `TabsTrigger` is a `<button>` with `role="tab"`, `aria-selected`, and `aria-controls`.
* `TabsContent` is a container with `role="tabpanel"` and `aria-labelledby`.

Keyboard:

* `ArrowLeft` / `ArrowRight` move between tabs.
* `Home` / `End` jump to first / last.
* Focus and selection behaviour matches ARIA authoring practices.

Tabs are used for:

* Splitting views within a section (e.g. “Console” vs “Validation” in the workbench).
* Settings sub‑sections where URL state isn’t required.

#### `ContextMenu`

Right‑click / kebab‑menu popup:

* Takes a list of items:

  * `label`
  * Optional `icon`
  * Optional `shortcut` string (visual only)
  * `onSelect`
  * `danger?: boolean`
  * `disabled?: boolean`

* Positions itself within the viewport to avoid overflow.

* Keyboard:

  * `ArrowUp` / `ArrowDown` to move.
  * `Enter` / `Space` to select.
  * `Esc` to close.

Used for:

* Workbench file tree (file/folder actions).
* Workbench tabs (close, close others, etc.).
* Any context‑sensitive menu where right‑click behaviour helps.

---

### 3.6 Top bar and search

#### `GlobalTopBar`

Shell‑level horizontal bar used in both the Workspace directory and Workspace shell.

Slots:

* `brand` – product or workspace directory branding.
* `leading` – breadcrumbs or current context (workspace name, environment label).
* `actions` – top‑level actions (e.g. “Start run”, “Upload”).
* `trailing` – typically `ProfileDropdown`.
* `secondaryContent` – optional row for filters, breadcrumbs, or hints.

Responsive behaviour:

* On narrow viewports, the bar collapses to prioritise brand, search, and profile.

#### `GlobalSearchField`

Search field embedded into `GlobalTopBar`.

Capabilities:

* Optional scope label (e.g. “Within workspace”).

* Controlled/uncontrolled mode.

* Global shortcut:

  * `⌘K` on macOS.
  * `Ctrl+K` on Windows/Linux.

* Suggestions dropdown:

  * Arrow keys to navigate.
  * Enter to select.
  * Esc to close.

The field itself remains generic; feature code decides:

* Which suggestions to show.
* How to handle “submit” and “select” actions (e.g. navigate to a run, filter documents).

---

### 3.7 Code editor wrapper

#### `CodeEditor`

A thin wrapper for Monaco, used by the Config Builder workbench.

Responsibilities:

* Manage Monaco’s lifecycle and lazy loading.

* Expose a `ref` with:

  * `focus()`
  * `revealLine(lineNumber: number)`

* Handle:

  * `language` (string ID, e.g. `"python"`, `"json"`).
  * `path` (virtual file path for Monaco’s model).
  * `theme` (`"ade-dark"` or `"vs-light"`).
  * `value` / `onChange`.
  * `readOnly`.
  * `onSaveShortcut` (wired to `⌘S` / `Ctrl+S`).

It does **not** know about ADE script semantics; those are configured by the workbench layer (see [`09-workbench-editor-and-scripting.md`](./09-workbench-editor-and-scripting.md)).

---

## 4. Accessibility patterns

Accessibility is a core requirement. UI components are responsible for exposing correct semantics; features only provide content.

### 4.1 Semantic roles and labels

* Use semantic elements wherever possible:

  * Buttons are `<button>`, links are `<a>`, lists are `<ul>/<li>`.

* When semantics require ARIA:

  * Tabs, menus, toolbars, and context menus use ARIA roles (`role="tab"`, `role="menu"`, etc.).
  * `Alert` uses `role="status"` or `role="alert"` where appropriate.

* Labels:

  * Icon‑only buttons must have `aria-label` or `aria-labelledby`.
  * `FormField` ensures text labels are linked to inputs via `for`/`id`.

### 4.2 Focus behaviour

Patterns:

* **Dropdowns/menus** (`ProfileDropdown`, `ContextMenu`):

  * When opened via keyboard, focus moves into the menu.
  * Tab/Shift+Tab cycle within the menu.
  * Esc closes the menu and returns focus to the trigger.

* **Overlays** (maximised workbench, future modals):

  * Background content is visually de‑emphasised and not focusable.
  * Focus is trapped within the overlay.
  * Esc closes or restores (subject to unsaved‑changes handling) and returns focus.

* **Tab order**:

  * Interactive elements must be reachable via Tab in a logical order.
  * Avoid `tabIndex` except where needed to support composite widgets (tabs, menus).

### 4.3 Keyboard interactions

For each widget:

* **Buttons and triggers**:

  * React to `Enter` and `Space`.
  * Visually indicate focus.

* **Tabs**:

  * Left/Right/Home/End manage focus and selection as per ARIA guidelines.

* **Menus**:

  * Arrow keys move between items.
  * Enter/Space selects.
  * Esc cancels.

### 4.4 Automated a11y checks

We treat automated accessibility tooling (e.g. axe) as a source of truth where practical. Violations reported in tests are expected to fail the suite until resolved or explicitly justified.

Shortcuts (below) build on top of these primitives.

---

## 5. Keyboard shortcuts

Keyboard shortcuts are implemented centrally (e.g. in `src/shared/keyboard`). UI components may display shortcut hints, but they do not bind global listeners themselves.

### 5.1 Global shortcuts

* `⌘K` / `Ctrl+K`
  Focus the `GlobalSearchField` or open a workspace search overlay.

* `⌘U` / `Ctrl+U`
  Open the document upload flow in the Documents section (when available).

Rules:

* Global shortcuts **must not** override browser behaviour when focus is in:

  * Text inputs.
  * Textareas.
  * Content‑editable regions.

* If a screen does not support a shortcut (e.g. `⌘U` on the Config Builder), the handler must no‑op.

### 5.2 Workbench shortcuts

Scoped to the Config Builder workbench:

* `⌘S` / `Ctrl+S` – Save active file in `CodeEditor`.
* `⌘B` / `Ctrl+B` – Build / reuse environment.
* `⇧⌘B` / `Ctrl+Shift+B` – Force rebuild.
* `⌘W` / `Ctrl+W` – Close active editor tab.
* `⌘Tab` / `Ctrl+Tab` – Switch to most recently used tab (forward).
* `⇧⌘Tab` / `Shift+Ctrl+Tab` – Switch MRU backward.
* `Ctrl+PageUp` / `Ctrl+PageDown` – Cycle tabs by visual order.

Guidelines:

* Implemented in the workbench container, not in `CodeEditor` or tab components directly.
* Use `preventDefault()` only when a shortcut is actually handled.
* Shortcuts should be disabled while modal dialogs in the workbench are open, unless they are explicitly designed to work there.

---

## 6. Notifications

Notifications are built from the same primitives (`Alert`, top‑bar/banners) but rendered at different scopes.

### 6.1 Toasts

Short‑lived messages that appear in a corner overlay.

Use for:

* Fast, non‑blocking feedback:

  * “Run queued.”
  * “File saved.”
  * “Document uploaded.”

Behaviour:

* Auto‑dismiss after a short duration.
* Accessible via a status region so screen readers receive updates.

### 6.2 Banners

Persistent messages at the top of a workspace or section.

Use for:

* Safe mode notifications.
* Connectivity problems.
* Important system‑level warnings.

Behaviour:

* Rendered under `GlobalTopBar` in the Workspace shell.
* Remain visible until the underlying condition changes or a user closes them (if dismissible).

### 6.3 Inline alerts

Local to a panel or form:

* Validation summary at the top of a form.
* Warning about a specific run or configuration.
* Guidance in an empty state.

These use `Alert` directly within the layout.

---

## 7. State persistence and user preferences

UI state and preferences are stored in `localStorage` via helpers in `src/shared/storage`. Components in `src/ui` are written to work cleanly whether preferences are present or absent.

### 7.1 Key naming convention

All preference keys follow:

```text
ade.ui.workspace.<workspaceId>.<suffix>
```

Examples:

* `ade.ui.workspace.<workspaceId>.nav.collapsed`
* `ade.ui.workspace.<workspaceId>.workbench.returnPath`
* `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.tabs`
* `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.console`
* `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.editor-theme`
* `ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences`

Rules:

* Keys are **per user**, **per workspace**, and optionally **per configuration** or **per document**.
* Only non‑sensitive data is stored; clearing storage should never break server state.
* No tokens, secrets, or PII beyond IDs that are already visible in the UI.

### 7.2 Persisted preferences

Current preferences include:

* **Workspace nav collapsed state**

  * Suffix: `nav.collapsed` (boolean).

* **Workbench return path**

  * Suffix: `workbench.returnPath` (string URL).
  * Used when exiting the workbench to navigate back to where the user came from.

* **Workbench open tabs**

  * Suffix: `configuration.<configurationId>.tabs`.
  * Value: `PersistedWorkbenchTabs` (open tab IDs, active ID, MRU list).

* **Workbench console state**

  * Suffix: `configuration.<configurationId>.console`.
  * Value: `ConsolePanelPreferences` (open/closed + height fraction).

* **Editor theme preference**

  * Suffix: `configuration.<configurationId>.editor-theme`.
  * Value: `"system" | "light" | "dark"`.

* **Per‑document run preferences**

  * Suffix: `document.<documentId>.run-preferences`.
  * Value: last used configuration, configuration version, sheet selections, optional run flags.

### 7.3 Access patterns

All storage access goes through helpers such as:

* `getPreference(workspaceId, suffix, defaultValue?)`
* `setPreference(workspaceId, suffix, value)`
* `clearWorkspacePreferences(workspaceId)`

Feature code (not `src/ui`) calls these helpers. Components simply receive the derived state via props.

---

## 8. Testing and quality

UI behaviour is validated with Vitest and React Testing Library. The goal is to test real user‑visible behaviour, not implementation details.

### 8.1 Test environment

Configuration (see `vitest.config.ts`):

* `environment: "jsdom"`
* `setupFiles: "./src/test/setup.ts"`
* `globals: true`
* `coverage.provider: "v8"`

`src/test/setup.ts` is responsible for:

* Installing DOM polyfills as needed.
* Configuring React Testing Library defaults.
* Optionally mocking `window.matchMedia` and similar browser APIs.

### 8.2 Testing `src/ui` components

For each component, prefer small, focused tests:

* **Buttons**

  * Click invokes `onClick`.
  * `isLoading` disables the button and renders a spinner.
  * Correct classes for variants and sizes.

* **Form controls / `FormField`**

  * `FormField` wires label, hint, and error via `for`/`id` and `aria-describedby`.
  * `invalid` sets `aria-invalid`.

* **Tabs**

  * Correct ARIA roles and attributes.
  * Arrow keys change focus and selection.
  * Only the active panel is visible.

* **ContextMenu**

  * Opens on trigger.
  * Items can be navigated by keyboard.
  * Calls `onSelect` and closes on selection or Esc.

* **ProfileDropdown**

  * Opens/closes with click and Esc.
  * Focus returns to trigger on close.

Tests should focus on:

* **What** the user sees and can do.
* Not **how** the component is implemented internally.

### 8.3 Testing keyboard shortcuts

Shortcuts are tested at the feature level, but they rely on UI components behaving correctly.

Examples:

* Global search:

  * Simulate `Ctrl+K`.
  * Assert that `GlobalSearchField` is focused.
  * Assert no action when a text input has focus.

* Workbench shortcuts:

  * Render workbench with `CodeEditor` and tabs.
  * Simulate `Ctrl+S` and assert the save handler is called.
  * Simulate `Ctrl+W` and assert the active tab closes.

These tests live under `src/features/.../__tests__/` and treat `src/ui` components as black boxes.

### 8.4 Testing state persistence

Test the storage helpers and features that rely on them:

* Storage helpers:

  * Correct key computation given workspace/configuration/document IDs.
  * Graceful handling of missing/malformed data.

* Workbench:

  * Hydrates tabs from persisted state.
  * Writes updated state when tabs open/close.

* Preferences:

  * Editor theme, console state, nav collapse.

UI components are not tested against `localStorage` directly; they assume their props are already configured.

### 8.5 Quality conventions

To keep the UI layer maintainable:

* **No direct globals**

  * Don’t call `window.location` or `localStorage` directly in `src/ui`.
  * Don’t attach global event listeners from `src/ui` without a clear cleanup path.

* **Linting & formatting**

  * Components must pass ESLint and Prettier checks enforced by the repo.

* **Keep docs in sync**

  * When adding a new UI component, shortcut, or preference:

    * Update this document.
    * If behaviour affects workbench or layout, update the relevant docs (`06`, `09`).

### 8.6 Selecting elements in tests

Prefer semantic queries in React Testing Library (`getByRole`, `getByLabelText`, visible text) so tests match user behaviour. Use `data-testid` only when no suitable semantic selector exists, and declare them in `src/ui` components to keep selectors stable for feature tests.

This keeps the UI layer small, predictable, and easy for both humans and AI agents to understand and extend.
```
