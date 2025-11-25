# Logical module layout (source -> sections below):
# - apps/ade-web/README.md
# - apps/ade-web/src/app/App.tsx
# - apps/ade-web/src/app/AppProviders.tsx
# - apps/ade-web/src/app/nav/Link.tsx
# - apps/ade-web/src/app/nav/history.tsx
# - apps/ade-web/src/app/nav/urlState.ts
# - apps/ade-web/src/main.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/detail/index.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/ActivityBar.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/BottomPanel.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/EditorArea.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Explorer.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Inspector.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/PanelResizeHandle.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/index.tsx
# - apps/ade-web/vite.config.ts
# - apps/ade-web/vitest.config.ts

# apps/ade-web/README.md
```markdown
````markdown
# ADE Web

ADE Web is the browser‑based front‑end for the **Automatic Data Extractor (ADE)** platform.

It serves two main personas:

- **Workspace owners / engineers** – design and evolve configuration packages (Python packages) that describe how documents are processed; manage safe mode; and administer workspaces, SSO, roles, and members.
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

### Workspace directory layout

The **Workspace directory** (`/workspaces`) is the primary entry point after sign‑in:

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

### Workspace shell layout

Inside a workspace (`/workspaces/:workspaceId/...`) ADE Web uses a reusable **workspace shell**:

- **Left navigation (desktop)**:
  - Workspace avatar/initials and name.
  - “Switch workspace” affordance.
  - Primary sections:
    - Documents
    - Runs
    - Config Builder
    - Settings
  - Collapse/expand state is persisted **per workspace** (so each workspace “remembers” whether you prefer a compact nav).

- **Top bar**:
  - Workspace name and optional environment label (e.g. “Production”, “Staging”).
  - Context‑aware **search**:
    - On the **Documents** section, it acts as a document‑scoped search.
    - Elsewhere, it can search within the workspace (sections, configs, runs).
  - A profile dropdown (user’s display name/email, sign‑out, etc.).

- **Mobile navigation**:
  - The left nav becomes a slide‑in panel:
    - Opens via a menu button.
    - Locks body scroll while open.
    - Closes on navigation, tapping outside, or pressing Esc.

- **Safe mode banner**:
  - When safe mode is active, a persistent banner appears within the workspace shell explaining that runs/builds are paused.

- **Notifications**:
  - Toasts for success/error messages.
  - Banners for cross‑cutting issues like safe mode or connectivity.

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

A **document** is any input file processed by ADE, often:

- Spreadsheets: `.xls`, `.xlsx`, `.xlsm`, `.xlsb`
- CSV/TSV files: `.csv`, `.tsv`
- PDFs and other semi‑structured formats (e.g. `.pdf`)

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
- Run dialogs (including the Config Builder’s *Run extraction* flow) can then offer sheet‑level selection.

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
    - An overall artifact (e.g., zipped outputs),
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

The Config Builder workbench uses the same run APIs to:

- Trigger *validation‑only* runs for a config version.
- Trigger *extraction* runs directly from the editor against recent workspace documents.
- Display the latest run’s outputs, artifact, and telemetry in a dedicated **Run summary** panel alongside the console.

---

### Config packages & versions

A **config package** is a Python package that tells ADE how to:

- Interpret specific document formats,
- Validate incoming data,
- Transform it into structured outputs.

Per workspace:

- There may be **one or many** config packages (e.g., per client, per pipeline).
- Each package has **config versions** (immutable snapshots).
- Exactly **one version is active** for “normal” runs at any time.

#### Version lifecycle

The product‑level lifecycle is:

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

Backends may add internal states (e.g. “published”, “archived”), but ADE Web presents the version lifecycle as **Draft → Active → Inactive**.

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

### Top‑level routes (`App.tsx`)

At the app entry point, `App` wraps everything in:

- `NavProvider` – custom navigation context.
- `AppProviders` – global React Query provider and dev tools.

`ScreenSwitch` inspects the **current pathname** (normalised to strip trailing slashes) and renders:

- `/` – Home / entry strategy (decides whether to send the user to login, setup, or the app).
- `/login` – Sign‑in and auth provider selection.
- `/auth/callback` – Auth provider callback handler.
- `/setup` – First‑run setup flow.
- `/logout` – Logout screen.
- `/workspaces` – Workspace directory.
- `/workspaces/new` – Create workspace.
- `/workspaces/:workspaceId/...` – Workspace shell; the exact internal route is resolved inside the workspace screen.
- Any other path – “Not found” screen.

Paths are **normalised** to avoid trailing‑slash variants (`/foo/` becomes `/foo`).

Within `/workspaces/:workspaceId`, the first path segment after the workspace ID selects the section:

- `/documents` – Documents list and document run UI.
- `/runs` – Runs ledger.
- `/config-builder` – Config overview and Builder routes:
  - e.g. `/config-builder/:configId` for a specific config,
  - nested routes for the editor workbench.
- `/settings` – Workspace settings:
  - Uses a `view` query parameter to choose sub‑tabs (general, members, roles).
- `/overview` – Optional overview/summary surface.

Unknown section paths inside a workspace show a **workspace‑local “Section not found”** state rather than a global 404.

### Custom navigation layer (`NavProvider`, `Link`, `NavLink`)

Navigation is handled by a small custom system instead of a third‑party router:

- `NavProvider` holds the current `location`:

  ```ts
  type LocationLike = { pathname: string; search: string; hash: string };
````

* Hooks:

  * `useLocation()` – read the current location.
  * `useNavigate()` – push or replace a new URL.
  * `useNavigationBlocker(blocker, when)` – register a function that can veto navigations.

#### SPA links

`Link` wraps `<a>` and:

* Sets `href={to}` for semantics and right‑click behaviour.
* Intercepts **unmodified** left‑clicks:

  * Calls any user `onClick`.
  * If `event.defaultPrevented` is false and no modifier keys are held:

    * Calls `preventDefault()`.
    * Uses `navigate(to, { replace })` to perform SPA navigation.
* For modified clicks (`metaKey`, `ctrlKey`, `shiftKey`, `altKey`), it **does not intercept**; the browser opens a new tab/window as usual.

`NavLink` builds on `Link` and:

```ts
const isActive = end
  ? pathname === to
  : pathname === to || pathname.startsWith(`${to}/`);
```

* Accepts:

  * `className` as a string or `(args: { isActive: boolean }) => string`.
  * `children` as a React node or `(args: { isActive: boolean }) => ReactNode`.
* Enables active styling and “active” render variants for nav items.

#### Back/forward and blockers (`history.tsx`)

`NavProvider` integrates with the browser history:

* Maintains a stateful `loc` derived from `window.location`.
* Subscribes to `popstate`:

  * Builds a `nextLocation` from the new URL.

  * Constructs a `NavigationIntent`:

    ```ts
    type NavigationIntent = {
      readonly to: string;
      readonly location: LocationLike;
      readonly kind: "push" | "replace" | "pop";
    };
    ```

  * Runs all registered **navigation blockers** with `{ kind: "pop", ... }`.

  * If any blocker returns `false`:

    * Uses `window.history.pushState` to restore the previous location.
    * Does **not** update internal state.

  * If allowed:

    * Updates `loc` so `useLocation()` consumers re‑render.

Programmatic navigation via `useNavigate()`:

* `navigate(to, opts)`:

  * Resolves `to` relative to `window.location.origin` using `new URL(to, origin)`.
  * Builds `nextLocation` and `NavigationIntent` with `kind` = `"push"` or `"replace"`.
  * Runs blockers; if any returns `false`, navigation is cancelled.
  * If allowed:

    * Calls `window.history.pushState` or `replaceState`.
    * Manually dispatches `new PopStateEvent("popstate")` so the same logic runs as for user‑initiated navigation.

#### Navigation blockers

A **navigation blocker** is a function:

```ts
type NavigationBlocker = (intent: NavigationIntent) => boolean;
```

* Returning `false` cancels that navigation.
* Register using:

```ts
useNavigationBlocker(blocker, when);
```

* `when` controls whether the blocker is active.
* The hook automatically registers/unregisters as needed.

Typical usage:

* Config Builder and other editors use blockers to guard against losing unsaved changes.
* Blockers commonly:

  * Skip navigation if the target path is the same (e.g. just search/hash changing).
  * Optionally bypass checks in specific circumstances (e.g. “Save then navigate”).

---

## URL state & search parameters

ADE Web encodes important UI state in the URL so views can be shared and restored on refresh.

Helpers in `urlState.ts` provide:

* `toURLSearchParams(init)` – build `URLSearchParams` from:

  * A query string,
  * A tuple array,
  * An existing `URLSearchParams`,
  * A record of keys → value/array.
* `getParam(search, key)` – read a single param from a raw search string.
* `setParams(url, patch)` – patch query params on a `URL` and return the path+search+hash string.

### Hook: `useSearchParams`

`useSearchParams()` is a React hook that:

* Reads the current query string from `useLocation()`.

* Returns:

  ```ts
  const [params, setSearchParams] = useSearchParams();
  // params: URLSearchParams
  // setSearchParams: (init: SearchParamsInit | (prev) => SearchParamsInit, options?: { replace?: boolean }) => void
  ```

* When called, `setSearchParams`:

  * Computes the new `URLSearchParams`.
  * Builds a new URL preserving `pathname` and `hash`.
  * Calls `navigate(target, { replace })` under the hood.

### Search params overrides

A context, `SearchParamsOverrideProvider`, allows nested components to **override** the behaviour of `useSearchParams`:

* The override value supplies:

  * A synthetic `params` object.
  * A `setSearchParams` implementation.
* Inside that subtree:

  * `useSearchParams()` will use the override instead of the global URL.
* This is useful when:

  * A dialog or embedded panel wants to manage “local” query state while still being aware of the outer URL.
  * Legacy flows need to simulate query changes without actually altering the browser address bar.

Most sections use the **global** URL state directly, but the override hook is available for advanced cases.

---

## Config Builder – URL‑driven layout & workbench model

The **Config Builder** is implemented as an IDE‑like workbench. Its layout, panel state, and file selection are encoded in query parameters and mirrored into internal state.

### Config Builder URL state (`readConfigBuilderSearch` & `mergeConfigBuilderSearch`)

Config Builder layout and file selection are encoded in query parameters:

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

#### Reading builder state

`readConfigBuilderSearch(source)`:

* Accepts a `URLSearchParams` or raw search string.

* Normalises values:

  * `console` → `"open"` or `"closed"` (anything else → `"closed"`).
  * `pane` → `"console"` or `"validation"` (legacy `"problems"` maps to `"validation"`).
  * `view` → `"editor" | "split" | "zen"` (invalid → `"editor"`).
  * `file` reads `file` or legacy `path`.

* Returns a **snapshot**:

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

* The `present` flags indicate which keys were explicitly set in the URL vs inherited defaults. This allows the UI to distinguish “user explicitly set this” vs “just using defaults”.

#### Merging builder state

`mergeConfigBuilderSearch(current, patch)`:

* Reads the current state from `current` (a `URLSearchParams`).
* Merges:

  * Global defaults,
  * Existing state,
  * `patch` values.
* Produces a new `URLSearchParams` where:

  * All builder‑related keys are **wiped first** (`tab`, `pane`, `console`, `view`, `file`, `path`).
  * Only **non‑default** values are written back.
  * `file` is omitted if empty/undefined.

Result:

* URLs stay clean: defaults are not redundantly encoded.
* Deep‑linking is explicit and stable: only state that actually matters or differs from defaults appears in the query string.

### Workbench URL state hook (`useWorkbenchUrlState`)

Config Builder’s workbench consumes the helpers via `useWorkbenchUrlState`:

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

* Uses `useSearchParams()` + `readConfigBuilderSearch(params)` to derive the snapshot.
* `setFileId`, `setPane`, `setConsole`:

  * Guard against no‑ops (do nothing if already at the desired value).
  * Use `mergeConfigBuilderSearch(current, patch)` to compute a new search string.
  * Call `setSearchParams` with `{ replace: true }` so history stays clean (tweaking panel state does not spam the back button).

The `consoleExplicit` flag indicates whether the user has explicitly toggled the console panel in the URL (present vs implied).

---

## Other notable search params

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

## Workspace directory & creation

### Workspace directory (`/workspaces`)

The directory screen presents:

* A **search box** to filter workspaces by name or slug.
* An optional “Create workspace” button (permission‑gated).
* Cards for each workspace with:

  * Name and slug,
  * Default badge (if this is the user’s default workspace),
  * A concise list of role labels.

Clicking a card navigates into the workspace shell, typically landing on Documents.

### Create workspace (`/workspaces/new`)

Users with `Workspaces.Create` (and any additional deployment‑specific permissions) can create a new workspace.

Form fields:

* **Workspace name**:

  * Required.
  * Length‑limited (e.g. ≤ 255 characters).
* **Workspace slug**:

  * Required.
  * Lowercase and URL‑friendly.
  * Pattern like: `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
  * Auto‑slugified from name until the user edits it.
* **Workspace owner** (optional, permission‑gated):

  * Shown only if the user can read the user directory (e.g. `Users.Read.All`).
  * Defaults to the current user.
  * Select from a paginated, searchable list of users.

Validation:

* **Client‑side** via a schema (e.g. Zod):

  * Required fields,
  * Length and pattern checks.
* **Server‑side**:

  * Uniqueness checks for name/slug,
  * Field‑specific error messages mapped back to the form,
  * A generic error banner for non‑field issues.

On success:

* ADE Web invalidates workspace lists.
* The user is redirected to `/workspaces/:workspaceId` (which normalises to the default section).

---

## Config Builder workbench

The **Config Builder** uses a workbench abstraction to present a repository‑like view of a config package, backed by a file listing from the backend.

The workbench is designed to feel like a lightweight IDE:

* **Activity bar** on the far left (Explorer, Search, SCM, Extensions).
* **Explorer** tree for files.
* **Tabbed editor** in the centre with keyboard shortcuts and drag‑reordering.
* **Inspector** on the right for file metadata.
* **Bottom panel** for console logs and validation output.
* A **chrome header** with Save, Build, Run validation, Run extraction, panel toggles, and window controls.

### Workbench window & session model

A **workbench session** is tracked per workspace/config pair via a `WorkbenchWindowContext` (not shown in this file):

* The Config Builder route (`ConfigEditorWorkbenchRoute`) opens a session for the selected config:

  ```ts
  openSession({
    workspaceId,
    configId,
    configName: `${workspace.name} · ${resolvedName}`,
  });
  ```

* `windowState` is one of:

  * `"restored"` – workbench is rendered inline inside the Config Builder section.
  * `"maximized"` – workbench uses a fixed, immersive overlay layout; background scrolling is disabled by temporarily setting `document.documentElement.style.overflow = "hidden"`.
  * `"minimized"` – workbench is docked elsewhere (e.g. in a bottom dock), and the Config Builder route shows a “Workbench docked” placeholder.

The `Workbench` chrome exposes window controls:

* **Minimize** – delegates to `onMinimizeWindow`.
* **Maximize / Restore** – toggles between inline and immersive modes.
* **Close** – closes the session and returns to the Config Builder overview.

This separation lets the workspace shell decide where and how to present the editor while the workbench remains self‑contained.

### File tree representation (`WorkbenchFileNode`)

Internally, the workbench models the package as a tree of nodes:

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

Typical tree root for a config package:

* A folder such as `ade_config` with children:

  * `manifest.json`,
  * `config.env`,
  * `header.py`,
  * `detectors` folder,
  * `hooks` folder,
  * `tests` folder.

A **default tree** and file contents are used for local development and to seed an empty workbench:

* `DEFAULT_FILE_TREE` – in‑memory representation of a canonical sample package.
* `DEFAULT_FILE_CONTENT` – map of file IDs to initial content strings.

#### Building the tree from backend listing (`createWorkbenchTreeFromListing`)

The backend exposes a flat file listing (e.g. `FileListing`) with entries:

* `path` – full path,
* `name` – base name,
* `parent` – parent path,
* `kind` – `"file"` or `"dir"`,
* `depth` – depth integer,
* `size`, `mtime`, `content_type`, `etag`.

`createWorkbenchTreeFromListing(listing)`:

* Derives a **root ID** (from `root`, `prefix` or first entry’s parent).
* Normalises paths using `canonicalizePath` (trims trailing slashes).
* Ensures folders are created along the way with `ensureFolder`.
* Populates a root `WorkbenchFileNode` and inserts children:

  * For directories:

    * Ensures a folder node exists.
    * Sets metadata.
  * For files:

    * Creates `WorkbenchFileNode` with:

      * `language` inferred from extension (`json`, `python`, `typescript`, `markdown`, etc.).
      * Metadata from listing.
* Children are sorted via `compareNodes`:

  * Folders before files.
  * Alphabetical by `name` within each group.

Helpers:

* `extractName(path)` – basename from canonicalised path.
* `deriveParent(path)` – parent path or `""` for root.
* `findFileNode(root, id)` – search to find a node by ID.
* `findFirstFile(root)` – find the first file node (folder‑first traversal), used as the default open file.

### Workbench tabs, content, persistence & keyboard interaction

Open files are managed as a tab strip via `useWorkbenchFiles`.

`WorkbenchFileTab`:

```ts
export type WorkbenchFileTabStatus = "loading" | "ready" | "error";

export interface WorkbenchFileTab {
  id: string;
  name: string;
  language?: string;
  initialContent: string;   // last-saved content
  content: string;          // current editor buffer
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

`useWorkbenchFiles` orchestrates:

* The list of open tabs.
* Which tab is currently **active**.
* Lazy loading of file contents (`loadFile`).
* Tracking **dirty** state (`content !== initialContent`).
* Saving and save error states.
* Rearranging and pinning tabs.
* MRU‑style recent tab ordering for quick switching.
* Optional cross‑session persistence in scoped storage.

Persisted structure:

```ts
interface PersistedWorkbenchTabs {
  readonly openTabs: readonly (string | { id: string; pinned?: boolean })[];
  readonly activeTabId?: string | null;
  readonly mru?: readonly string[];
}
```

Behaviour highlights:

* **Hydration**:

  * If persistence is provided:

    * Recreates tabs from the stored snapshot (only for nodes still present in the current tree).
    * Restores pinned state, active tab, and MRU order.
  * Else:

    * Opens `initialActiveFileId` if valid, or the first file in the tree.

* **Tab lifecycle**:

  * `openFile(fileId)` – creates/activates a tab (initially `loading`, content fetched via `loadFile`).
  * `selectTab(fileId)` – activates an existing tab; if it previously failed, transitions back to `"loading"` to retry.
  * `closeTab`, `closeOtherTabs`, `closeTabsToRight`, `closeAllTabs` – mirrors typical IDE behaviour.
  * `moveTab(fileId, targetIndex, { zone })` – drag‑and‑drop reordering, respecting zones:

    * `"pinned"` – dedicated left‑hand group.
    * `"regular"` – standard tabs.

* **Pinning**:

  * `pinTab`, `unpinTab`, `toggleTabPin` – pinned tabs stay at the left and are treated separately for ordering.

* **Recent‑tab navigation**:

  * `selectRecentTab("forward" | "backward")` – cycles through visible tabs using MRU order.
  * Keyboard shortcuts handled in `EditorArea`:

    * `Ctrl/Cmd+Tab` – recent‑tab forward.
    * `Shift+Ctrl/Cmd+Tab` – recent‑tab backward.
    * `Ctrl/Cmd+PageUp/PageDown` – cycle tabs by visual order.
    * `Ctrl/Cmd+W` – close active tab.

* **Loading content**:

  * Tabs start as `status: "loading"`.
  * `loadFile` uses `readConfigFileJson` + React Query (`configsKeys.file`) to fetch:

    * `content` (possibly base64 decoded),
    * `etag` for concurrency.
  * On success: `status: "ready"`, `initialContent = content`, `metadata` updated.
  * On failure: `status: "error"`, `error` message set; `TabsContent` offers a retry affordance.

* **Editing & saving**:

  * `updateContent(fileId, content)`:

    * Updates the buffer and marks tab as ready if it wasn’t.
  * Save path:

    * `beginSavingTab` → call `useSaveConfigFileMutation` (`saveConfigFile`) → `completeSavingTab` or `failSavingTab`.
    * On success:

      * `initialContent` updated to the current buffer.
      * `etag`, `metadata.size`, `metadata.modifiedAt` refreshed.
      * `lastSavedAt` set to now; a success banner (“Saved X”) is shown.
    * On concurrency error (`412`):

      * Tab enters error state.
      * Workbench reloads the latest version via `reloadFileFromServer`.
      * A warning banner explains that the file was reloaded and should be reviewed before saving again.

* **Dirty tracking**:

  * `isDirty` is `true` if any `ready` tab has `content !== initialContent`.
  * Used by the unsaved‑changes guard.

All tab operations are surfaced via `EditorArea`, which:

* Renders the tab strip (pinned + regular).
* Supports drag‑and‑drop reordering via dnd‑kit.
* Provides tab‑level context menus (save, save all, pin/unpin, close variants).
* Provides an overflow “open editors list” menu.
* Mounts a `CodeEditor` for the active tab:

  * `language` and `path` are passed through for syntax highlighting.
  * Save shortcut is forwarded to workbench (`⌘S` / `Ctrl+S`).

### Panel layout, resizing & persistence

The workbench layout can show or hide three side/bottom panels:

* **Explorer** (left)
* **Inspector** (right)
* **Console / Validation** bottom panel

Key details:

* All panel sizes are stored as **fractions** of available width/height and are clamped to min/max pixel bounds:

  * Explorer: `EXPLORER_LIMITS` (min/max width).
  * Inspector: `INSPECTOR_LIMITS` (min/max width).
  * Console: `OUTPUT_LIMITS` (min/max height), plus global minimums for editor and console.
* Widths are recalculated when the container resizes (via `ResizeObserver`), and fractions are re‑clamped.
* Vertical and horizontal `PanelResizeHandle` components drive pointer‑drag sizing:

  * Use `trackPointerDrag` and set cursor (`col-resize` / `row-resize`).
* Console height:

  * Stored as a fraction (`ConsolePanelPreferences`).
  * Hydrated once from scoped storage.
  * Auto‑closes (with a banner message) on very small viewports where maintaining the console would make the editor unreadable.
  * Toggling console, explorer, or inspector emits a custom `window` event `"ade:workbench-layout"` to let observers respond.

Explorer and inspector visibility:

* Explorer visibility toggles via:

  * Activity bar selection (Explorer view).
  * “Hide explorer” icon in the Explorer header.
  * Workbench chrome explorer toggle.
* Inspector is visible only when there is an active file; a toggle in the chrome shows/hides it.

Console open/closed state is reflected in the Config Builder URL (`console=open/closed`) and in console panel preferences.

### Explorer

`Explorer` renders the config file tree:

* Visual style inspired by VS Code (dark/light tokens).
* Always shows the root’s children; root itself is implicit.
* Folders:

  * Expand/collapse state stored in a `Set<string>` of node IDs.
  * `collectExpandedFolderIds` pre‑expands all folders at first render; “Collapse all” keeps the root expanded.
* Files:

  * Styled by extension/language (JSON, Python, TS, etc. get coloured icons).
  * Show **Active** badge for the currently opened tab, **Open** for the rest.
* Context menu on folders:

  * Expand / collapse.
  * Collapse all.
  * Copy path.
* Context menu on files:

  * Open.
  * Close / Close others / Close tabs to the right / Close all (mirrors editor tab operations).
  * Copy path.

Copying file paths uses the Clipboard API when available and falls back to a hidden textarea + `document.execCommand("copy")`.

### Inspector

`Inspector` shows a skinny right‑hand panel with metadata for the active file:

* File:

  * Name, path, language.
* Metadata:

  * Size (formatted to B / KB / MB / GB),
  * Last modified (locale string),
  * Content type,
  * ETag.
* Editor:

  * Load status (`loading`, `ready`, `error`),
  * Dirty flag (based on `content !== initialContent`).

This is intentionally simple, but provides a stable layout for future schema‑aware helpers.

### Console & validation (`BottomPanel`)

The bottom panel (`BottomPanel`) hosts two tabs:

* **Console**
* **Validation**

**Console tab**:

* Displays:

  * An optional **Run summary card** for the latest extraction run.
  * A streaming list of `WorkbenchConsoleLine` entries (timestamp, level, message).
* Levels:

  * `info`, `warning`, `error`, `success` – styled differently for labels, prompts, and message text.
* Run summary card:

  * Shows run ID, status, document name, and worksheet selection.
  * Provides download links:

    * `artifact` (e.g. zipped outputs),
    * `logfile` / telemetry.
  * Summarises:

    * Output files (paths + sizes),
    * Artifact structure (via `ArtifactSummary`),
    * Telemetry (`TelemetrySummary`).

**Validation tab**:

* Shows `WorkbenchValidationState`:

  * `status` – `idle`, `running`, `success`, `error`.
  * `messages` – list of issues with `level` (`error`, `warning`, or informational), `message`, and optional `path`.
  * `lastRunAt` – last validation time.
  * `error` – top‑level error message.
* Renders:

  * A header with a status line and “Last run …”.
  * A list of issues or a fallback message (e.g. “Trigger validation from the workbench header…”).

Validation status strings are human‑readable (e.g. “Validation completed with 3 issues.”).

### Build & validation pipeline

The workbench header includes a **Build environment** control, implemented via `streamBuild`:

* **Primary build button**:

  * Default: “Build environment”.
  * When the backend reports that the environment was **reused**, console and banner messages explain that it is already up to date and hint that you can force a rebuild.
  * If a build is in progress, label changes to “Building…”.
* **Force rebuild**:

  * You can request a forced rebuild by:

    * Holding `Shift` or `Alt` while clicking the build button.
    * Toggling a *force next rebuild* chrome icon.
    * Using the split‑button menu option “Force rebuild now”.
* **Build menu** (split button):

  * “Build / reuse environment” – normal build (reusing current environment when possible).
  * “Force rebuild now” – immediate forced rebuild.
  * “Force rebuild after current build” – queue a forced rebuild after any currently running build.

All build streams are printed to the console via `describeBuildEvent`. Completion status is summarised with banners (success, cancelled, or error).

### Running validation

The **Run validation** button in the header:

* Starts a `validate_only` run via `startRunStream({ validate_only: true }, { mode: "validation" })`.
* Shows progress in the console and updates validation state:

  * On success:

    * Issues from `result.issues` are mapped into `validation.messages`.
    * `lastRunAt` updated.
    * `digest` stored (e.g. content hash).
  * On error:

    * Status `error`, message stored in `validation.error`.

While a validation is running, further validations are disabled until completion.

### Running extraction from the workbench

The **Run extraction** button opens a `RunExtractionDialog`:

* Fetches up to 50 most‑recent documents for the workspace via:

  ```ts
  GET /api/v1/workspaces/{workspace_id}/documents?sort=-created_at&page_size=50
  ```

* Lets the user:

  * Select a document.
  * Optionally select worksheet(s) for spreadsheet inputs:

    * Worksheet metadata loaded via `fetchDocumentSheets`.
    * Selection is de‑duplicated and validated against the available sheets.
    * “Use all worksheets” resets selection to process the entire file.

* When the user confirms:

  * Calls `startRunStream` with:

    * `input_document_id`,
    * `input_sheet_names` (list),
    * `input_sheet_name` (single name when only one is selected).
  * Closes the dialog and streams events into the console.

On run completion:

* The latest run summary is populated (outputs, artifact, telemetry).
* Console banners summarise success/failure.

### Editor theme preference (`useEditorThemePreference`)

Workbench editor theme honours user preferences:

```ts
export type EditorThemePreference = "system" | "light" | "dark";
export type EditorThemeId = "ade-dark" | "vs-light";
```

Behaviour:

* Preference is stored in scoped storage:

  ```ts
  `ade.ui.workspace.${workspaceId}.config.${configId}.editor-theme`
  ```

* System dark mode is detected via:

  ```ts
  window.matchMedia("(prefers-color-scheme: dark)");
  ```

* Resolved theme:

  ```ts
  pref === "dark" || (pref === "system" && systemPrefersDark)
    ? "ade-dark"
    : "vs-light";
  ```

`useEditorThemePreference` returns `{ preference, resolvedTheme, setPreference }` and reacts to both system theme changes and storage updates. The workbench header exposes a context menu for switching between System, Light, and Dark themes.

### Unsaved‑changes guard (`useUnsavedChangesGuard`)

Config Builder integrates a **navigation guard** for unsaved changes:

```ts
interface UseUnsavedChangesGuardOptions {
  readonly isDirty: boolean;
  readonly confirm?: (message: string) => boolean;
  readonly message?: string;
  readonly shouldBypassNavigation?: () => boolean;
}
```

Behaviour:

* Registers a navigation blocker via `useNavigationBlocker` when `isDirty` is true:

  * If `shouldBypassNavigation()` returns true, navigation is allowed.
  * Navigations that do not change the pathname are allowed.
  * Otherwise, calls `confirm(message)` (defaults to `window.confirm`).
* Adds a `beforeunload` handler while dirty:

  * Shows a native prompt when the user tries to close/refresh the tab.
* Default prompt:

  > "You have unsaved changes in the config editor. Are you sure you want to leave?"

The workbench receives a `shouldBypassUnsavedGuard` callback from `useWorkbenchWindow` so certain transitions (e.g. closing the window after a successful save) can skip the prompt.

---

## Workspace Settings

The **Settings** section holds workspace‑specific configuration. It is tabbed, and the active tab is reflected in the `view` query parameter.

Code reinforces:

* The `Settings` route uses `useSearchParams` to:

  * Interpret `view` as `general`, `members`, or `roles`.
  * Normalise invalid values back to `general`.
  * Keep the tab selection in sync with the URL by calling `setSearchParams` with `{ replace: true }`.
* Tabs lazily mount their content so inactive tabs do not incur unnecessary data fetching.

### Workbench return path (Settings ↔ Config Builder / Documents / Runs)

To keep flows smooth between operational views and config editing, a helper key is used:

```ts
export function getWorkbenchReturnPathStorageKey(workspaceId: string) {
  return `ade.ui.workspace.${workspaceId}.workbench.returnPath`;
}
```

When entering the workbench from any workspace section:

* The app can store the originating URL (e.g. filtered Documents view, Runs query, or Settings tab).

When exiting the workbench:

* ADE Web can navigate back to that stored path and clear the key, so “back to where I was” feels predictable.

---

## Notifications & keyboard shortcuts

Notifications:

* **Toasts** – short‑lived events (saves, minor warnings).
* **Banners** – persistent messages for safe mode, connectivity, console‑related warnings (e.g. console auto‑closed due to viewport size).

Workbench‑specific banner scopes are used so messages (e.g. around console collapse or build reuse) can be dismissed or persisted independently.

Keyboard shortcuts (non‑exhaustive):

* **Global**

  * `⌘K` / `Ctrl+K` – global search / workspace search.
  * (Elsewhere in the app: shortcuts for document upload, deletion, etc., where implemented.)

* **Workbench**

  * `⌘S` / `Ctrl+S` – save active editor tab.
  * `⌘B` / `Ctrl+B` – build / reuse environment.
  * `Shift+⌘B` / `Ctrl+Shift+B` – force rebuild (equivalent to holding Shift).
  * `⌘W` / `Ctrl+W` – close active editor tab.
  * `⌘Tab` / `Ctrl+Tab` – recent‑tab forward (within workbench).
  * `Shift+⌘Tab` / `Shift+Ctrl+Tab` – recent‑tab backward.
  * `⌘PageUp/PageDown` / `Ctrl+PageUp/PageDown` – cycle tabs by visual order.

Where browser or OS behaviour conflicts, ADE Web is careful to only intercept shortcuts when the editor has focus and the target element is not an input/textarea/content‑editable.

---

## Backend expectations (high‑level)

Contracts for:

* Auth and sessions,
* Workspaces, users & invitations,
* Roles & permissions,
* Documents & runs,
* Config packages & versions,
* Safe mode,
* Security (CSRF, cookies, CORS),

are as described in the earlier conceptual sections.

The workbench‑specific additions imply:

* A **file listing endpoint** that can produce `FileListing`‑like structures with:

  * Paths, names, parents, depth, kind, size, mtime, content_type, etag.

* **File content endpoints**:

  * To read, write, rename, and delete files in a config package version.
  * To use ETags or similar for optimistic concurrency control.

* **Run APIs** that support:

  * Validation‑only runs for a configuration.
  * Runs bound to a specific input document and optional sheet names.
  * Streaming NDJSON events for both builds and runs.

* **Artifacts & telemetry** endpoints:

  * Listing output files for a run.
  * Downloading artifacts.
  * Downloading or streaming telemetry events.

As long as these contracts are honoured, ADE Web can be re‑used with different backend implementations without changing the user experience described here.

---

## Front‑end architecture & tooling

### Entry point (`main.tsx`)

`main.tsx` mounts `<App />` into `#root` inside `React.StrictMode`:

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
* `ScreenSwitch` (top‑level route switch).

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

* A single `QueryClient` is created once per app instance using `useState`.
* `ReactQueryDevtools` is included in development builds (`import.meta.env.DEV`).

### Build tooling (Vite)

`apps/ade-web/vite.config.ts`:

* Uses:

  * `@tailwindcss/vite` – Tailwind integration.
  * `@vitejs/plugin-react` – React refresh and JSX transform.
  * `vite-tsconfig-paths` – align TS path aliases with Vite resolve.

Aliases:

* `@app` → `src/app`
* `@features` → `src/screens`
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

This arrangement allows:

* Frontend and backend running on separate ports during development.
* Avoiding CORS pain by proxying API calls through the dev server.

### Testing (Vitest)

`apps/ade-web/vitest.config.ts`:

* Module resolution aliases mirror Vite’s (`@app`, `@features`, etc.).
* Test config:

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
* A single global setup (e.g. for mocking fetch, setting global config).
* ESBuild‑powered TS + JSX transform with automatic JSX runtime.

---

## Summary

ADE Web is the operational and configuration console for Automatic Data Extractor:

* **Analysts** use it to upload documents, run extractions, inspect runs, and download outputs.
* **Workspace owners / engineers** use it to evolve Python‑based config packages, validate and test changes, and safely roll out new versions.
* **Admins** use it to manage workspaces, members, roles, SSO hints, and safe mode.

This README captures:

* The **conceptual model** (workspaces, documents, runs, configs, safe mode, roles),
* The **navigation and URL‑state conventions** (custom history, search params, deep linking),
* The **workbench model** for config packages (file tree, tabs, layout, editor theme, unsaved changes, build & run integration),
* And the **backend contracts** ADE Web expects.

As long as backend implementations respect these concepts and contracts, ADE Web can remain stable, even as internals and infrastructure evolve.
```

# apps/ade-web/src/app/App.tsx
```tsx
import { NavProvider, useLocation } from "@app/nav/history";

import { AppProviders } from "./AppProviders";
import HomeScreen from "@features/Home";
import LoginScreen from "@features/Login";
import AuthCallbackScreen from "@features/AuthCallback";
import SetupScreen from "@features/Setup";
import WorkspacesScreen from "@features/Workspaces";
import WorkspaceCreateScreen from "@features/Workspaces/New";
import WorkspaceScreen from "@features/Workspace";
import LogoutScreen from "@features/Logout";
import NotFoundScreen from "@features/NotFound";

export function App() {
  return (
    <NavProvider>
      <AppProviders>
        <ScreenSwitch />
      </AppProviders>
    </NavProvider>
  );
}

export function ScreenSwitch() {
  const location = useLocation();
  const normalized = normalizePathname(location.pathname);
  const segments = normalized.split("/").filter(Boolean);

  if (segments.length === 0) {
    return <HomeScreen />;
  }

  const [first, second] = segments;

  switch (first) {
    case "login":
      return <LoginScreen />;
    case "logout":
      return <LogoutScreen />;
    case "auth":
      if (second === "callback") {
        return <AuthCallbackScreen />;
      }
      break;
    case "setup":
      return <SetupScreen />;
    case "workspaces":
      if (!second) {
        return <WorkspacesScreen />;
      }
      if (second === "new") {
        return <WorkspaceCreateScreen />;
      }
      return <WorkspaceScreen />;
    default:
      break;
  }

  return <NotFoundScreen />;
}

export function normalizePathname(pathname: string) {
  if (!pathname || pathname === "/") {
    return "/";
  }
  return pathname.endsWith("/") && pathname.length > 1 ? pathname.slice(0, -1) : pathname;
}

export default App;
```

# apps/ade-web/src/app/AppProviders.tsx
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import type { ReactNode } from "react";
import { useState } from "react";

interface AppProvidersProps {
  readonly children: ReactNode;
}

export function AppProviders({ children }: AppProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV ? (
        <ReactQueryDevtools initialIsOpen={false} />
      ) : null}
    </QueryClientProvider>
  );
}
```

# apps/ade-web/src/app/nav/Link.tsx
```tsx
import React from "react";
import { useNavigate, useLocation } from "./history";

type LinkProps = React.PropsWithChildren<{
  to: string;
  replace?: boolean;
  className?: string;
  title?: string;
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
}>;

export function Link({ to, replace, className, title, children, onClick }: LinkProps) {
  const navigate = useNavigate();
  return (
    <a
      href={to}
      className={className}
      title={title}
      onClick={(event) => {
        onClick?.(event);
        if (
          event.defaultPrevented ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }
        event.preventDefault();
        navigate(to, { replace });
      }}
    >
      {children}
    </a>
  );
}

type NavLinkRenderArgs = { isActive: boolean };
type NavLinkClassName = string | ((args: NavLinkRenderArgs) => string);
type Renderable = React.ReactNode | ((args: NavLinkRenderArgs) => React.ReactNode);
type NavLinkProps = {
  to: string;
  end?: boolean;
  className?: NavLinkClassName;
  title?: string;
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
  children: Renderable;
};

export function NavLink({ to, end, className, children, title, onClick }: NavLinkProps) {
  const { pathname } = useLocation();
  const isActive = end
    ? pathname === to
    : pathname === to || pathname.startsWith(`${to}/`);
  const computedClassName =
    typeof className === "function" ? className({ isActive }) : className;
  const renderedChildren =
    typeof children === "function" ? children({ isActive }) : children;

  return (
    <Link to={to} className={computedClassName} title={title} onClick={onClick}>
      {renderedChildren}
    </Link>
  );
}
```

# apps/ade-web/src/app/nav/history.tsx
```tsx
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export type LocationLike = { pathname: string; search: string; hash: string };
type NavigateOptions = { replace?: boolean };

export type NavigationIntent = {
  readonly to: string;
  readonly location: LocationLike;
  readonly kind: "push" | "replace" | "pop";
};

export type NavigationBlocker = (intent: NavigationIntent) => boolean;

type NavContextValue = {
  location: LocationLike;
  navigate: (to: string, opts?: NavigateOptions) => void;
  registerBlocker: (blocker: NavigationBlocker) => () => void;
};

const NavCtx = createContext<NavContextValue | null>(null);

export function NavProvider({ children }: { children: React.ReactNode }) {
  const [loc, setLoc] = useState<LocationLike>(() => ({
    pathname: window.location.pathname,
    search: window.location.search,
    hash: window.location.hash,
  }));
  const blockersRef = useRef(new Set<NavigationBlocker>());
  const latestLocationRef = useRef<LocationLike>(loc);

  useEffect(() => {
    latestLocationRef.current = loc;
  }, [loc]);

  const runBlockers = useCallback(
    (intent: NavigationIntent) => {
      for (const blocker of blockersRef.current) {
        if (blocker(intent) === false) {
          return false;
        }
      }
      return true;
    },
    [],
  );

  useEffect(() => {
    const onPop = () => {
      const nextLocation: LocationLike = {
        pathname: window.location.pathname,
        search: window.location.search,
        hash: window.location.hash,
      };
      const target = `${nextLocation.pathname}${nextLocation.search}${nextLocation.hash}`;
      const allowed = runBlockers({ kind: "pop", to: target, location: nextLocation });
      if (!allowed) {
        const current = latestLocationRef.current;
        window.history.pushState(null, "", `${current.pathname}${current.search}${current.hash}`);
        return;
      }
      setLoc(nextLocation);
    };

    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [runBlockers]);

  const registerBlocker = useCallback((blocker: NavigationBlocker) => {
    blockersRef.current.add(blocker);
    return () => {
      blockersRef.current.delete(blocker);
    };
  }, []);

  const navigate = useCallback(
    (to: string, opts?: NavigateOptions) => {
      const url = new URL(to, window.location.origin);
      const nextLocation: LocationLike = {
        pathname: url.pathname,
        search: url.search,
        hash: url.hash,
      };
      const target = `${nextLocation.pathname}${nextLocation.search}${nextLocation.hash}`;
      const kind: NavigationIntent["kind"] = opts?.replace ? "replace" : "push";
      const allowed = runBlockers({ kind, to: target, location: nextLocation });
      if (!allowed) {
        return;
      }
      if (opts?.replace) {
        window.history.replaceState(null, "", target);
      } else {
        window.history.pushState(null, "", target);
      }
      window.dispatchEvent(new PopStateEvent("popstate"));
    },
    [runBlockers],
  );

  const value = useMemo(
    () => ({
      location: loc,
      navigate,
      registerBlocker,
    }),
    [loc, navigate, registerBlocker],
  );

  return <NavCtx.Provider value={value}>{children}</NavCtx.Provider>;
}

export function useLocation() {
  const ctx = useContext(NavCtx);
  if (!ctx) {
    throw new Error("useLocation must be used within NavProvider");
  }
  return ctx.location;
}

export function useNavigate() {
  const ctx = useContext(NavCtx);
  if (!ctx) {
    throw new Error("useNavigate must be used within NavProvider");
  }
  return ctx.navigate;
}

export function useNavigationBlocker(blocker: NavigationBlocker, when = true) {
  const ctx = useContext(NavCtx);
  if (!ctx) {
    throw new Error("useNavigationBlocker must be used within NavProvider");
  }

  useEffect(() => {
    if (!when) {
      return;
    }
    return ctx.registerBlocker(blocker);
  }, [blocker, ctx, when]);
}
```

# apps/ade-web/src/app/nav/urlState.ts
```typescript
import { createContext, createElement, useCallback, useContext, useMemo, type ReactNode } from "react";

import { useLocation, useNavigate } from "./history";

type SearchParamPrimitive = string | number | boolean;
type SearchParamsRecordValue =
  | SearchParamPrimitive
  | readonly SearchParamPrimitive[]
  | null
  | undefined;
type SearchParamsRecord = Record<string, SearchParamsRecordValue>;

export type SearchParamsInit =
  | string
  | string[][]
  | URLSearchParams
  | SearchParamsRecord;

export function toURLSearchParams(init: SearchParamsInit): URLSearchParams {
  if (init instanceof URLSearchParams) {
    return new URLSearchParams(init);
  }

  if (typeof init === "string" || Array.isArray(init)) {
    return new URLSearchParams(init as string | string[][]);
  }

  const params = new URLSearchParams();

  for (const [key, rawValue] of Object.entries(init)) {
    if (rawValue == null) {
      continue;
    }

    const values = Array.isArray(rawValue) ? rawValue : [rawValue];
    for (const value of values) {
      if (value == null) {
        continue;
      }
      params.append(key, String(value));
    }
  }

  return params;
}

export function getParam(search: string, key: string) {
  return new URLSearchParams(search).get(key) ?? undefined;
}

type ParamPatchValue = string | number | boolean | null | undefined;

export function setParams(url: URL, patch: Record<string, ParamPatchValue>) {
  const next = new URL(url.toString());
  const query = new URLSearchParams(next.search);

  for (const [paramKey, value] of Object.entries(patch)) {
    if (value == null || value === "") {
      query.delete(paramKey);
    } else {
      query.set(paramKey, String(value));
    }
  }

  next.search = query.toString() ? `?${query}` : "";
  return `${next.pathname}${next.search}${next.hash}`;
}

export type SetSearchParamsInit = SearchParamsInit | ((prev: URLSearchParams) => SearchParamsInit);
export type SetSearchParamsOptions = { replace?: boolean };

interface SearchParamsOverrideValue {
  readonly params: URLSearchParams;
  readonly setSearchParams: (init: SetSearchParamsInit, options?: SetSearchParamsOptions) => void;
}

const SearchParamsOverrideContext = createContext<SearchParamsOverrideValue | null>(null);

export function SearchParamsOverrideProvider({
  value,
  children,
}: {
  readonly value: SearchParamsOverrideValue | null;
  readonly children: ReactNode;
}) {
  return createElement(SearchParamsOverrideContext.Provider, { value }, children);
}

export function useSearchParams(): [URLSearchParams, (init: SetSearchParamsInit, options?: SetSearchParamsOptions) => void] {
  const override = useContext(SearchParamsOverrideContext);
  const location = useLocation();
  const navigate = useNavigate();

  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);

  const setSearchParams = useCallback(
    (init: SetSearchParamsInit, options?: SetSearchParamsOptions) => {
      const nextInit = typeof init === "function" ? init(new URLSearchParams(params)) : init;
      const next = toURLSearchParams(nextInit);
      const search = next.toString();
      const target = `${location.pathname}${search ? `?${search}` : ""}${location.hash}`;
      navigate(target, { replace: options?.replace });
    },
    [location.hash, location.pathname, navigate, params],
  );

  return [override?.params ?? params, override?.setSearchParams ?? setSearchParams];
}

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

export interface ConfigBuilderSearchSnapshot extends ConfigBuilderSearchState {
  readonly present: {
    readonly tab: boolean;
    readonly pane: boolean;
    readonly console: boolean;
    readonly view: boolean;
    readonly file: boolean;
  };
}

export const DEFAULT_CONFIG_BUILDER_SEARCH: ConfigBuilderSearchState = {
  tab: "editor",
  pane: "console",
  console: "closed",
  view: "editor",
};

const CONFIG_BUILDER_KEYS = ["tab", "pane", "console", "view", "file", "path"] as const;

function normalizeConsole(value: string | null): ConfigBuilderConsole {
  return value === "open" ? "open" : "closed";
}

function normalizePane(value: string | null): ConfigBuilderPane {
  if (value === "validation" || value === "problems") {
    return "validation";
  }
  return "console";
}

function normalizeView(value: string | null): ConfigBuilderView {
  return value === "split" || value === "zen" ? value : "editor";
}

export function readConfigBuilderSearch(
  source: URLSearchParams | string,
): ConfigBuilderSearchSnapshot {
  const params = source instanceof URLSearchParams ? source : new URLSearchParams(source);
  const tabRaw = params.get("tab");
  const paneRaw = params.get("pane");
  const consoleRaw = params.get("console");
  const viewRaw = params.get("view");
  const fileRaw = params.get("file") ?? params.get("path");

  const state: ConfigBuilderSearchState = {
    tab: tabRaw === "editor" ? "editor" : DEFAULT_CONFIG_BUILDER_SEARCH.tab,
    pane: normalizePane(paneRaw),
    console: normalizeConsole(consoleRaw),
    view: normalizeView(viewRaw),
    file: fileRaw ?? undefined,
  };

  return {
    ...state,
    present: {
      tab: params.has("tab"),
      pane: params.has("pane"),
      console: params.has("console"),
      view: params.has("view"),
      file: params.has("file") || params.has("path"),
    },
  };
}

export function mergeConfigBuilderSearch(
  current: URLSearchParams,
  patch: Partial<ConfigBuilderSearchState>,
): URLSearchParams {
  const existing = readConfigBuilderSearch(current);
  const nextState: ConfigBuilderSearchState = {
    ...DEFAULT_CONFIG_BUILDER_SEARCH,
    ...existing,
    ...patch,
  };

  const next = new URLSearchParams(current);
  for (const key of CONFIG_BUILDER_KEYS) {
    next.delete(key);
  }

  if (nextState.tab !== DEFAULT_CONFIG_BUILDER_SEARCH.tab) {
    next.set("tab", nextState.tab);
  }
  if (nextState.pane !== DEFAULT_CONFIG_BUILDER_SEARCH.pane) {
    next.set("pane", nextState.pane);
  }
  if (nextState.console !== DEFAULT_CONFIG_BUILDER_SEARCH.console) {
    next.set("console", nextState.console);
  }
  if (nextState.view !== DEFAULT_CONFIG_BUILDER_SEARCH.view) {
    next.set("view", nextState.view);
  }
  if (nextState.file && nextState.file.length > 0) {
    next.set("file", nextState.file);
  }

  return next;
}
```

# apps/ade-web/src/main.tsx
```tsx
import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "@app/App";
import "@app/app.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/detail/index.tsx
```tsx
import { useMemo } from "react";

import { useNavigate } from "@app/nav/history";

import { Button } from "@ui/Button";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@features/Workspace/context/WorkspaceContext";

import { useConfigsQuery } from "@shared/configs";

interface WorkspaceConfigRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function WorkspaceConfigRoute({ params }: WorkspaceConfigRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const configId = params?.configId;

  const configsQuery = useConfigsQuery({ workspaceId: workspace.id });

  const config = useMemo(
    () => configsQuery.data?.items.find((item) => item.config_id === configId),
    [configsQuery.data, configId],
  );

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Configuration not found"
        description="Pick a configuration from the list to view its details."
      />
    );
  }

  if (configsQuery.isLoading) {
    return (
      <PageState
        variant="loading"
        title="Loading configuration"
        description="Fetching configuration details."
      />
    );
  }

  if (!config) {
    return (
      <PageState
        variant="error"
        title="Configuration unavailable"
        description="The selected configuration could not be found. It may have been deleted."
      />
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Configuration</p>
            <h1 className="text-xl font-semibold text-slate-900">{config.display_name}</h1>
          </div>
          <Button
            variant="secondary"
            onClick={() =>
              navigate(`/workspaces/${workspace.id}/config-builder/${encodeURIComponent(config.config_id)}/editor`)
            }
          >
            Open editor
          </Button>
        </header>
        <dl className="grid gap-4 md:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Config ID</dt>
            <dd className="text-sm text-slate-700">{config.config_id}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</dt>
            <dd className="text-sm capitalize text-slate-700">{config.status.toLowerCase()}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Updated</dt>
            <dd className="text-sm text-slate-700">{new Date(config.updated_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Active version</dt>
            <dd className="text-sm text-slate-700">
              {("active_version" in config ? (config as { active_version?: number | null }).active_version : null) ??
                config.config_version ??
                "—"}
            </dd>
          </div>
        </dl>
      </section>
      <section className="flex-1 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6">
        <h2 className="text-base font-semibold text-slate-800">Overview</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          The refreshed config workbench will eventually surface manifest summaries, validation history, and deployment metrics
          here. For now this page offers a quick launch point into the editor while we rebuild the experience.
        </p>
      </section>
    </div>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx
```tsx
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";
import clsx from "clsx";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPortal } from "react-dom";

import { ActivityBar, type ActivityBarView } from "./components/ActivityBar";
import { BottomPanel, type WorkbenchRunSummary } from "./components/BottomPanel";
import { EditorArea } from "./components/EditorArea";
import { Explorer } from "./components/Explorer";
import { Inspector } from "./components/Inspector";
import { PanelResizeHandle } from "./components/PanelResizeHandle";
import { useWorkbenchFiles } from "./state/useWorkbenchFiles";
import { useWorkbenchUrlState } from "./state/useWorkbenchUrlState";
import { useUnsavedChangesGuard } from "./state/useUnsavedChangesGuard";
import { useEditorThemePreference } from "./state/useEditorThemePreference";
import type { EditorThemePreference } from "./state/useEditorThemePreference";
import type { WorkbenchConsoleLine, WorkbenchDataSeed, WorkbenchValidationState } from "./types";
import { clamp, trackPointerDrag } from "./utils/drag";
import { createWorkbenchTreeFromListing } from "./utils/tree";

import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";
import { SplitButton } from "@ui/SplitButton";
import { PageState } from "@ui/PageState";

import { useConfigFilesQuery, useSaveConfigFileMutation } from "@shared/configs/hooks/useConfigFiles";
import { configsKeys } from "@shared/configs/keys";
import { readConfigFileJson } from "@shared/configs/api";
import type { FileReadJson } from "@shared/configs/types";
import { useValidateConfigurationMutation } from "@shared/configs/hooks/useValidateConfiguration";
import { createScopedStorage } from "@shared/storage";
import type { ConfigBuilderConsole } from "@app/nav/urlState";
import { ApiError } from "@shared/api";
import { streamBuild } from "@shared/builds/api";
import {
  fetchRunArtifact,
  fetchRunOutputs,
  fetchRunTelemetry,
  streamRun,
  type RunStreamOptions,
} from "@shared/runs/api";
import { isTelemetryEnvelope, type RunStatus } from "@shared/runs/types";
import type { components } from "@schema";
import { fetchDocumentSheets, type DocumentSheet } from "@shared/documents";
import { client } from "@shared/api/client";
import { describeBuildEvent, describeRunEvent, formatConsoleTimestamp } from "./utils/console";
import { useNotifications, type NotificationIntent } from "@shared/notifications";
import { Select } from "@ui/Select";
import { Button } from "@ui/Button";
import { Alert } from "@ui/Alert";

const EXPLORER_LIMITS = { min: 200, max: 420 } as const;
const INSPECTOR_LIMITS = { min: 260, max: 420 } as const;
const OUTPUT_LIMITS = { min: 140, max: 420 } as const;
const MIN_EDITOR_HEIGHT = 320;
const MIN_CONSOLE_HEIGHT = 140;
const DEFAULT_CONSOLE_HEIGHT = 220;
const MAX_CONSOLE_LINES = 400;
const OUTPUT_HANDLE_THICKNESS = 4; // matches h-1 Tailwind utility on PanelResizeHandle
const ACTIVITY_BAR_WIDTH = 56; // w-14
const CONSOLE_COLLAPSE_MESSAGE =
  "Console closed to keep the editor readable on this screen size. Resize the window or collapse other panes to reopen it.";
const buildTabStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.tabs`;
const buildConsoleStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.console`;
const buildEditorThemeStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.editor-theme`;

const THEME_MENU_OPTIONS: Array<{ value: EditorThemePreference; label: string }> = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const ACTIVITY_LABELS: Record<ActivityBarView, string> = {
  explorer: "",
  search: "Search coming soon",
  scm: "Source Control coming soon",
  extensions: "Extensions coming soon",
};

interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number;
  readonly state: ConfigBuilderConsole;
}

type SideBounds = {
  readonly minPx: number;
  readonly maxPx: number;
  readonly minFrac: number;
  readonly maxFrac: number;
};

type BuildTriggerOptions = {
  readonly force?: boolean;
  readonly wait?: boolean;
  readonly source?: "button" | "menu" | "shortcut";
};

type WorkbenchWindowState = "restored" | "maximized";

type DocumentRecord = components["schemas"]["DocumentOut"];

interface RunStreamMetadata {
  readonly mode: "validation" | "extraction";
  readonly documentId?: string;
  readonly documentName?: string;
  readonly sheetNames?: readonly string[];
}

interface WorkbenchProps {
  readonly workspaceId: string;
  readonly configId: string;
  readonly configName: string;
  readonly seed?: WorkbenchDataSeed;
  readonly windowState: WorkbenchWindowState;
  readonly onMinimizeWindow: () => void;
  readonly onMaximizeWindow: () => void;
  readonly onRestoreWindow: () => void;
  readonly onCloseWorkbench: () => void;
  readonly shouldBypassUnsavedGuard?: () => boolean;
}

export function Workbench({
  workspaceId,
  configId,
  configName,
  seed,
  windowState,
  onMinimizeWindow,
  onMaximizeWindow,
  onRestoreWindow,
  onCloseWorkbench,
  shouldBypassUnsavedGuard,
}: WorkbenchProps) {
  const queryClient = useQueryClient();
  const {
    fileId,
    pane,
    console: consoleState,
    consoleExplicit,
    setFileId,
    setPane,
    setConsole,
  } = useWorkbenchUrlState();

  const usingSeed = Boolean(seed);
  const filesQuery = useConfigFilesQuery({
    workspaceId,
    configId,
    depth: "infinity",
    sort: "path",
    order: "asc",
    enabled: !usingSeed,
  });

  const tree = useMemo(() => {
    if (seed) {
      return seed.tree;
    }
    if (!filesQuery.data) {
      return null;
    }
    return createWorkbenchTreeFromListing(filesQuery.data);
  }, [seed, filesQuery.data]);

  const [consoleLines, setConsoleLines] = useState<WorkbenchConsoleLine[]>(() =>
    seed?.console ? seed.console.slice(-MAX_CONSOLE_LINES) : [],
  );

  useEffect(() => {
    if (!seed?.console) {
      return;
    }
    setConsoleLines(seed.console.slice(-MAX_CONSOLE_LINES));
  }, [seed?.console]);

  const [validationState, setValidationState] = useState<WorkbenchValidationState>(() => ({
    status: seed?.validation?.length ? "success" : "idle",
    messages: seed?.validation ?? [],
    lastRunAt: seed?.validation?.length ? new Date().toISOString() : undefined,
    error: null,
    digest: null,
  }));

  const consoleStreamRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);
  type ActiveStream =
    | {
        readonly kind: "build";
        readonly startedAt: string;
        readonly metadata?: {
          readonly force?: boolean;
          readonly wait?: boolean;
        };
      }
    | {
        readonly kind: "run";
        readonly startedAt: string;
        readonly metadata?: RunStreamMetadata;
      };
  const [activeStream, setActiveStream] = useState<ActiveStream | null>(null);

  const [latestRun, setLatestRun] = useState<WorkbenchRunSummary | null>(null);
  const [runDialogOpen, setRunDialogOpen] = useState(false);

  const resetConsole = useCallback(
    (message: string) => {
      if (!isMountedRef.current) {
        return;
      }
      const timestamp = formatConsoleTimestamp(new Date());
      setConsoleLines([{ level: "info", message, timestamp }]);
    },
    [setConsoleLines],
  );

  const appendConsoleLine = useCallback(
    (line: WorkbenchConsoleLine) => {
      if (!isMountedRef.current) {
        return;
      }
      setConsoleLines((prev) => {
        const next = [...prev, line];
        return next.length > MAX_CONSOLE_LINES ? next.slice(next.length - MAX_CONSOLE_LINES) : next;
      });
    },
    [setConsoleLines],
  );

  useEffect(() => {
    if (seed?.validation) {
      setValidationState({
        status: "success",
        messages: seed.validation,
        lastRunAt: new Date().toISOString(),
        error: null,
        digest: null,
      });
    }
  }, [seed?.validation]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      consoleStreamRef.current?.abort();
    };
  }, []);

  const validateConfiguration = useValidateConfigurationMutation(workspaceId, configId);

  const tabPersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildTabStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const consolePersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildConsoleStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const initialConsolePrefsRef = useRef<ConsolePanelPreferences | Record<string, unknown> | null>(null);
  if (!initialConsolePrefsRef.current && consolePersistence) {
    initialConsolePrefsRef.current =
      (consolePersistence.get<unknown>() as ConsolePanelPreferences | Record<string, unknown> | null) ?? null;
  }
  const editorTheme = useEditorThemePreference(buildEditorThemeStorageKey(workspaceId, configId));
  const menuAppearance = editorTheme.resolvedTheme === "vs-light" ? "light" : "dark";
  const validationLabel = validationState.lastRunAt ? `Last run ${formatRelative(validationState.lastRunAt)}` : undefined;

  const [explorer, setExplorer] = useState({ collapsed: false, fraction: 280 / 1200 });
  const [inspector, setInspector] = useState({ collapsed: false, fraction: 300 / 1200 });
  const [consoleFraction, setConsoleFraction] = useState<number | null>(null);
  const [hasHydratedConsoleState, setHasHydratedConsoleState] = useState(false);
  const [layoutSize, setLayoutSize] = useState({ width: 0, height: 0 });
  const [paneAreaEl, setPaneAreaEl] = useState<HTMLDivElement | null>(null);
  const [activityView, setActivityView] = useState<ActivityBarView>("explorer");
  const [settingsMenu, setSettingsMenu] = useState<{ x: number; y: number } | null>(null);
  const [buildMenu, setBuildMenu] = useState<{ x: number; y: number } | null>(null);
  const [forceNextBuild, setForceNextBuild] = useState(false);
  const [forceModifierActive, setForceModifierActive] = useState(false);
  const [isResizingConsole, setIsResizingConsole] = useState(false);
  const { notifyBanner, dismissScope } = useNotifications();
  const consoleBannerScope = useMemo(
    () => `workbench-console:${workspaceId}:${configId}`,
    [workspaceId, configId],
  );
  const showConsoleBanner = useCallback(
    (message: string, options?: { intent?: NotificationIntent; duration?: number | null }) => {
      notifyBanner({
        title: message,
        intent: options?.intent ?? "info",
        duration: options?.duration ?? 6000,
        dismissible: true,
        scope: consoleBannerScope,
        persistKey: consoleBannerScope,
      });
    },
    [notifyBanner, consoleBannerScope],
  );
  const clearConsoleBanners = useCallback(() => {
    dismissScope(consoleBannerScope, "banner");
  }, [dismissScope, consoleBannerScope]);

  const pushConsoleError = useCallback(
    (error: unknown) => {
      if (!isMountedRef.current) {
        return;
      }
      const message = describeError(error);
      appendConsoleLine({ level: "error", message, timestamp: formatConsoleTimestamp(new Date()) });
      showConsoleBanner(message, { intent: "danger", duration: null });
    },
    [appendConsoleLine, showConsoleBanner],
  );

  const isMaximized = windowState === "maximized";
  const isMacPlatform = typeof navigator !== "undefined" ? /mac/i.test(navigator.platform) : false;
  const handleCloseWorkbench = useCallback(() => {
    onCloseWorkbench();
  }, [onCloseWorkbench]);
  const openBuildMenu = useCallback((position: { x: number; y: number }) => {
    setBuildMenu(position);
  }, []);
  const closeBuildMenu = useCallback(() => setBuildMenu(null), []);
  const showExplorerPane = !explorer.collapsed;

  const loadFile = useCallback(
    async (path: string) => {
      if (seed) {
        return { content: seed.content[path] ?? "", etag: null };
      }
      const payload = await queryClient.fetchQuery({
        queryKey: configsKeys.file(workspaceId, configId, path),
        queryFn: ({ signal }) => readConfigFileJson(workspaceId, configId, path, signal),
      });
      if (!payload) {
        throw new Error("File could not be loaded.");
      }
      return { content: decodeFileContent(payload), etag: payload.etag ?? null };
    },
    [seed, queryClient, workspaceId, configId],
  );

  const files = useWorkbenchFiles({
    tree,
    initialActiveFileId: fileId,
    loadFile,
    persistence: tabPersistence ?? undefined,
  });
  const saveConfigFile = useSaveConfigFileMutation(workspaceId, configId);
  const reloadFileFromServer = useCallback(
    async (fileId: string) => {
      if (usingSeed) {
        return null;
      }
      const payload = await queryClient.fetchQuery({
        queryKey: configsKeys.file(workspaceId, configId, fileId),
        queryFn: ({ signal }) => readConfigFileJson(workspaceId, configId, fileId, signal),
      });
      const content = decodeFileContent(payload);
      files.replaceTabContent(fileId, {
        content,
        etag: payload.etag ?? null,
        metadata: {
          size: payload.size ?? null,
          modifiedAt: payload.mtime ?? null,
          contentType:
            payload.content_type ??
            files.tabs.find((tab) => tab.id === fileId)?.metadata?.contentType ??
            null,
          etag: payload.etag ?? null,
        },
      });
      return payload;
    },
    [usingSeed, queryClient, workspaceId, configId, files],
  );

  useUnsavedChangesGuard({
    isDirty: files.isDirty,
    shouldBypassNavigation: shouldBypassUnsavedGuard,
  });

  const handleMinimizeWindow = useCallback(() => {
    onMinimizeWindow();
  }, [onMinimizeWindow]);

  const handleToggleMaximize = useCallback(() => {
    if (isMaximized) {
      onRestoreWindow();
    } else {
      onMaximizeWindow();
    }
  }, [isMaximized, onMaximizeWindow, onRestoreWindow]);

  const handleToggleForceNextBuild = useCallback(() => {
    setForceNextBuild((current) => !current);
  }, []);
  const outputCollapsed = consoleState !== "open";
  const dirtyTabs = useMemo(
    () => files.tabs.filter((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [files.tabs],
  );
  const isSavingTabs = files.tabs.some((tab) => tab.saving);
  const canSaveFiles = !usingSeed && dirtyTabs.length > 0;

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event("ade:workbench-layout"));
    });
  }, [explorer.collapsed, explorer.fraction, inspector.collapsed, inspector.fraction, outputCollapsed, consoleFraction, isMaximized]);

  const saveTab = useCallback(
    async (tabId: string): Promise<boolean> => {
      if (usingSeed) {
        return false;
      }
      const tab = files.tabs.find((entry) => entry.id === tabId);
      if (!tab || tab.status !== "ready") {
        return false;
      }
      if (tab.content === tab.initialContent || tab.saving) {
        return false;
      }
      files.beginSavingTab(tabId);
      try {
        const response = await saveConfigFile.mutateAsync({
          path: tab.id,
          content: tab.content,
          etag: tab.etag ?? undefined,
          create: !tab.etag,
          parents: true,
        });
        const metadata = {
          size: response.size ?? tab.metadata?.size ?? null,
          modifiedAt: response.mtime ?? tab.metadata?.modifiedAt ?? null,
          contentType: tab.metadata?.contentType ?? null,
          etag: response.etag ?? tab.metadata?.etag ?? null,
        };
        files.completeSavingTab(tabId, {
          etag: response.etag ?? tab.etag ?? null,
          metadata,
        });
        showConsoleBanner(`Saved ${tab.name}`, { intent: "success", duration: 4000 });
        return true;
      } catch (error) {
        const isConcurrencyError = error instanceof ApiError && error.status === 412;
        const failure = isConcurrencyError
          ? new Error("Save blocked because this file changed on the server. Reloading latest version.")
          : error;
        files.failSavingTab(tabId, failure instanceof Error ? failure.message : String(failure));
        if (isConcurrencyError) {
          try {
            await reloadFileFromServer(tabId);
            showConsoleBanner("File reloaded with the latest version from the server. Review before saving again.", {
              intent: "warning",
              duration: 6000,
            });
          } catch (reloadError) {
            pushConsoleError(reloadError);
          }
        }
        pushConsoleError(failure);
        return false;
      }
    },
    [usingSeed, files, saveConfigFile, showConsoleBanner, reloadFileFromServer, pushConsoleError],
  );

  const saveTabsSequentially = useCallback(
    async (tabIds: readonly string[]) => {
      const saved: string[] = [];
      for (const id of tabIds) {
        const result = await saveTab(id);
        if (result) {
          saved.push(id);
        }
      }
      return saved;
    },
    [saveTab],
  );

  const handleSaveTabShortcut = useCallback(
    (tabId: string) => {
      void saveTab(tabId);
    },
    [saveTab],
  );

  const handleSaveActiveTab = useCallback(() => {
    if (!files.activeTab) {
      return;
    }
    void saveTab(files.activeTab.id);
  }, [files.activeTab, saveTab]);

  const handleSaveAllTabs = useCallback(() => {
    if (!canSaveFiles) {
      return;
    }
    const ids = dirtyTabs.map((tab) => tab.id);
    void (async () => {
      const saved = await saveTabsSequentially(ids);
      if (saved.length > 1) {
        showConsoleBanner(`Saved ${saved.length} files`, { intent: "success", duration: 5000 });
      }
    })();
  }, [canSaveFiles, dirtyTabs, saveTabsSequentially, showConsoleBanner]);

  useEffect(() => {
    const node = paneAreaEl;
    if (!node || typeof window === "undefined") {
      return;
    }

    const measure = () => {
      const rect = node.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      setLayoutSize({
        width,
        height,
      });
      window.dispatchEvent(new Event("ade:workbench-layout"));
    };

    measure();

    if (typeof window.ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }

    const observer = new window.ResizeObserver(() => measure());
    observer.observe(node);
    return () => observer.disconnect();
  }, [paneAreaEl]);

  const consoleLimits = useMemo(() => {
    const container = Math.max(0, layoutSize.height);
    const maxPx = Math.min(OUTPUT_LIMITS.max, Math.max(0, container - MIN_EDITOR_HEIGHT - OUTPUT_HANDLE_THICKNESS));
    const minPx = Math.min(MIN_CONSOLE_HEIGHT, maxPx);
    return { container, minPx, maxPx };
  }, [layoutSize.height]);

  const clampConsoleHeight = useCallback(
    (height: number, limits = consoleLimits) => clamp(height, limits.minPx, limits.maxPx),
    [consoleLimits],
  );

  const resolveInitialConsoleFraction = useCallback(() => {
    const stored = initialConsolePrefsRef.current;
    if (stored && "version" in stored && stored.version === 2 && typeof stored.fraction === "number") {
      return clamp(stored.fraction, 0, 1);
    }
    if (stored && "height" in stored && typeof stored.height === "number" && consoleLimits.container > 0) {
      return clamp(stored.height / consoleLimits.container, 0, 1);
    }
    return 0.25;
  }, [consoleLimits.container]);

  useEffect(() => {
    if (consoleFraction === null && consoleLimits.container > 0) {
      setConsoleFraction(resolveInitialConsoleFraction());
    }
  }, [consoleFraction, consoleLimits.container, resolveInitialConsoleFraction]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const updateModifierState = (event: KeyboardEvent) => {
      setForceModifierActive(event.shiftKey || event.altKey);
    };
    const resetModifiers = () => setForceModifierActive(false);
    window.addEventListener("keydown", updateModifierState);
    window.addEventListener("keyup", updateModifierState);
    window.addEventListener("blur", resetModifiers);
    return () => {
      window.removeEventListener("keydown", updateModifierState);
      window.removeEventListener("keyup", updateModifierState);
      window.removeEventListener("blur", resetModifiers);
    };
  }, []);

  const openConsole = useCallback(() => {
    if (consoleLimits.container > 0 && consoleLimits.maxPx < MIN_CONSOLE_HEIGHT) {
      setConsole("closed");
      showConsoleBanner(CONSOLE_COLLAPSE_MESSAGE, { intent: "warning", duration: 10000 });
      return false;
    }
    clearConsoleBanners();
    setConsole("open");
    setConsoleFraction((current) => {
      if (current !== null) {
        return clamp(current, 0, 1);
      }
      return resolveInitialConsoleFraction();
    });
    return true;
  }, [consoleLimits, setConsole, showConsoleBanner, clearConsoleBanners, resolveInitialConsoleFraction]);

  const closeConsole = useCallback(() => {
    setConsole("closed");
    clearConsoleBanners();
  }, [setConsole, clearConsoleBanners]);

  useEffect(() => {
    if (hasHydratedConsoleState) {
      return;
    }
    const storedState = initialConsolePrefsRef.current?.state;
    if (consoleExplicit || !storedState) {
      setHasHydratedConsoleState(true);
      return;
    }
    if (storedState === "open" || storedState === "closed") {
      if (storedState !== consoleState) {
        setConsole(storedState);
      }
    }
    setHasHydratedConsoleState(true);
  }, [consoleExplicit, consoleState, setConsole, hasHydratedConsoleState]);

  useEffect(() => {
    if (!consolePersistence || isResizingConsole || consoleFraction === null) {
      return;
    }
    consolePersistence.set<ConsolePanelPreferences>({
      version: 2,
      fraction: clamp(consoleFraction, 0, 1),
      state: consoleState,
    });
  }, [consolePersistence, consoleFraction, consoleState, isResizingConsole]);

  useEffect(() => {
    if (consoleState !== "open" || !consoleLimits.container) {
      return;
    }
    if (consoleLimits.maxPx < MIN_CONSOLE_HEIGHT) {
      setConsole("closed");
      showConsoleBanner(CONSOLE_COLLAPSE_MESSAGE, { intent: "warning", duration: 10000 });
      return;
    }
    setConsoleFraction((current) => {
      if (current === null) {
        return resolveInitialConsoleFraction();
      }
      return clamp(current, 0, 1);
    });
  }, [consoleState, consoleLimits, setConsole, showConsoleBanner, resolveInitialConsoleFraction]);

  const deriveSideBounds = useCallback(
    (availableWidth: number, limits: { min: number; max: number }): SideBounds => {
      if (availableWidth <= 0) {
        return { minPx: limits.min, maxPx: limits.max, minFrac: 0, maxFrac: 1 };
      }
      const minPx = Math.min(limits.min, availableWidth);
      const maxPx = Math.min(limits.max, availableWidth);
      return {
        minPx,
        maxPx,
        minFrac: minPx / availableWidth,
        maxFrac: maxPx / availableWidth,
      };
    },
    [],
  );

  const contentWidth = Math.max(0, layoutSize.width - ACTIVITY_BAR_WIDTH);
  const explorerBounds = useMemo(() => deriveSideBounds(contentWidth, EXPLORER_LIMITS), [contentWidth, deriveSideBounds]);
  const inspectorBounds = useMemo(
    () => deriveSideBounds(contentWidth, INSPECTOR_LIMITS),
    [contentWidth, deriveSideBounds],
  );

  const clampSideFraction = useCallback((fraction: number, bounds: SideBounds) => clamp(fraction, bounds.minFrac, bounds.maxFrac), []);

  useEffect(() => {
    if (contentWidth <= 0) {
      return;
    }
    setExplorer((prev) => {
      if (prev.collapsed) {
        return prev;
      }
      const next = clampSideFraction(prev.fraction, explorerBounds);
      return next === prev.fraction ? prev : { ...prev, fraction: next };
    });
    setInspector((prev) => {
      if (prev.collapsed) {
        return prev;
      }
      const next = clampSideFraction(prev.fraction, inspectorBounds);
      return next === prev.fraction ? prev : { ...prev, fraction: next };
    });
  }, [contentWidth, explorerBounds, inspectorBounds, clampSideFraction]);

  const inspectorVisible = !inspector.collapsed && Boolean(files.activeTab);
  const rawExplorerWidth = explorer.collapsed
    ? 0
    : clamp(explorer.fraction, explorerBounds.minFrac, explorerBounds.maxFrac) * contentWidth;
  const rawInspectorWidth = inspectorVisible
    ? clamp(inspector.fraction, inspectorBounds.minFrac, inspectorBounds.maxFrac) * contentWidth
    : 0;
  let explorerWidth = rawExplorerWidth;
  let inspectorWidth = rawInspectorWidth;
  if (contentWidth > 0) {
    const handleBudget =
      (showExplorerPane ? OUTPUT_HANDLE_THICKNESS : 0) + (inspectorVisible ? OUTPUT_HANDLE_THICKNESS : 0);
    const occupied = rawExplorerWidth + rawInspectorWidth + handleBudget;
    if (occupied > contentWidth) {
      const overflow = occupied - contentWidth;
      const inspectorShrink = Math.min(overflow, Math.max(0, rawInspectorWidth - inspectorBounds.minPx));
      inspectorWidth = rawInspectorWidth - inspectorShrink;
      const remaining = overflow - inspectorShrink;
      if (remaining > 0) {
        const explorerShrink = Math.min(remaining, Math.max(0, rawExplorerWidth - explorerBounds.minPx));
        explorerWidth = rawExplorerWidth - explorerShrink;
      }
    }
  }
  const paneHeight = Math.max(0, consoleLimits.container);
  const defaultFraction = 0.25;
  const desiredFraction =
    consoleFraction ??
    (paneHeight > 0 ? clamp(DEFAULT_CONSOLE_HEIGHT / paneHeight, 0, 1) : defaultFraction);
  const desiredHeight = outputCollapsed ? 0 : desiredFraction * paneHeight;
  const consoleHeight = outputCollapsed
    ? 0
    : paneHeight > 0
      ? clampConsoleHeight(desiredHeight)
      : 0;
  const editorHeight =
    paneHeight > 0
      ? Math.max(MIN_EDITOR_HEIGHT, paneHeight - OUTPUT_HANDLE_THICKNESS - consoleHeight)
      : MIN_EDITOR_HEIGHT;

  useEffect(() => {
    const activeId = files.activeTabId;
    if (!activeId) {
      setFileId(undefined);
      return;
    }
    setFileId(activeId);
  }, [files.activeTabId, setFileId]);

  const startRunStream = useCallback(
    (options: RunStreamOptions, metadata: RunStreamMetadata) => {
      if (
        usingSeed ||
        !tree ||
        filesQuery.isLoading ||
        filesQuery.isError ||
        activeStream !== null
      ) {
        return null;
      }
      if (metadata.mode === "validation" && validateConfiguration.isPending) {
        return null;
      }
      if (!openConsole()) {
        return null;
      }

      const startedAt = new Date();
      const startedIso = startedAt.toISOString();
      setPane("console");
      resetConsole(
        metadata.mode === "validation"
          ? "Starting ADE run (validate-only)…"
          : "Starting ADE extraction…",
      );
      if (metadata.mode === "validation") {
        setValidationState((prev) => ({
          ...prev,
          status: "running",
          lastRunAt: startedIso,
          error: null,
        }));
      } else {
        setLatestRun(null);
      }

      const controller = new AbortController();
      consoleStreamRef.current?.abort();
      consoleStreamRef.current = controller;
      setActiveStream({ kind: "run", startedAt: startedIso, metadata });

      void (async () => {
        let currentRunId: string | null = null;
        try {
          for await (const event of streamRun(configId, options, controller.signal)) {
            appendConsoleLine(describeRunEvent(event));
            if (!isMountedRef.current) {
              return;
            }
            if (isTelemetryEnvelope(event)) {
              continue;
            }
            if (event.type === "run.created") {
              currentRunId = event.run_id;
            }
            if (event.type === "run.completed") {
              const notice =
                event.status === "succeeded"
                  ? "ADE run completed successfully."
                  : event.status === "canceled"
                    ? "ADE run canceled."
                    : event.error_message?.trim() || "ADE run failed.";
              const intent: NotificationIntent =
                event.status === "succeeded"
                  ? "success"
                  : event.status === "canceled"
                    ? "info"
                    : "danger";
              showConsoleBanner(notice, { intent });

              if (metadata.mode === "extraction" && currentRunId) {
                const downloadBase = `/api/v1/runs/${encodeURIComponent(currentRunId)}`;
                setLatestRun({
                  runId: currentRunId,
                  status: event.status as RunStatus,
                  downloadBase,
                  documentName: metadata.documentName,
                  sheetNames: metadata.sheetNames ?? [],
                  outputs: [],
                  outputsLoaded: false,
                  artifact: null,
                  artifactLoaded: false,
                  artifactError: null,
                  telemetry: null,
                  telemetryLoaded: false,
                  telemetryError: null,
                  error: null,
                });
                try {
                  const listing = await fetchRunOutputs(currentRunId);
                  const files = Array.isArray(listing.files) ? listing.files : [];
                  setLatestRun((prev) =>
                    prev && prev.runId === currentRunId
                      ? { ...prev, outputs: files, outputsLoaded: true }
                      : prev,
                  );
                } catch (error) {
                  const message =
                    error instanceof Error ? error.message : "Unable to load run outputs.";
                  setLatestRun((prev) =>
                    prev && prev.runId === currentRunId
                      ? { ...prev, outputsLoaded: true, error: message }
                      : prev,
                  );
                }

                try {
                  const artifact = await fetchRunArtifact(currentRunId);
                  setLatestRun((prev) =>
                    prev && prev.runId === currentRunId
                      ? { ...prev, artifact, artifactLoaded: true }
                      : prev,
                  );
                } catch (error) {
                  const message =
                    error instanceof Error ? error.message : "Unable to load run artifact.";
                  setLatestRun((prev) =>
                    prev && prev.runId === currentRunId
                      ? { ...prev, artifactLoaded: true, artifactError: message }
                      : prev,
                  );
                }

                try {
                  const telemetry = await fetchRunTelemetry(currentRunId);
                  setLatestRun((prev) =>
                    prev && prev.runId === currentRunId
                      ? { ...prev, telemetry, telemetryLoaded: true }
                      : prev,
                  );
                } catch (error) {
                  const message =
                    error instanceof Error ? error.message : "Unable to load run telemetry.";
                  setLatestRun((prev) =>
                    prev && prev.runId === currentRunId
                      ? { ...prev, telemetryLoaded: true, telemetryError: message }
                      : prev,
                  );
                }
              }
            }
          }
        } catch (error) {
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
          pushConsoleError(error);
        } finally {
          if (consoleStreamRef.current === controller) {
            consoleStreamRef.current = null;
          }
          if (isMountedRef.current) {
            setActiveStream(null);
          }
        }
      })();

      return startedIso;
    },
    [
      usingSeed,
      tree,
      filesQuery.isLoading,
      filesQuery.isError,
      activeStream,
      validateConfiguration.isPending,
      openConsole,
      setPane,
      resetConsole,
      setValidationState,
      setLatestRun,
      consoleStreamRef,
      setActiveStream,
      configId,
      appendConsoleLine,
      showConsoleBanner,
      pushConsoleError,
    ],
  );

  const handleRunValidation = useCallback(() => {
    const startedIso = startRunStream({ validate_only: true }, { mode: "validation" });
    if (!startedIso) {
      return;
    }
    validateConfiguration.mutate(undefined, {
      onSuccess(result) {
        const issues = result.issues ?? [];
        const messages = issues.map((issue) => ({
          level: "error" as const,
          message: issue.message,
          path: issue.path,
        }));
        setValidationState({
          status: "success",
          messages,
          lastRunAt: startedIso,
          error: null,
          digest: result.content_digest ?? null,
        });
      },
      onError(error) {
        const message = error instanceof Error ? error.message : "Validation failed.";
        setValidationState({
          status: "error",
          messages: [{ level: "error", message }],
          lastRunAt: startedIso,
          error: message,
          digest: null,
        });
      },
    });
  }, [startRunStream, validateConfiguration, setValidationState]);

  const handleRunExtraction = useCallback(
    (selection: { documentId: string; documentName: string; sheetNames?: readonly string[] }) => {
      const worksheetList = Array.from(new Set((selection.sheetNames ?? []).filter(Boolean)));
      const started = startRunStream(
        {
          input_document_id: selection.documentId,
          input_sheet_names: worksheetList.length ? worksheetList : undefined,
          input_sheet_name: worksheetList.length === 1 ? worksheetList[0] : undefined,
        },
        {
          mode: "extraction",
          documentId: selection.documentId,
          documentName: selection.documentName,
          sheetNames: worksheetList,
        },
      );
      if (started) {
        setRunDialogOpen(false);
      }
    },
    [startRunStream],
  );

  const triggerBuild = useCallback(
    (options?: BuildTriggerOptions) => {
      closeBuildMenu();
      if (
        usingSeed ||
        !tree ||
        filesQuery.isLoading ||
        filesQuery.isError ||
        activeStream !== null
      ) {
        return;
      }
      if (!openConsole()) {
        return;
      }

      const resolvedForce = typeof options?.force === "boolean" ? options.force : forceModifierActive;
      const resolvedWait = Boolean(options?.wait);

      const startedIso = new Date().toISOString();
      setPane("console");
      resetConsole(resolvedForce ? "Force rebuilding environment…" : "Starting configuration build…");

      const nowTimestamp = formatConsoleTimestamp(new Date());
      if (resolvedForce) {
        appendConsoleLine({
          level: "warning",
          message: "Force rebuild requested. ADE will recreate the environment from scratch.",
          timestamp: nowTimestamp,
        });
      } else if (resolvedWait) {
        appendConsoleLine({
          level: "info",
          message: "Waiting for any running build to finish before starting.",
          timestamp: nowTimestamp,
        });
      }

      const controller = new AbortController();
      consoleStreamRef.current?.abort();
      consoleStreamRef.current = controller;
      setActiveStream({
        kind: "build",
        startedAt: startedIso,
        metadata: { force: resolvedForce, wait: resolvedWait },
      });

      void (async () => {
        try {
          for await (const event of streamBuild(
            workspaceId,
            configId,
            { force: resolvedForce, wait: resolvedWait },
            controller.signal,
          )) {
            appendConsoleLine(describeBuildEvent(event));
            if (!isMountedRef.current) {
              return;
            }
            if (event.type === "build.completed") {
              const summary = event.summary?.trim();
              if (summary && /reused/i.test(summary)) {
                appendConsoleLine({
                  level: "info",
                  message: "Environment reused. Hold Shift or open the build menu to force a rebuild.",
                  timestamp: formatConsoleTimestamp(new Date()),
                });
                showConsoleBanner(
                  "Environment already up to date. Hold Shift or use the menu to force rebuild.",
                  { intent: "info" },
                );
              } else {
                const notice =
                  event.status === "active"
                    ? summary || "Build completed successfully."
                    : event.status === "canceled"
                      ? "Build canceled."
                      : event.error_message?.trim() || "Build failed.";
                const intent: NotificationIntent =
                  event.status === "active"
                    ? "success"
                    : event.status === "canceled"
                      ? "info"
                      : "danger";
                showConsoleBanner(notice, { intent });
              }
            }
          }
        } catch (error) {
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
          pushConsoleError(error);
        } finally {
          if (consoleStreamRef.current === controller) {
            consoleStreamRef.current = null;
          }
          if (isMountedRef.current) {
            setActiveStream(null);
          }
        }
      })();
    },
    [
      usingSeed,
      tree,
      filesQuery.isLoading,
      filesQuery.isError,
      activeStream,
      closeBuildMenu,
      openConsole,
      forceModifierActive,
      setPane,
      resetConsole,
      appendConsoleLine,
      consoleStreamRef,
      setActiveStream,
      workspaceId,
      configId,
      pushConsoleError,
      showConsoleBanner,
    ],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      const usesPrimary = isMacPlatform ? event.metaKey : event.ctrlKey;
      if (!usesPrimary || event.altKey) {
        return;
      }
      if (event.key.toLowerCase() !== "b") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          (target as HTMLElement).isContentEditable
        ) {
          return;
        }
      }
      event.preventDefault();
      triggerBuild({ force: event.shiftKey, source: "shortcut" });
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [triggerBuild, isMacPlatform]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      const usesPrimary = isMacPlatform ? event.metaKey : event.ctrlKey;
      if (!usesPrimary || event.altKey) {
        return;
      }
      if (event.key.toLowerCase() !== "s") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable) {
          return;
        }
      }
      if (!canSaveFiles) {
        return;
      }
      event.preventDefault();
      handleSaveActiveTab();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isMacPlatform, canSaveFiles, handleSaveActiveTab]);

  const runStreamMetadata = activeStream?.kind === "run" ? activeStream.metadata : undefined;
  const isStreamingRun = activeStream?.kind === "run";
  const isStreamingBuild = activeStream?.kind === "build";
  const isStreamingAny = activeStream !== null;

  const isStreamingExtraction = isStreamingRun && runStreamMetadata?.mode === "extraction";
  const isStreamingValidationRun = isStreamingRun && runStreamMetadata?.mode !== "extraction";

  const isRunningValidation =
    validationState.status === "running" || validateConfiguration.isPending || isStreamingValidationRun;
  const canRunValidation =
    !usingSeed &&
    Boolean(tree) &&
    !filesQuery.isLoading &&
    !filesQuery.isError &&
    !isStreamingAny &&
    !validateConfiguration.isPending &&
    validationState.status !== "running";

  const isRunningExtraction = isStreamingExtraction;
  const canRunExtraction =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !isStreamingAny;

  const isBuildingEnvironment = isStreamingBuild;
  const canBuildEnvironment =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !isStreamingAny;

  const handleSelectActivityView = useCallback((view: ActivityBarView) => {
    setActivityView(view);
    if (view === "explorer") {
      setExplorer((prev) => ({ ...prev, collapsed: false }));
    }
  }, []);

  const handleOpenSettingsMenu = useCallback((event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    setSettingsMenu({ x: rect.right + 8, y: rect.top });
  }, []);

  const closeSettingsMenu = useCallback(() => setSettingsMenu(null), []);

  const handleToggleOutput = useCallback(() => {
    if (outputCollapsed) {
      void openConsole();
    } else {
      closeConsole();
    }
  }, [outputCollapsed, openConsole, closeConsole]);

  const handleToggleExplorer = useCallback(() => {
    setExplorer((prev) => ({ ...prev, collapsed: !prev.collapsed }));
  }, []);

  const handleHideExplorer = useCallback(() => {
    setExplorer((prev) => ({ ...prev, collapsed: true }));
  }, []);

  const handleToggleInspectorVisibility = useCallback(() => {
    setInspector((prev) => ({ ...prev, collapsed: !prev.collapsed }));
  }, []);

  const settingsMenuItems = useMemo<ContextMenuItem[]>(() => {
    const blankIcon = <span className="inline-block h-4 w-4 opacity-0" />;
    const items: ContextMenuItem[] = THEME_MENU_OPTIONS.map((option) => ({
      id: `theme-${option.value}`,
      label: `${option.label} theme`,
      icon: editorTheme.preference === option.value ? <MenuIconCheck /> : blankIcon,
      onSelect: () => editorTheme.setPreference(option.value),
    }));
    items.push(
      {
        id: "toggle-explorer",
        label: explorer.collapsed ? "Show Explorer" : "Hide Explorer",
        dividerAbove: true,
        icon: explorer.collapsed ? blankIcon : <MenuIconCheck />,
        onSelect: () => setExplorer((prev) => ({ ...prev, collapsed: !prev.collapsed })),
      },
      {
        id: "toggle-inspector",
        label: inspector.collapsed ? "Show Inspector" : "Hide Inspector",
        icon: inspector.collapsed ? blankIcon : <MenuIconCheck />,
        onSelect: () => setInspector((prev) => ({ ...prev, collapsed: !prev.collapsed })),
      },
      {
        id: "toggle-console",
        label: outputCollapsed ? "Show Console" : "Hide Console",
        icon: outputCollapsed ? blankIcon : <MenuIconCheck />,
        onSelect: handleToggleOutput,
      },
    );
    return items;
  }, [
    editorTheme,
    explorer.collapsed,
    inspector.collapsed,
    outputCollapsed,
    handleToggleOutput,
  ]);

  useEffect(() => {
    if (typeof document === "undefined" || !isMaximized) {
      return;
    }
    const previous = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    return () => {
      document.documentElement.style.overflow = previous || "";
    };
  }, [isMaximized]);

  const workspaceLabel = formatWorkspaceLabel(workspaceId);
  const saveShortcutLabel = isMacPlatform ? "⌘S" : "Ctrl+S";
  const buildShortcutLabel = isMacPlatform ? "⌘B" : "Ctrl+B";
  const forceShortcutLabel = isMacPlatform ? "⇧⌘B" : "Ctrl+Shift+B";
  const buildMenuItems = useMemo<ContextMenuItem[]>(() => {
    const disabled = !canBuildEnvironment;
    return [
      {
        id: "build-default",
        label: "Build / reuse environment",
        shortcut: buildShortcutLabel,
        disabled,
        onSelect: () => triggerBuild(),
      },
      {
        id: "build-force",
        label: "Force rebuild now",
        shortcut: forceShortcutLabel,
        disabled,
        onSelect: () => triggerBuild({ force: true }),
      },
      {
        id: "build-force-wait",
        label: "Force rebuild after current build",
        disabled,
        onSelect: () => triggerBuild({ force: true, wait: true }),
      },
    ];
  }, [buildShortcutLabel, forceShortcutLabel, canBuildEnvironment, triggerBuild]);

  if (!seed && filesQuery.isLoading) {
    return (
      <PageState
        variant="loading"
        title="Loading configuration files"
        description="Fetching workspace configuration files for the workbench."
      />
    );
  }

  if (!seed && filesQuery.isError) {
    return (
      <PageState
        variant="error"
        title="Unable to load configuration files"
        description="Try reloading the page or check your connection."
      />
    );
  }

  if (!tree) {
    return (
      <PageState
        variant="empty"
        title="No configuration files found"
        description="Create files in the ADE configuration package to begin editing."
      />
    );
  }
  const rootSurfaceClass = isMaximized
    ? menuAppearance === "dark"
      ? "bg-[#0f111a] text-white"
      : "bg-slate-50 text-slate-900"
    : menuAppearance === "dark"
      ? "bg-transparent text-white"
      : "bg-transparent text-slate-900";
  const editorSurface = menuAppearance === "dark" ? "#1b1f27" : "#ffffff";
  const editorText = menuAppearance === "dark" ? "#f5f6fb" : "#0f172a";
  const windowFrameClass = isMaximized
    ? clsx(
        "fixed inset-0 z-[90] flex flex-col",
        menuAppearance === "dark" ? "bg-[#0f111a] text-white" : "bg-white text-slate-900",
      )
    : clsx(
        "flex w-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
        menuAppearance === "dark" ? "bg-[#101322] text-white" : "bg-white text-slate-900",
      );

  return (
    <div className={clsx("flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden", rootSurfaceClass)}>
      {isMaximized ? <div className="fixed inset-0 z-40 bg-slate-900/60" /> : null}
      <div className={windowFrameClass}>
        <WorkbenchChrome
        configName={configName}
        workspaceLabel={workspaceLabel}
        validationLabel={validationLabel}
        canSaveFiles={canSaveFiles}
        isSavingFiles={isSavingTabs}
        onSaveFile={handleSaveActiveTab}
        saveShortcutLabel={saveShortcutLabel}
        canBuildEnvironment={canBuildEnvironment}
        isBuildingEnvironment={isBuildingEnvironment}
        onBuildEnvironment={triggerBuild}
        onOpenBuildMenu={openBuildMenu}
        forceModifierActive={forceModifierActive}
        buildShortcutLabel={buildShortcutLabel}
        forceShortcutLabel={forceShortcutLabel}
        canRunValidation={canRunValidation}
        isRunningValidation={isRunningValidation}
        onRunValidation={handleRunValidation}
        canRunExtraction={canRunExtraction}
        isRunningExtraction={isRunningExtraction}
        onRunExtraction={() => {
          if (!canRunExtraction) {
            return;
          }
          setRunDialogOpen(true);
        }}
        explorerVisible={showExplorerPane}
        onToggleExplorer={handleToggleExplorer}
        consoleOpen={!outputCollapsed}
        onToggleConsole={handleToggleOutput}
        inspectorCollapsed={inspector.collapsed}
        onToggleInspector={handleToggleInspectorVisibility}
        appearance={menuAppearance}
        forceNextBuild={forceNextBuild}
        onToggleForceNextBuild={handleToggleForceNextBuild}
        windowState={windowState}
        onMinimizeWindow={handleMinimizeWindow}
        onToggleMaximize={handleToggleMaximize}
        onCloseWindow={handleCloseWorkbench}
      />
        <div ref={setPaneAreaEl} className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
          <ActivityBar
            activeView={activityView}
            onSelectView={handleSelectActivityView}
            onOpenSettings={handleOpenSettingsMenu}
            appearance={menuAppearance}
          />
          {showExplorerPane ? (
            <>
              <div className="flex min-h-0" style={{ width: explorerWidth }}>
                {activityView === "explorer" && files.tree ? (
                  <Explorer
                    width={explorerWidth}
                    tree={files.tree}
                    activeFileId={files.activeTab?.id ?? ""}
                    openFileIds={files.tabs.map((tab) => tab.id)}
                    onSelectFile={(fileId) => {
                      files.openFile(fileId);
                      setFileId(fileId);
                    }}
                    theme={menuAppearance}
                    onCloseFile={files.closeTab}
                    onCloseOtherFiles={files.closeOtherTabs}
                    onCloseTabsToRight={files.closeTabsToRight}
                    onCloseAllFiles={files.closeAllTabs}
                    onHide={handleHideExplorer}
                  />
                ) : (
                  <SidePanelPlaceholder width={explorerWidth} view={activityView} />
                )}
              </div>
              <PanelResizeHandle
                orientation="vertical"
                onPointerDown={(event) => {
                  const startX = event.clientX;
                  const startWidth = explorerWidth;
                  trackPointerDrag(event, {
                    cursor: "col-resize",
                    onMove: (move) => {
                      const delta = move.clientX - startX;
                      const nextWidth = clamp(startWidth + delta, explorerBounds.minPx, explorerBounds.maxPx);
                      setExplorer((prev) =>
                        prev.collapsed || contentWidth <= 0
                          ? prev
                          : { ...prev, fraction: clampSideFraction(nextWidth / contentWidth, explorerBounds) },
                      );
                    },
                  });
                }}
              />
            </>
          ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col" style={{ backgroundColor: editorSurface, color: editorText }}>
          {outputCollapsed ? (
            <EditorArea
              tabs={files.tabs}
              activeTabId={files.activeTab?.id ?? ""}
              onSelectTab={(tabId) => {
                files.selectTab(tabId);
                setFileId(tabId);
              }}
              onCloseTab={files.closeTab}
              onCloseOtherTabs={files.closeOtherTabs}
              onCloseTabsToRight={files.closeTabsToRight}
              onCloseAllTabs={files.closeAllTabs}
              onContentChange={files.updateContent}
              onSaveTab={handleSaveTabShortcut}
              onSaveAllTabs={handleSaveAllTabs}
              onMoveTab={files.moveTab}
              onPinTab={files.pinTab}
              onUnpinTab={files.unpinTab}
              onSelectRecentTab={files.selectRecentTab}
              editorTheme={editorTheme.resolvedTheme}
              menuAppearance={menuAppearance}
              canSaveFiles={canSaveFiles}
              minHeight={MIN_EDITOR_HEIGHT}
            />
          ) : (
            <div
                className="grid min-h-0 min-w-0 flex-1"
                style={{
                height: paneHeight > 0 ? `${paneHeight}px` : undefined,
                gridTemplateRows: `${Math.max(MIN_EDITOR_HEIGHT, editorHeight)}px ${OUTPUT_HANDLE_THICKNESS}px ${Math.max(
                  0,
                  consoleHeight,
                )}px`,
              }}
            >
              <EditorArea
                tabs={files.tabs}
                activeTabId={files.activeTab?.id ?? ""}
                onSelectTab={(tabId) => {
                  files.selectTab(tabId);
                  setFileId(tabId);
                }}
                onCloseTab={files.closeTab}
                onCloseOtherTabs={files.closeOtherTabs}
                onCloseTabsToRight={files.closeTabsToRight}
                onCloseAllTabs={files.closeAllTabs}
                onContentChange={files.updateContent}
                onSaveTab={handleSaveTabShortcut}
                onSaveAllTabs={handleSaveAllTabs}
                onMoveTab={files.moveTab}
                onPinTab={files.pinTab}
                onUnpinTab={files.unpinTab}
                onSelectRecentTab={files.selectRecentTab}
                editorTheme={editorTheme.resolvedTheme}
                menuAppearance={menuAppearance}
                canSaveFiles={canSaveFiles}
                minHeight={MIN_EDITOR_HEIGHT}
              />
              <PanelResizeHandle
                orientation="horizontal"
                onPointerDown={(event) => {
                  setIsResizingConsole(true);
                  const startY = event.clientY;
                  const startHeight = consoleHeight;
                  trackPointerDrag(event, {
                    cursor: "row-resize",
                    onMove: (move) => {
                      if (consoleLimits.maxPx <= 0 || paneHeight <= 0) {
                        return;
                      }
                      const delta = startY - move.clientY;
                      const nextHeight = clamp(startHeight + delta, consoleLimits.minPx, consoleLimits.maxPx);
                      setConsoleFraction(clamp(nextHeight / paneHeight, 0, 1));
                    },
                    onEnd: () => {
                      setIsResizingConsole(false);
                    },
                  });
                }}
              />
              <BottomPanel
                height={Math.max(0, consoleHeight)}
                consoleLines={consoleLines}
                validation={validationState}
                activePane={pane}
                onPaneChange={setPane}
                latestRun={latestRun}
              />
            </div>
          )}
        </div>

        {inspectorVisible ? (
          <>
            <PanelResizeHandle
              orientation="vertical"
              onPointerDown={(event) => {
                const startX = event.clientX;
                const startWidth = inspectorWidth;
                trackPointerDrag(event, {
                  cursor: "col-resize",
                  onMove: (move) => {
                    const delta = startX - move.clientX;
                    const nextWidth = clamp(startWidth + delta, inspectorBounds.minPx, inspectorBounds.maxPx);
                    setInspector((prev) =>
                      prev.collapsed || contentWidth <= 0
                        ? prev
                        : { ...prev, fraction: clampSideFraction(nextWidth / contentWidth, inspectorBounds) },
                    );
                  },
                });
              }}
            />
                    <Inspector width={inspectorWidth} file={files.activeTab ?? null} />
          </>
        ) : null}
      </div>
      </div>
      {runDialogOpen ? (
        <RunExtractionDialog
          open={runDialogOpen}
          workspaceId={workspaceId}
          onClose={() => setRunDialogOpen(false)}
          onRun={handleRunExtraction}
        />
      ) : null}
      <ContextMenu
        open={Boolean(buildMenu)}
        position={buildMenu}
        onClose={closeBuildMenu}
        items={buildMenuItems}
        appearance={menuAppearance}
      />
      <ContextMenu
        open={Boolean(settingsMenu)}
        position={settingsMenu}
        onClose={closeSettingsMenu}
        items={settingsMenuItems}
        appearance={menuAppearance}
      />
    </div>
  );
}

interface SidePanelPlaceholderProps {
  readonly width: number;
  readonly view: ActivityBarView;
}

function SidePanelPlaceholder({ width, view }: SidePanelPlaceholderProps) {
  const label = ACTIVITY_LABELS[view] || "Coming soon";
  return (
    <div
      className="flex h-full min-h-0 flex-col items-center justify-center border-r border-[#111111] bg-[#1e1e1e] px-4 text-center text-[11px] uppercase tracking-wide text-slate-400"
      style={{ width }}
      aria-live="polite"
    >
      {label}
    </div>
  );
}

function MenuIconCheck() {
  return (
    <svg className="h-4 w-4 text-[#4fc1ff]" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 8l3 3 5-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function WorkbenchChrome({
  configName,
  workspaceLabel,
  validationLabel,
  canSaveFiles,
  isSavingFiles,
  onSaveFile,
  saveShortcutLabel,
  canBuildEnvironment,
  isBuildingEnvironment,
  onBuildEnvironment,
  onOpenBuildMenu,
  forceNextBuild,
  forceModifierActive,
  buildShortcutLabel,
  forceShortcutLabel,
  canRunValidation,
  isRunningValidation,
  onRunValidation,
  canRunExtraction,
  isRunningExtraction,
  onRunExtraction,
  explorerVisible,
  onToggleExplorer,
  consoleOpen,
  onToggleConsole,
  inspectorCollapsed,
  onToggleInspector,
  appearance,
  onToggleForceNextBuild,
  windowState,
  onMinimizeWindow,
  onToggleMaximize,
  onCloseWindow,
}: {
  readonly configName: string;
  readonly workspaceLabel: string;
  readonly validationLabel?: string;
  readonly canSaveFiles: boolean;
  readonly isSavingFiles: boolean;
  readonly onSaveFile: () => void;
  readonly saveShortcutLabel: string;
  readonly canBuildEnvironment: boolean;
  readonly isBuildingEnvironment: boolean;
  readonly onBuildEnvironment: (options?: BuildTriggerOptions) => void;
  readonly onOpenBuildMenu: (position: { x: number; y: number }) => void;
  readonly forceNextBuild: boolean;
  readonly forceModifierActive: boolean;
  readonly buildShortcutLabel: string;
  readonly forceShortcutLabel: string;
  readonly canRunValidation: boolean;
  readonly isRunningValidation: boolean;
  readonly onRunValidation: () => void;
  readonly canRunExtraction: boolean;
  readonly isRunningExtraction: boolean;
  readonly onRunExtraction: () => void;
  readonly explorerVisible: boolean;
  readonly onToggleExplorer: () => void;
  readonly consoleOpen: boolean;
  readonly onToggleConsole: () => void;
  readonly inspectorCollapsed: boolean;
  readonly onToggleInspector: () => void;
  readonly appearance: "light" | "dark";
  readonly onToggleForceNextBuild: () => void;
  readonly windowState: WorkbenchWindowState;
  readonly onMinimizeWindow: () => void;
  readonly onToggleMaximize: () => void;
  readonly onCloseWindow: () => void;
}) {
  const dark = appearance === "dark";
  const surfaceClass = dark
    ? "border-white/10 bg-[#151821] text-white"
    : "border-slate-200 bg-white text-slate-900";
  const metaTextClass = dark ? "text-white/60" : "text-slate-500";
  const buildButtonClass = dark
    ? "bg-white/10 text-white hover:bg-white/20 disabled:bg-white/10 disabled:text-white/40"
    : "bg-slate-100 text-slate-900 hover:bg-slate-200 disabled:bg-slate-50 disabled:text-slate-400";
  const saveButtonClass = dark
    ? "bg-emerald-400/20 text-emerald-50 hover:bg-emerald-400/30 disabled:bg-white/10 disabled:text-white/30"
    : "bg-emerald-500 text-white hover:bg-emerald-400 disabled:bg-slate-200 disabled:text-slate-500";
  const runButtonClass = dark
    ? "bg-brand-500 text-white hover:bg-brand-400 disabled:bg-white/20 disabled:text-white/40"
    : "bg-brand-600 text-white hover:bg-brand-500 disabled:bg-slate-200 disabled:text-slate-500";
  const isMaximized = windowState === "maximized";
  const forceIntentActive = forceNextBuild || forceModifierActive;
  const buildButtonLabel = isBuildingEnvironment
    ? "Building…"
    : forceIntentActive
      ? "Force rebuild"
      : "Build environment";
  const buildButtonTitle = forceIntentActive
    ? `Force rebuild (Shift+Click · ${forceShortcutLabel})`
    : `Build environment (${buildShortcutLabel})`;

  return (
    <div className={clsx("flex items-center justify-between border-b px-4 py-2", surfaceClass)}>
      <div className="flex min-w-0 items-center gap-3">
        <WorkbenchBadgeIcon />
        <div className="min-w-0 leading-tight">
          <div className={clsx("text-[10px] font-semibold uppercase tracking-[0.35em]", metaTextClass)}>
            Config Workbench
          </div>
          <div className="truncate text-sm font-semibold" title={configName}>
            {configName}
          </div>
          <div className={clsx("text-[11px]", metaTextClass)} title={workspaceLabel}>
            Workspace · {workspaceLabel}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {validationLabel ? <span className={clsx("text-xs", metaTextClass)}>{validationLabel}</span> : null}
        <button
          type="button"
          onClick={onSaveFile}
          disabled={!canSaveFiles}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            saveButtonClass,
          )}
          title={`Save (${saveShortcutLabel})`}
        >
          {isSavingFiles ? <SpinnerIcon /> : <SaveIcon />}
          {isSavingFiles ? "Saving…" : "Save"}
        </button>
        <SplitButton
          label={buildButtonLabel}
          icon={isBuildingEnvironment ? <SpinnerIcon /> : <BuildIcon />}
          disabled={!canBuildEnvironment}
          isLoading={isBuildingEnvironment}
          highlight={forceIntentActive && !isBuildingEnvironment}
          title={buildButtonTitle}
          primaryClassName={clsx(
            buildButtonClass,
            "rounded-r-none focus-visible:ring-offset-0",
          )}
          menuClassName={clsx(
            buildButtonClass,
            "rounded-l-none px-2",
            dark ? "border-white/20" : "border-slate-300",
          )}
          menuAriaLabel="Open build options"
          onPrimaryClick={(event) =>
            onBuildEnvironment({
              force: event.shiftKey || event.altKey || forceModifierActive,
            })
          }
          onOpenMenu={(position) => onOpenBuildMenu({ x: position.x, y: position.y })}
          onContextMenu={(event) => {
            event.preventDefault();
            onOpenBuildMenu({ x: event.clientX, y: event.clientY });
          }}
        />
        <button
          type="button"
          onClick={onRunValidation}
          disabled={!canRunValidation}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
        >
          {isRunningValidation ? <SpinnerIcon /> : <RunIcon />}
          {isRunningValidation ? "Running…" : "Run validation"}
        </button>
        <button
          type="button"
          onClick={onRunExtraction}
          disabled={!canRunExtraction}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
        >
          {isRunningExtraction ? <SpinnerIcon /> : <RunIcon />}
          {isRunningExtraction ? "Running…" : "Run extraction"}
        </button>
        <ChromeIconButton
          ariaLabel={forceNextBuild ? "Force rebuild enabled for next run" : "Force next rebuild"}
          onClick={onToggleForceNextBuild}
          appearance={appearance}
          active={forceNextBuild}
          icon={<BuildIcon />}
        />
        <div className="flex items-center gap-1">
          <ChromeIconButton
            ariaLabel={explorerVisible ? "Hide explorer" : "Show explorer"}
            onClick={onToggleExplorer}
            appearance={appearance}
            active={explorerVisible}
            icon={<SidebarIcon active={explorerVisible} />}
          />
          <ChromeIconButton
            ariaLabel={inspectorCollapsed ? "Show inspector" : "Hide inspector"}
            onClick={onToggleInspector}
            appearance={appearance}
            active={!inspectorCollapsed}
            icon={<InspectorIcon />}
          />
          <ChromeIconButton
            ariaLabel={consoleOpen ? "Hide console" : "Show console"}
            onClick={onToggleConsole}
            appearance={appearance}
            active={consoleOpen}
            icon={<ConsoleIcon />}
          />
        </div>
        <div
          className={clsx(
            "flex items-center gap-2 border-l pl-3",
            appearance === "dark" ? "border-white/20" : "border-slate-200/70",
          )}
        >
          <ChromeIconButton
            ariaLabel="Minimize workbench"
            onClick={onMinimizeWindow}
            appearance={appearance}
            icon={<MinimizeIcon />}
          />
          <ChromeIconButton
            ariaLabel={isMaximized ? "Restore workbench" : "Maximize workbench"}
            onClick={onToggleMaximize}
            appearance={appearance}
            active={isMaximized}
            icon={isMaximized ? <WindowRestoreIcon /> : <WindowMaximizeIcon />}
          />
          <ChromeIconButton
            ariaLabel="Close workbench"
            onClick={onCloseWindow}
            appearance={appearance}
            icon={<CloseIcon />}
          />
        </div>
      </div>
    </div>
  );
}

interface RunExtractionDialogProps {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly onClose: () => void;
  readonly onRun: (selection: {
    documentId: string;
    documentName: string;
    sheetNames?: readonly string[];
  }) => void;
}

function RunExtractionDialog({ open, workspaceId, onClose, onRun }: RunExtractionDialogProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const documentsQuery = useQuery<DocumentRecord[]>({
    queryKey: ["builder-documents", workspaceId],
    queryFn: ({ signal }) => fetchRecentDocuments(workspaceId, signal),
    staleTime: 60_000,
  });
  const documents = useMemo(
    () => documentsQuery.data ?? [],
    [documentsQuery.data],
  );
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  useEffect(() => {
    if (!documents.length) {
      setSelectedDocumentId("");
      return;
    }
    setSelectedDocumentId((current) => {
      if (current && documents.some((doc) => doc.id === current)) {
        return current;
      }
      return documents[0]?.id ?? "";
    });
  }, [documents]);

  const selectedDocument = documents.find((doc) => doc.id === selectedDocumentId) ?? null;
  const sheetQuery = useQuery<DocumentSheet[]>({
    queryKey: ["builder-document-sheets", workspaceId, selectedDocumentId],
    queryFn: ({ signal }) => fetchDocumentSheets(workspaceId, selectedDocumentId, signal),
    enabled: Boolean(selectedDocumentId),
    staleTime: 60_000,
  });
  const sheetOptions = useMemo(
    () => sheetQuery.data ?? [],
    [sheetQuery.data],
  );
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  useEffect(() => {
    if (!sheetOptions.length) {
      setSelectedSheets([]);
      return;
    }
    setSelectedSheets((current) =>
      current.filter((name) => sheetOptions.some((sheet) => sheet.name === name)),
    );
  }, [sheetOptions]);

  const normalizedSheetSelection = useMemo(
    () =>
      Array.from(
        new Set(selectedSheets.filter((name) => sheetOptions.some((sheet) => sheet.name === name))),
      ),
    [selectedSheets, sheetOptions],
  );

  const toggleWorksheet = useCallback((name: string) => {
    setSelectedSheets((current) =>
      current.includes(name) ? current.filter((sheet) => sheet !== name) : [...current, name],
    );
  }, []);

  if (!open) {
    return null;
  }

  const runDisabled = !selectedDocument || documentsQuery.isLoading || documentsQuery.isError;
  const sheetsAvailable = sheetOptions.length > 0;

  const content = (
    <div className="fixed inset-0 z-[95] flex items-center justify-center bg-slate-900/60 px-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-2xl"
      >
        <header className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Select a document</h2>
            <p className="text-sm text-slate-500">
              Choose a workspace document and optional worksheet before running the extractor.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </header>

        {documentsQuery.isError ? (
          <Alert tone="danger">Unable to load documents. Try again later.</Alert>
        ) : documentsQuery.isLoading ? (
          <p className="text-sm text-slate-500">Loading documents…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-slate-500">Upload a document in the workspace to run the extractor.</p>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="builder-run-document-select">
                Document
              </label>
              <Select
                id="builder-run-document-select"
                value={selectedDocumentId}
                onChange={(event) => setSelectedDocumentId(event.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                {documents.map((document) => (
                  <option key={document.id} value={document.id}>
                    {document.name}
                  </option>
                ))}
              </Select>
              {selectedDocument ? (
                <p className="text-xs text-slate-500">
                  Uploaded {formatDocumentTimestamp(selectedDocument.created_at)} ·{" "}
                  {(selectedDocument.byte_size ?? 0).toLocaleString()} bytes
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-700">Worksheet</p>
              {sheetQuery.isLoading ? (
                <p className="text-sm text-slate-500">Loading worksheets…</p>
              ) : sheetQuery.isError ? (
                <Alert tone="warning">
                  <div className="space-y-2">
                    <p className="text-sm text-slate-700">
                      Worksheet metadata is temporarily unavailable. The run will process the entire file unless you retry and
                      pick specific sheets.
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => sheetQuery.refetch()}
                        disabled={sheetQuery.isFetching}
                      >
                        Retry loading
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setSelectedSheets([])}>
                        Use all worksheets
                      </Button>
                    </div>
                  </div>
                </Alert>
              ) : sheetsAvailable ? (
                <div className="space-y-3 rounded-lg border border-slate-200 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-slate-700">Worksheets</p>
                      <p className="text-xs text-slate-500">
                        {normalizedSheetSelection.length === 0
                          ? "All worksheets will be processed by default. Select specific sheets to narrow the run."
                          : `${normalizedSheetSelection.length.toLocaleString()} worksheet${
                              normalizedSheetSelection.length === 1 ? "" : "s"
                            } selected.`}
                      </p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => setSelectedSheets([])}>
                      Use all worksheets
                    </Button>
                  </div>

                  <div className="max-h-48 space-y-2 overflow-auto rounded-md border border-slate-200 p-2">
                    {sheetOptions.map((sheet) => {
                      const checked = normalizedSheetSelection.includes(sheet.name);
                      return (
                        <label
                          key={`${sheet.index}-${sheet.name}`}
                          className="flex items-center gap-2 rounded px-2 py-1 text-sm text-slate-700 hover:bg-slate-100"
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                            checked={checked}
                            onChange={() => toggleWorksheet(sheet.name)}
                          />
                          <span className="flex-1 truncate">
                            {sheet.name}
                            {sheet.is_active ? " (active)" : ""}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-500">This file will be ingested directly.</p>
              )}
            </div>
          </div>
        )}

        <footer className="mt-6 flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
              onClick={() => {
                if (!selectedDocument) {
                  return;
                }
                onRun({
                  documentId: selectedDocument.id,
                  documentName: selectedDocument.name,
                  sheetNames:
                    normalizedSheetSelection.length > 0 ? normalizedSheetSelection : undefined,
                });
              }}
              disabled={runDisabled}
            >
              Run extraction
          </Button>
        </footer>
      </div>
    </div>
  );

  return typeof document === "undefined" ? null : createPortal(content, document.body);
}

async function fetchRecentDocuments(workspaceId: string, signal?: AbortSignal): Promise<DocumentRecord[]> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query: { sort: "-created_at", page_size: 50 } },
    signal,
  });
  return ((data as components["schemas"]["DocumentPage"] | undefined)?.items ?? []) as DocumentRecord[];
}

function formatDocumentTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function ChromeIconButton({
  ariaLabel,
  onClick,
  icon,
  appearance,
  active = false,
}: {
  readonly ariaLabel: string;
  readonly onClick: () => void;
  readonly icon: ReactNode;
  readonly appearance: "light" | "dark";
  readonly active?: boolean;
}) {
  const dark = appearance === "dark";
  const baseClass = dark
    ? "text-white/70 hover:text-white hover:bg-white/5 hover:border-white/20 focus-visible:ring-white/40"
    : "text-slate-500 hover:text-slate-900 hover:bg-slate-100 hover:border-slate-300 focus-visible:ring-slate-400/40";
  const activeClass = dark ? "text-white border-white/30 bg-white/10" : "text-slate-900 border-slate-300 bg-slate-200/70";
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      className={clsx(
        "flex h-7 w-7 items-center justify-center rounded-[4px] border border-transparent text-sm transition focus-visible:outline-none focus-visible:ring-2",
        baseClass,
        active && activeClass,
      )}
      title={ariaLabel}
    >
      {icon}
    </button>
  );
}

function WorkbenchBadgeIcon() {
  return (
    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#4fc1ff] via-[#2d7dff] to-[#7c4dff] text-white shadow-lg shadow-[#10121f]">
      <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="9" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="2" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="9" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
      </svg>
    </span>
  );
}

function SidebarIcon({ active }: { readonly active: boolean }) {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect
        x="3"
        y="4"
        width="14"
        height="12"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.4"
        opacity={active ? 1 : 0.6}
      />
      <path d="M7 4v12" stroke="currentColor" strokeWidth="1.4" opacity={active ? 1 : 0.6} />
    </svg>
  );
}

function ConsoleIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2" />
      <path d="M3 10.5h10" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function InspectorIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2" />
      <path d="M10 3v10" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function WindowMaximizeIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function WindowRestoreIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4.5 5.5h6v6h-6z" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 4h6v6" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function MinimizeIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 11h8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M5 5l6 6M11 5l-6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" opacity="0.35" />
      <path d="M20 12a8 8 0 0 0-8-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function BuildIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M11 2.5a2.5 2.5 0 0 0-2.62 3.04L4 9.92 6.08 12l4.58-4.38A2.5 2.5 0 0 0 13.5 5 2.5 2.5 0 0 0 11 2.5Z"
        fill="currentColor"
      />
      <path d="M4 10l2 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function RunIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4.5 3.5v9l7-4.5-7-4.5Z" fill="currentColor" />
    </svg>
  );
}

function SaveIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M4 2.5h7.25L13.5 4.8v8.7H4z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 2.5v4h4v-4" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 11h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return "Operation canceled.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function formatRelative(timestamp?: string): string {
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

function formatWorkspaceLabel(workspaceId: string): string {
  if (workspaceId.length <= 12) {
    return workspaceId;
  }
  return `${workspaceId.slice(0, 6)}…${workspaceId.slice(-4)}`;
}

function decodeFileContent(payload: FileReadJson): string {
  if (payload.encoding === "base64") {
    if (typeof atob === "function") {
      return atob(payload.content);
    }
    const buffer = (globalThis as { Buffer?: { from: (data: string, encoding: string) => { toString: (encoding: string) => string } } }).Buffer;
    if (buffer) {
      return buffer.from(payload.content, "base64").toString("utf-8");
    }
  }
  return payload.content;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/ActivityBar.tsx
```tsx
import React from "react";
import clsx from "clsx";

export type ActivityBarView = "explorer" | "search" | "scm" | "extensions";

interface ActivityBarProps {
  readonly activeView: ActivityBarView;
  readonly onSelectView: (view: ActivityBarView) => void;
  readonly onOpenSettings: (event: React.MouseEvent<HTMLButtonElement>) => void;
  readonly appearance: "light" | "dark";
}

const ITEMS: Array<{ id: ActivityBarView; label: string; icon: React.ReactNode }> = [
  { id: "explorer", label: "Explorer", icon: <ExplorerIcon /> },
  { id: "search", label: "Search", icon: <SearchIcon /> },
  { id: "scm", label: "Source Control", icon: <SourceControlIcon /> },
  { id: "extensions", label: "Extensions", icon: <ExtensionsIcon /> },
];

export function ActivityBar({ activeView, onSelectView, onOpenSettings, appearance }: ActivityBarProps) {
  const theme =
    appearance === "dark"
      ? {
          bg: "bg-[#1b1b1f]",
          border: "border-[#111111]",
          iconIdle: "text-slate-400",
          iconActive: "text-[#4fc1ff]",
          hover: "hover:text-white hover:bg-white/5 focus-visible:text-white",
          indicator: "bg-[#4fc1ff]",
        }
      : {
          bg: "bg-[#f3f3f3]",
          border: "border-[#d0d0d0]",
          iconIdle: "text-slate-500",
          iconActive: "text-[#005fb8]",
          hover: "hover:text-[#0f172a] hover:bg-black/5 focus-visible:text-[#0f172a]",
          indicator: "bg-[#005fb8]",
        };

  return (
    <aside
      className={clsx(
        "flex h-full w-14 flex-col items-center justify-between border-r",
        theme.bg,
        theme.border,
        theme.iconIdle,
      )}
      aria-label="Workbench navigation"
    >
      <div className="flex flex-col items-center gap-1 py-3">
        {ITEMS.map((item) => {
          const active = activeView === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectView(item.id)}
              className={clsx(
                "relative flex h-10 w-10 items-center justify-center rounded-lg text-base transition",
                active ? theme.iconActive : clsx(theme.iconIdle, theme.hover),
              )}
              aria-label={item.label}
              aria-pressed={active}
            >
              {active ? (
                <span className={clsx("absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded", theme.indicator)} />
              ) : null}
              {item.icon}
            </button>
          );
        })}
      </div>
      <div className="flex flex-col items-center gap-3 pb-3">
        <button
          type="button"
          onClick={onOpenSettings}
          className={clsx(
            "flex h-10 w-10 items-center justify-center rounded-lg text-base transition",
            theme.iconIdle,
            theme.hover,
          )}
          aria-label="Open settings"
        >
          <GearIcon />
        </button>
      </div>
    </aside>
  );
}

function ExplorerIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect x="4" y="4" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4 8.25h12" stroke="currentColor" strokeWidth="1.2" />
      <path d="M8.25 4v12" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <circle cx="9" cy="9" r="4.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12.7 12.7l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function SourceControlIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6.5 4a1.75 1.75 0 1 1-1.5 0v12m9-8a1.75 1.75 0 1 1-1.5 0v8"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path d="M5 9.5h10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function ExtensionsIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6 4.5h4l4 4v6.5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.3"
      />
      <path d="M10 4.5v4h4" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M10 6.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M3 10h2m10 0h2M10 3v2m0 10v2M5.2 5.2l1.4 1.4m7 7 1.4 1.4M14.8 5.2l-1.4 1.4m-7 7-1.4 1.4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/BottomPanel.tsx
```tsx
import type { ConfigBuilderPane } from "@app/nav/urlState";
import type { ArtifactV1 } from "@schema";
import type { TelemetryEnvelope } from "@schema/adeTelemetry";
import type { RunStatus } from "@shared/runs/types";
import clsx from "clsx";

import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import type { WorkbenchConsoleLine, WorkbenchValidationState } from "../types";
import { ArtifactSummary, TelemetrySummary } from "@shared/runs/RunInsights";

export interface WorkbenchRunSummary {
  readonly runId: string;
  readonly status: RunStatus;
  readonly downloadBase: string;
  readonly outputs: ReadonlyArray<{ path: string; byte_size: number }>;
  readonly outputsLoaded: boolean;
  readonly artifact?: ArtifactV1 | null;
  readonly artifactLoaded: boolean;
  readonly artifactError?: string | null;
  readonly telemetry?: readonly TelemetryEnvelope[] | null;
  readonly telemetryLoaded: boolean;
  readonly telemetryError?: string | null;
  readonly documentName?: string;
  readonly sheetNames?: readonly string[];
  readonly error?: string | null;
}

interface BottomPanelProps {
  readonly height: number;
  readonly consoleLines: readonly WorkbenchConsoleLine[];
  readonly validation: WorkbenchValidationState;
  readonly activePane: ConfigBuilderPane;
  readonly onPaneChange: (pane: ConfigBuilderPane) => void;
  readonly latestRun?: WorkbenchRunSummary | null;
}

export function BottomPanel({
  height,
  consoleLines,
  validation,
  activePane,
  onPaneChange,
  latestRun,
}: BottomPanelProps) {
  const hasConsoleLines = consoleLines.length > 0;
  const statusLabel = describeValidationStatus(validation);
  const fallbackMessage = describeValidationFallback(validation);

  return (
    <section className="flex min-h-0 flex-col overflow-hidden border-t border-slate-200 bg-slate-50" style={{ height }}>
      <TabsRoot value={activePane} onValueChange={(value) => onPaneChange(value as ConfigBuilderPane)}>
        <div className="flex flex-none items-center justify-between border-b border-slate-200 px-3 py-2">
          <TabsList className="flex items-center gap-2">
            <TabsTrigger value="console" className="rounded px-2 py-1 text-xs uppercase tracking-wide">
              Console
            </TabsTrigger>
            <TabsTrigger value="validation" className="rounded px-2 py-1 text-xs uppercase tracking-wide">
              Validation
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="console" className="flex min-h-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-slate-900/80 bg-slate-950 font-mono text-[13px] leading-relaxed text-slate-100 shadow-inner shadow-black/30">
            <div className="flex flex-none items-center gap-3 border-b border-white/5 bg-slate-950/80 px-4 py-2 text-[11px] uppercase tracking-[0.35em] text-slate-500">
              <span className="font-semibold tracking-[0.45em] text-slate-200">Terminal</span>
              <span className="text-[10px] tracking-[0.45em] text-emerald-400">live</span>
            </div>
            <div className="flex-1 overflow-auto">
              {latestRun ? <RunSummaryCard summary={latestRun} /> : null}
              {hasConsoleLines ? (
                <ul className="divide-y divide-white/5">
                  {consoleLines.map((line, index) => (
                    <li
                      key={`${line.timestamp ?? index}-${line.message}`}
                      className="grid grid-cols-[auto_auto_1fr] items-baseline gap-4 px-4 py-2"
                    >
                      <span className="text-[11px] text-slate-500 tabular-nums whitespace-nowrap">
                        {formatConsoleTimestamp(line.timestamp)}
                      </span>
                      <span className={clsx("text-[11px] uppercase tracking-[0.3em]", consoleLevelClass(line.level))}>
                        {consoleLevelLabel(line.level)}
                      </span>
                      <span className="flex flex-wrap items-baseline gap-2 text-[13px] text-slate-100">
                        <span className={clsx("text-sm", consolePromptClass(line.level))}>$</span>
                        <span className={clsx("flex-1 whitespace-pre-wrap break-words", consoleLineClass(line.level))}>
                          {line.message}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-8 text-center text-[13px] text-slate-500">
                  <p className="tracking-wide text-slate-300">Waiting for ADE output…</p>
                  <p className="text-[12px] leading-relaxed text-slate-500">
                    Start a build or run validation to stream live logs in this terminal window.
                  </p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>
        <TabsContent value="validation" className="flex min-h-0 flex-1 flex-col overflow-auto px-3 py-2 text-sm">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
              <span>{statusLabel}</span>
              {validation.lastRunAt ? <span>Last run {formatRelative(validation.lastRunAt)}</span> : null}
            </div>
            {validation.messages.length > 0 ? (
              <ul className="space-y-2">
                {validation.messages.map((item, index) => (
                  <li key={`${item.level}-${item.path ?? index}-${index}`} className={validationMessageClass(item.level)}>
                    {item.path ? (
                      <span className="block text-xs font-medium uppercase tracking-wide text-slate-500">{item.path}</span>
                    ) : null}
                    <span>{item.message}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs leading-relaxed text-slate-500">{fallbackMessage}</p>
            )}
          </div>
        </TabsContent>
      </TabsRoot>
    </section>
  );
}

function RunSummaryCard({ summary }: { summary: WorkbenchRunSummary }) {
  const statusLabel = summary.status.charAt(0).toUpperCase() + summary.status.slice(1);
  return (
    <section className="border-b border-white/5 bg-slate-900/60 px-4 py-3 text-[13px] text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-slate-50" title={summary.runId}>
            Run {summary.runId}
          </p>
          <p className="text-xs text-slate-400">Status: {statusLabel}</p>
          {summary.documentName ? (
            <p className="text-xs text-slate-400">Document: {summary.documentName}</p>
          ) : null}
          {summary.sheetNames ? (
            <p className="text-xs text-slate-400">
              Worksheets:
              {summary.sheetNames.length === 0
                ? " All worksheets"
                : ` ${summary.sheetNames.join(", ")}`}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href={`${summary.downloadBase}/artifact`}
            className="inline-flex items-center rounded border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-800"
          >
            Download artifact
          </a>
          <a
            href={`${summary.downloadBase}/logfile`}
            className="inline-flex items-center rounded border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-800"
          >
            Download telemetry
          </a>
        </div>
      </div>
      <div className="mt-3 rounded-md border border-white/10 bg-slate-950/70 px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Output files</p>
        {summary.error ? (
          <p className="text-xs text-rose-300">{summary.error}</p>
        ) : !summary.outputsLoaded ? (
          <p className="text-xs text-slate-400">Loading outputs…</p>
        ) : summary.outputs.length > 0 ? (
          <ul className="mt-2 space-y-1 text-xs text-slate-100">
            {summary.outputs.map((file) => (
              <li key={file.path} className="flex items-center justify-between gap-2 break-all rounded border border-white/10 px-2 py-1">
                <a
                  href={`${summary.downloadBase}/outputs/${file.path.split("/").map(encodeURIComponent).join("/")}`}
                  className="text-emerald-400 hover:underline"
                >
                  {file.path}
                </a>
                <span className="text-[11px] text-slate-400">{file.byte_size.toLocaleString()} bytes</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-slate-400">No output files were generated.</p>
        )}
      </div>
      <div className="mt-3 rounded-md border border-white/10 bg-slate-950/70 px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Artifact summary</p>
        {summary.artifactError ? (
          <p className="text-xs text-rose-300">{summary.artifactError}</p>
        ) : !summary.artifactLoaded ? (
          <p className="text-xs text-slate-400">Loading artifact…</p>
        ) : summary.artifact ? (
          <ArtifactSummary artifact={summary.artifact} />
        ) : (
          <p className="text-xs text-slate-400">Artifact not available.</p>
        )}
      </div>
      <div className="mt-3 rounded-md border border-white/10 bg-slate-950/70 px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Telemetry summary</p>
        {summary.telemetryError ? (
          <p className="text-xs text-rose-300">{summary.telemetryError}</p>
        ) : !summary.telemetryLoaded ? (
          <p className="text-xs text-slate-400">Loading telemetry…</p>
        ) : summary.telemetry && summary.telemetry.length > 0 ? (
          <TelemetrySummary events={[...summary.telemetry]} />
        ) : (
          <p className="text-xs text-slate-400">No telemetry events captured.</p>
        )}
      </div>
    </section>
  );
}

const CONSOLE_PROMPTS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-[#569cd6]",
  warning: "text-[#dcdcaa]",
  error: "text-[#f48771]",
  success: "text-[#89d185]",
};

const CONSOLE_LINES: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-slate-100",
  warning: "text-amber-100",
  error: "text-rose-100",
  success: "text-emerald-100",
};

const CONSOLE_LEVELS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-slate-400",
  warning: "text-amber-400",
  error: "text-rose-400",
  success: "text-emerald-300",
};

const CONSOLE_LEVEL_LABELS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "INFO",
  warning: "WARN",
  error: "ERROR",
  success: "DONE",
};

function consolePromptClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_PROMPTS[level] ?? CONSOLE_PROMPTS.info;
}

function consoleLineClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_LINES[level] ?? CONSOLE_LINES.info;
}

function consoleLevelClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_LEVELS[level] ?? CONSOLE_LEVELS.info;
}

function consoleLevelLabel(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_LEVEL_LABELS[level] ?? CONSOLE_LEVEL_LABELS.info;
}

function validationMessageClass(level: WorkbenchValidationState["messages"][number]["level"]) {
  switch (level) {
    case "error":
      return "text-danger-600";
    case "warning":
      return "text-amber-600";
    default:
      return "text-slate-600";
  }
}

function describeValidationStatus(validation: WorkbenchValidationState): string {
  switch (validation.status) {
    case "running":
      return "Running validation...";
    case "success": {
      if (validation.messages.length === 0) {
        return "Validation completed with no issues.";
      }
      const count = validation.messages.length;
      return `Validation completed with ${count} ${count === 1 ? "issue" : "issues"}.`;
    }
    case "error":
      return validation.error ?? "Validation failed.";
    default:
      return "No validation run yet.";
  }
}

function formatRelative(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

function formatConsoleTimestamp(timestamp: WorkbenchConsoleLine["timestamp"]): string {
  if (!timestamp) {
    return " ";
  }
  // Keep ISO timestamps readable while preventing multi-line wrapping.
  const trimmed = timestamp.replace(/\s+/g, " ").trim();
  const longIso = Date.parse(trimmed);
  if (!Number.isNaN(longIso) && trimmed.includes("T")) {
    const date = new Date(longIso);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  return trimmed;
}

function describeValidationFallback(validation: WorkbenchValidationState): string {
  if (validation.status === "running") {
    return "Validation in progress...";
  }
  if (validation.status === "success") {
    return "No validation issues detected.";
  }
  if (validation.status === "error") {
    return validation.error ?? "Validation failed.";
  }
  return "Trigger validation from the workbench header to see ADE parsing results and manifest issues.";
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/EditorArea.tsx
```tsx
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";

import clsx from "clsx";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, useSortable, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { CodeEditor } from "@ui/CodeEditor";
import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import type { WorkbenchFileTab } from "../types";

type WorkbenchTabZone = "pinned" | "regular";

const SCROLL_STEP = 220;
const AUTO_SCROLL_THRESHOLD = 64;
const AUTO_SCROLL_SPEED = 14;

interface EditorAreaProps {
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly onSelectTab: (tabId: string) => void;
  readonly onCloseTab: (tabId: string) => void;
  readonly onCloseOtherTabs: (tabId: string) => void;
  readonly onCloseTabsToRight: (tabId: string) => void;
  readonly onCloseAllTabs: () => void;
  readonly onMoveTab: (tabId: string, targetIndex: number, options?: { zone?: WorkbenchTabZone }) => void;
  readonly onPinTab: (tabId: string) => void;
  readonly onUnpinTab: (tabId: string) => void;
  readonly onContentChange: (tabId: string, value: string) => void;
  readonly onSaveTab?: (tabId: string) => void;
  readonly onSaveAllTabs?: () => void;
  readonly onSelectRecentTab: (direction: "forward" | "backward") => void;
  readonly editorTheme: string;
  readonly menuAppearance: "light" | "dark";
  readonly canSaveFiles?: boolean;
  readonly minHeight?: number;
}

export function EditorArea({
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onCloseOtherTabs,
  onCloseTabsToRight,
  onCloseAllTabs,
  onMoveTab,
  onPinTab,
  onUnpinTab,
  onContentChange,
  onSaveTab,
  onSaveAllTabs,
  onSelectRecentTab,
  editorTheme,
  menuAppearance,
  canSaveFiles = false,
  minHeight,
}: EditorAreaProps) {
  const hasTabs = tabs.length > 0;
  const [contextMenu, setContextMenu] = useState<{ tabId: string; x: number; y: number } | null>(null);
  const [tabCatalogMenu, setTabCatalogMenu] = useState<{ x: number; y: number } | null>(null);
  const [draggingTabId, setDraggingTabId] = useState<string | null>(null);
  const [scrollShadow, setScrollShadow] = useState({ left: false, right: false });
  const [autoScrollDirection, setAutoScrollDirection] = useState<0 | -1 | 1>(0);

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const overflowButtonRef = useRef<HTMLButtonElement | null>(null);

  const activeTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0] ?? null,
    [tabs, activeTabId],
  );

  const pinnedTabs = useMemo(() => tabs.filter((tab) => tab.pinned), [tabs]);
  const regularTabs = useMemo(() => tabs.filter((tab) => !tab.pinned), [tabs]);
  const contentTabs = useMemo(() => tabs.slice().sort((a, b) => a.id.localeCompare(b.id)), [tabs]);
  const dirtyTabs = useMemo(
    () => tabs.filter((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [tabs],
  );
  const hasDirtyTabs = dirtyTabs.length > 0;

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    }),
  );

  useEffect(() => {
    if (!hasTabs) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }

      if (event.key.toLowerCase() === "w") {
        if (!activeTabId) {
          return;
        }
        event.preventDefault();
        onCloseTab(activeTabId);
        return;
      }

      if (event.key === "Tab") {
        if (tabs.length < 2) {
          return;
        }
        event.preventDefault();
        onSelectRecentTab(event.shiftKey ? "backward" : "forward");
        return;
      }

      const cycleVisual = (delta: number) => {
        if (tabs.length < 2) {
          return;
        }
        const currentIndex = tabs.findIndex((tab) => tab.id === activeTabId);
        const safeIndex = currentIndex >= 0 ? currentIndex : 0;
        const nextIndex = (safeIndex + delta + tabs.length) % tabs.length;
        const nextTab = tabs[nextIndex];
        if (nextTab) {
          onSelectTab(nextTab.id);
        }
      };

      if (event.key === "PageUp") {
        event.preventDefault();
        cycleVisual(-1);
        return;
      }

      if (event.key === "PageDown") {
        event.preventDefault();
        cycleVisual(1);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [hasTabs, tabs, activeTabId, onCloseTab, onSelectTab, onSelectRecentTab]);

  useEffect(() => {
    if (!contextMenu) {
      return;
    }
    if (!tabs.some((tab) => tab.id === contextMenu.tabId)) {
      setContextMenu(null);
    }
  }, [contextMenu, tabs]);

  const handleDragStart = (event: DragStartEvent) => {
    setDraggingTabId(String(event.active.id));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const activeId = event.active.id;
    const overId = event.over?.id;
    if (!overId) {
      setDraggingTabId(null);
      return;
    }
    if (activeId !== overId) {
      const activeIndex = tabs.findIndex((tab) => tab.id === activeId);
      const overIndex = tabs.findIndex((tab) => tab.id === overId);
      if (activeIndex !== -1 && overIndex !== -1) {
        const insertIndex = activeIndex < overIndex ? overIndex + 1 : overIndex;
        const overTab = tabs[overIndex];
        const zone: WorkbenchTabZone = overTab?.pinned ? "pinned" : "regular";
        onMoveTab(String(activeId), insertIndex, { zone });
      }
    }
    setDraggingTabId(null);
  };

  const handleDragCancel = () => {
    setDraggingTabId(null);
  };

  const updateScrollIndicators = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      setScrollShadow({ left: false, right: false });
      return;
    }
    const { scrollLeft, scrollWidth, clientWidth } = container;
    setScrollShadow({
      left: scrollLeft > 2,
      right: scrollLeft + clientWidth < scrollWidth - 2,
    });
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      setScrollShadow({ left: false, right: false });
      return;
    }
    updateScrollIndicators();
    const handleScroll = () => updateScrollIndicators();
    container.addEventListener("scroll", handleScroll);
    window.addEventListener("resize", updateScrollIndicators);
    const observer =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateScrollIndicators) : null;
    observer?.observe(container);
    return () => {
      container.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", updateScrollIndicators);
      observer?.disconnect();
    };
  }, [tabs.length, updateScrollIndicators]);

  useEffect(() => {
    if (!draggingTabId) {
      setAutoScrollDirection(0);
      return;
    }
    const handlePointerMove = (event: PointerEvent) => {
      const container = scrollContainerRef.current;
      if (!container) {
        setAutoScrollDirection(0);
        return;
      }
      const bounds = container.getBoundingClientRect();
      if (event.clientX < bounds.left + AUTO_SCROLL_THRESHOLD) {
        setAutoScrollDirection(-1);
      } else if (event.clientX > bounds.right - AUTO_SCROLL_THRESHOLD) {
        setAutoScrollDirection(1);
      } else {
        setAutoScrollDirection(0);
      }
    };
    window.addEventListener("pointermove", handlePointerMove);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      setAutoScrollDirection(0);
    };
  }, [draggingTabId]);

  useEffect(() => {
    if (!draggingTabId || autoScrollDirection === 0) {
      return;
    }
    let frame: number;
    const step = () => {
      const container = scrollContainerRef.current;
      if (!container) {
        return;
      }
      container.scrollBy({ left: autoScrollDirection * AUTO_SCROLL_SPEED });
      frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [autoScrollDirection, draggingTabId]);

  useEffect(() => {
    if (!activeTabId) {
      return;
    }
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }
    const selector = `[data-tab-id="${escapeAttributeValue(activeTabId)}"]`;
    const target = container.querySelector<HTMLElement>(selector);
    target?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }, [activeTabId, tabs.length]);

  const tabContextItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) {
      return [];
    }
    const currentTab = tabs.find((tab) => tab.id === contextMenu.tabId);
    if (!currentTab) {
      return [];
    }
    const tabIndex = tabs.findIndex((tab) => tab.id === contextMenu.tabId);
    const hasTabsToRight = tabIndex >= 0 && tabIndex < tabs.length - 1;
    const hasMultipleTabs = tabs.length > 1;
    const isDirty = currentTab.status === "ready" && currentTab.content !== currentTab.initialContent;
    const canSaveCurrent = Boolean(onSaveTab) && canSaveFiles && isDirty && !currentTab.saving;
    const canSaveAny = Boolean(onSaveAllTabs) && canSaveFiles && hasDirtyTabs;
    const shortcuts = {
      save: "Ctrl+S",
      saveAll: "Ctrl+Shift+S",
      close: "Ctrl+W",
      closeOthers: "Ctrl+K Ctrl+O",
      closeRight: "Ctrl+K Ctrl+Right",
      closeAll: "Ctrl+K Ctrl+W",
    };
    return [
      {
        id: "save",
        label: currentTab.saving ? "Saving…" : "Save",
        icon: <MenuIconSave />,
        disabled: !canSaveCurrent,
        shortcut: shortcuts.save,
        onSelect: () => onSaveTab?.(currentTab.id),
      },
      {
        id: "save-all",
        label: "Save All",
        icon: <MenuIconSaveAll />,
        disabled: !canSaveAny,
        shortcut: shortcuts.saveAll,
        onSelect: () => onSaveAllTabs?.(),
      },
      {
        id: "pin",
        label: currentTab.pinned ? "Unpin" : "Pin",
        icon: currentTab.pinned ? <MenuIconUnpin /> : <MenuIconPin />,
        dividerAbove: true,
        onSelect: () => (currentTab.pinned ? onUnpinTab(currentTab.id) : onPinTab(currentTab.id)),
      },
      {
        id: "close",
        label: "Close",
        icon: <MenuIconClose />,
        dividerAbove: true,
        shortcut: shortcuts.close,
        onSelect: () => onCloseTab(currentTab.id),
      },
      {
        id: "close-others",
        label: "Close Others",
        icon: <MenuIconCloseOthers />,
        disabled: !hasMultipleTabs,
        shortcut: shortcuts.closeOthers,
        onSelect: () => onCloseOtherTabs(currentTab.id),
      },
      {
        id: "close-right",
        label: "Close Tabs to the Right",
        icon: <MenuIconCloseRight />,
        disabled: !hasTabsToRight,
        shortcut: shortcuts.closeRight,
        onSelect: () => onCloseTabsToRight(currentTab.id),
      },
      {
        id: "close-all",
        label: "Close All",
        icon: <MenuIconCloseAll />,
        dividerAbove: true,
        disabled: tabs.length === 0,
        shortcut: shortcuts.closeAll,
        onSelect: () => onCloseAllTabs(),
      },
    ];
  }, [
    contextMenu,
    tabs,
    hasDirtyTabs,
    canSaveFiles,
    onPinTab,
    onUnpinTab,
    onCloseTab,
    onCloseOtherTabs,
    onCloseTabsToRight,
    onCloseAllTabs,
    onSaveTab,
    onSaveAllTabs,
  ]);

  const tabCatalogItems: ContextMenuItem[] = useMemo(() => {
    if (!hasTabs) {
      return [
        {
          id: "empty",
          label: "No open editors",
          onSelect: () => undefined,
          disabled: true,
        },
      ];
    }
    const items: ContextMenuItem[] = [];
    const appendItem = (tab: WorkbenchFileTab, dividerAbove: boolean) => {
      items.push({
        id: `switch-${tab.id}`,
        label: tab.name,
        icon: tab.pinned ? <MenuIconPin /> : <MenuIconFile />,
        shortcut: tab.id === activeTabId ? "Active" : undefined,
        dividerAbove,
        onSelect: () => onSelectTab(tab.id),
      });
    };
    pinnedTabs.forEach((tab) => appendItem(tab, false));
    regularTabs.forEach((tab, index) => appendItem(tab, index === 0 && pinnedTabs.length > 0));
    return items;
  }, [hasTabs, pinnedTabs, regularTabs, activeTabId, onSelectTab]);

  const scrollTabs = (delta: number) => {
    scrollContainerRef.current?.scrollBy({ left: delta, behavior: "smooth" });
  };

  const openTabListMenu = () => {
    if (typeof window === "undefined") {
      return;
    }
    const anchor = overflowButtonRef.current?.getBoundingClientRect();
    if (!anchor) {
      return;
    }
    setTabCatalogMenu({ x: anchor.left, y: anchor.bottom + 6 });
  };

  if (!hasTabs || !activeTab) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
        Select a file from the explorer to begin editing.
      </div>
    );
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col" style={minHeight ? { minHeight } : undefined}>
      <TabsRoot value={activeTab.id} onValueChange={onSelectTab}>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <SortableContext items={tabs.map((tab) => tab.id)} strategy={horizontalListSortingStrategy}>
            <div className="flex items-center gap-1 border-b border-slate-200 bg-slate-900/5 px-1">
              <ScrollButton
                direction="left"
                disabled={!scrollShadow.left}
                onClick={() => scrollTabs(-SCROLL_STEP)}
              />
              <div className="relative flex min-w-0 flex-1 items-stretch">
                {scrollShadow.left ? <ScrollGradient position="left" /> : null}
                {scrollShadow.right ? <ScrollGradient position="right" /> : null}
                <div
                  ref={scrollContainerRef}
                  className="flex min-w-0 flex-1 overflow-x-auto pb-1"
                  onWheel={(event) => {
                    if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
                      event.preventDefault();
                      scrollContainerRef.current?.scrollBy({ left: event.deltaY });
                    }
                  }}
                >
                  <TabsList className="flex min-h-[2.75rem] flex-1 items-end gap-0 px-1">
                    {tabs.map((tab) => {
                      const isDirty = tab.status === "ready" && tab.content !== tab.initialContent;
                      const isActive = tab.id === activeTab.id;
                      return (
                        <SortableTab
                          key={tab.id}
                          tab={tab}
                          isActive={isActive}
                          isDirty={isDirty}
                          draggingId={draggingTabId}
                          onContextMenu={(event) => {
                            event.preventDefault();
                            setContextMenu({ tabId: tab.id, x: event.clientX, y: event.clientY });
                          }}
                          onCloseTab={onCloseTab}
                        />
                      );
                    })}
                  </TabsList>
                </div>
              </div>
              <ScrollButton
                direction="right"
                disabled={!scrollShadow.right}
                onClick={() => scrollTabs(SCROLL_STEP)}
              />
              <button
                ref={overflowButtonRef}
                type="button"
                className="mx-1 flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition hover:bg-white hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                aria-label="Open editors list"
                onClick={openTabListMenu}
              >
                <ChevronDownIcon />
              </button>
            </div>
          </SortableContext>
        </DndContext>

        {contentTabs.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="flex min-h-0 min-w-0 flex-1">
            {tab.status === "loading" ? (
              <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
                Loading {tab.name}…
              </div>
            ) : tab.status === "error" ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-sm text-slate-500">
                <p>{tab.error ?? "Unable to load the file."}</p>
                <button
                  type="button"
                  className="rounded bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-500"
                  onClick={() => onSelectTab(tab.id)}
                >
                  Retry loading
                </button>
              </div>
            ) : (
              <div
                className={clsx(
                  "flex min-h-0 min-w-0 flex-1",
                  draggingTabId && "pointer-events-none select-none",
                )}
              >
                <CodeEditor
                  value={tab.content}
                  language={tab.language ?? "plaintext"}
                  path={tab.id}
                  theme={editorTheme}
                  onChange={(value) => onContentChange(tab.id, value ?? "")}
                  onSaveShortcut={() => {
                    if (!canSaveFiles) {
                      return;
                    }
                    onSaveTab?.(tab.id);
                  }}
                />
              </div>
            )}
          </TabsContent>
        ))}
      </TabsRoot>
      <ContextMenu
        open={Boolean(contextMenu)}
        position={contextMenu && { x: contextMenu.x, y: contextMenu.y }}
        onClose={() => setContextMenu(null)}
        items={tabContextItems}
        appearance={menuAppearance}
      />
      <ContextMenu
        open={Boolean(tabCatalogMenu)}
        position={tabCatalogMenu}
        onClose={() => setTabCatalogMenu(null)}
        items={tabCatalogItems}
        appearance={menuAppearance}
      />
    </div>
  );
}

interface SortableTabProps {
  readonly tab: WorkbenchFileTab;
  readonly isActive: boolean;
  readonly isDirty: boolean;
  readonly draggingId: string | null;
  readonly onContextMenu: (event: ReactMouseEvent<HTMLDivElement>) => void;
  readonly onCloseTab: (tabId: string) => void;
}

function SortableTab({ tab, isActive, isDirty, draggingId, onContextMenu, onCloseTab }: SortableTabProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: tab.id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  const showingDrag = isDragging || draggingId === tab.id;
  const isPinned = Boolean(tab.pinned);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={clsx(
        "group relative mr-1 flex min-w-0 items-stretch",
        showingDrag && "opacity-60",
      )}
      data-editor-tab="true"
      onContextMenu={onContextMenu}
      onMouseDown={(event) => {
        if (event.button === 1) {
          event.preventDefault();
          onCloseTab(tab.id);
        }
      }}
      {...attributes}
      {...listeners}
    >
      <TabsTrigger
        value={tab.id}
        data-tab-id={tab.id}
        title={tab.id}
        className={clsx(
          "relative flex min-w-[3rem] max-w-[16rem] items-center gap-2 overflow-hidden rounded-t-lg border px-2 py-1.5 pr-8 text-sm font-medium transition-[background-color,border-color,color] duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
          isActive
            ? "border-slate-200 border-b-white bg-white text-slate-900 shadow-[0_1px_0_rgba(15,23,42,0.08)]"
            : "border-transparent border-b-slate-200 text-slate-500 hover:border-slate-200 hover:bg-white/70 hover:text-slate-900",
          isPinned ? "min-w-[4rem] max-w-[8rem] justify-center" : "min-w-[9rem] justify-start px-3",
        )}
      >
        {isPinned ? (
          <span className="flex-none text-[12px]" aria-label="Pinned">
            <PinGlyph filled={isActive} />
          </span>
        ) : null}
        <span className="block min-w-0 flex-1 truncate text-left">{tab.name}</span>
        {tab.status === "loading" ? (
          <span
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-slate-400"
            aria-label="Loading"
          >
            ●
          </span>
        ) : null}
        {tab.status === "error" ? (
          <span
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-danger-600"
            aria-label="Load failed"
          >
            !
          </span>
        ) : null}
        {tab.saving ? (
          <span className="flex-none" aria-label="Saving" title="Saving changes…">
            <TabSavingSpinner />
          </span>
        ) : null}
        {tab.saveError ? (
          <span
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-danger-600"
            aria-label="Save failed"
            title={tab.saveError}
          >
            !
          </span>
        ) : null}
        {isDirty ? <span className="flex-none text-xs leading-none text-brand-600">●</span> : null}
      </TabsTrigger>
      <button
        type="button"
        className={clsx(
          "absolute right-1 top-1/2 -translate-y-1/2 rounded p-0.5 text-xs transition focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 focus-visible:ring-offset-white",
          isActive
            ? "text-slate-500 hover:bg-slate-200 hover:text-slate-900"
            : "text-slate-400 opacity-0 group-hover:opacity-100 hover:bg-slate-200 hover:text-slate-700",
        )}
        onClick={(event) => {
          event.stopPropagation();
          onCloseTab(tab.id);
        }}
        aria-label={`Close ${tab.name}`}
      >
        ×
      </button>
    </div>
  );
}

interface ScrollButtonProps {
  readonly direction: "left" | "right";
  readonly disabled: boolean;
  readonly onClick: () => void;
}

function ScrollButton({ direction, disabled, onClick }: ScrollButtonProps) {
  return (
    <button
      type="button"
      className={clsx(
        "flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
        disabled
          ? "cursor-default opacity-30"
          : "hover:bg-white hover:text-slate-900 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900/5",
      )}
      onClick={onClick}
      disabled={disabled}
      aria-label={direction === "left" ? "Scroll tabs left" : "Scroll tabs right"}
    >
      {direction === "left" ? <ChevronLeftIcon /> : <ChevronRightIcon />}
    </button>
  );
}

interface ScrollGradientProps {
  readonly position: "left" | "right";
}

function ScrollGradient({ position }: ScrollGradientProps) {
  return (
    <div
      className={clsx(
        "pointer-events-none absolute top-0 bottom-0 w-8",
        position === "left"
          ? "left-0 bg-gradient-to-r from-slate-100 via-slate-100/70 to-transparent"
          : "right-0 bg-gradient-to-l from-slate-100 via-slate-100/70 to-transparent",
      )}
    />
  );
}

function PinGlyph({ filled }: { readonly filled: boolean }) {
  return filled ? (
    <svg className="h-3 w-3" viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6.5 2.5h3l.5 4h2v1.5h-4V13l-1-.5V8H4V6.5h2z"
        fill="currentColor"
        className="text-slate-500"
      />
    </svg>
  ) : (
    <svg className="h-3 w-3" viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6.5 2.5h3l.5 4h2v1.5h-4V13l-1-.5V8H4V6.5h2z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        className="text-slate-400"
      />
    </svg>
  );
}

const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

function TabSavingSpinner() {
  return (
    <svg className="h-3 w-3 animate-spin text-brand-500" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
      <path
        d="M14 8a6 6 0 0 0-6-6"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MenuIconSave() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M4 2.5h7.5L13.5 5v8.5H4z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 2.5v4h4v-4" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 11h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconSaveAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 3.5h6l3 3v5.5h-9z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 3.5v3.5h3.5v-3.5" stroke="currentColor" strokeWidth="1.2" />
      <path d="M5 11h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path
        d="M6.5 6.5h6l1.5 1.5v4"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        opacity="0.6"
      />
    </svg>
  );
}

function MenuIconClose() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M4 4l8 8m0-8l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseOthers() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <rect x="2.5" y="3" width="8" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.2" fill="none" />
      <path d="M7 7l5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseRight() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 3v10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M7 5l5 3-5 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 6v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 4h3a1 1 0 0 1 1 1v7.5M12.5 12h-3a1 1 0 0 1-1-1V3.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path d="M5 6l6 6m0-6-6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconPin() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M5.5 2.5h5l.5 4h2v1.5h-4V13l-1-.5V8h-3V6.5h3z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function MenuIconUnpin() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 3.5l9 9M5.5 2.5h5l.5 4h2v1.5H10M8 8v4.5L7 12.5V8H4V6.5h1"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function MenuIconFile() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M5 2.5h4l2.5 2.5V13.5H5z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function escapeAttributeValue(value: string) {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Explorer.tsx
```tsx
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import clsx from "clsx";

import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";

import type { WorkbenchFileNode } from "../types";

type ExplorerTheme = "light" | "dark";

interface ExplorerThemeTokens {
  readonly surface: string;
  readonly border: string;
  readonly heading: string;
  readonly label: string;
  readonly textPrimary: string;
  readonly textMuted: string;
  readonly rowHover: string;
  readonly folderActiveBg: string;
  readonly selectionBg: string;
  readonly selectionText: string;
  readonly badgeActive: string;
  readonly badgeOpen: string;
  readonly folderIcon: string;
  readonly folderIconActive: string;
  readonly chevronIdle: string;
  readonly chevronActive: string;
}

const EXPLORER_THEME_TOKENS: Record<ExplorerTheme, ExplorerThemeTokens> = {
  dark: {
    surface: "#1e1e1e",
    border: "#252526",
    heading: "#cccccc",
    label: "#999999",
    textPrimary: "#f3f3f3",
    textMuted: "#c5c5c5",
    rowHover: "#2a2d2e",
    folderActiveBg: "transparent",
    selectionBg: "#2f3136",
    selectionText: "#f8f8f8",
    badgeActive: "#4fc1ff",
    badgeOpen: "#858585",
    folderIcon: "#c8ae7d",
    folderIconActive: "#e0c08e",
    chevronIdle: "#7a7a7a",
    chevronActive: "#d4d4d4",
  },
  light: {
    surface: "#f3f3f3",
    border: "#d4d4d4",
    heading: "#616161",
    label: "#8a8a8a",
    textPrimary: "#1e1e1e",
    textMuted: "#555555",
    rowHover: "#e8e8e8",
    folderActiveBg: "transparent",
    selectionBg: "#dcdcdc",
    selectionText: "#0f172a",
    badgeActive: "#0e639c",
    badgeOpen: "#6b6b6b",
    folderIcon: "#c0933a",
    folderIconActive: "#a67c32",
    chevronIdle: "#7a7a7a",
    chevronActive: "#3c3c3c",
  },
};

const FOCUS_RING_CLASS: Record<ExplorerTheme, string> = {
  dark: "focus-visible:ring-2 focus-visible:ring-[#007acc] focus-visible:ring-offset-2 focus-visible:ring-offset-[#252526]",
  light: "focus-visible:ring-2 focus-visible:ring-[#007acc] focus-visible:ring-offset-2 focus-visible:ring-offset-white",
};

function collectExpandedFolderIds(root: WorkbenchFileNode): Set<string> {
  const expanded = new Set<string>();
  const visit = (node: WorkbenchFileNode) => {
    expanded.add(node.id);
    node.children?.forEach((child) => {
      if (child.kind === "folder") {
        visit(child);
      }
    });
  };
  visit(root);
  return expanded;
}

interface ExplorerProps {
  readonly width: number;
  readonly tree: WorkbenchFileNode;
  readonly activeFileId: string;
  readonly openFileIds: readonly string[];
  readonly onSelectFile: (fileId: string) => void;
  readonly theme: ExplorerTheme;
  readonly onCloseFile: (fileId: string) => void;
  readonly onCloseOtherFiles: (fileId: string) => void;
  readonly onCloseTabsToRight: (fileId: string) => void;
  readonly onCloseAllFiles: () => void;
  readonly onHide: () => void;
}

export function Explorer({
  width,
  tree,
  activeFileId,
  openFileIds,
  onSelectFile,
  theme,
  onCloseFile,
  onCloseOtherFiles,
  onCloseTabsToRight,
  onCloseAllFiles,
  onHide,
}: ExplorerProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => collectExpandedFolderIds(tree));
  const [contextMenu, setContextMenu] = useState<{
    readonly node: WorkbenchFileNode;
    readonly position: { readonly x: number; readonly y: number };
  } | null>(null);

  useEffect(() => {
    setExpanded(collectExpandedFolderIds(tree));
  }, [tree]);

  const toggleFolder = useCallback((nodeId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const setFolderExpanded = useCallback(
    (nodeId: string, nextExpanded: boolean) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (nextExpanded) {
          next.add(nodeId);
        } else if (nodeId !== tree.id) {
          next.delete(nodeId);
        }
        if (!next.has(tree.id)) {
          next.add(tree.id);
        }
        return next;
      });
    },
    [tree.id],
  );

  const collapseAll = useCallback(() => {
    setExpanded(new Set([tree.id]));
  }, [tree.id]);

  const rootChildren = useMemo(() => tree.children ?? [], [tree]);
  const menuAppearance = theme === "dark" ? "dark" : "light";

  const handleNodeContextMenu = useCallback((event: React.MouseEvent, node: WorkbenchFileNode) => {
    event.preventDefault();
    setContextMenu({ node, position: { x: event.clientX, y: event.clientY } });
  }, []);

  const handleCopyPath = useCallback(async (path: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(path);
        return;
      } catch {
        // fall through to manual copy
      }
    }
    if (typeof document === "undefined") {
      return;
    }
    const textarea = document.createElement("textarea");
    textarea.value = path;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "absolute";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
  }, []);

  const explorerMenuItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) {
      return [];
    }
    const node = contextMenu.node;
    const shortcuts = {
      open: "Enter",
      close: "Ctrl+W",
      closeOthers: "Ctrl+K Ctrl+O",
      closeRight: "Ctrl+K Ctrl+Right",
      closeAll: "Ctrl+K Ctrl+W",
      copyPath: "Ctrl+K Ctrl+C",
      collapseAll: "Ctrl+K Ctrl+0",
    };
    if (node.kind === "file") {
      const isOpen = openFileIds.includes(node.id);
      const openCount = openFileIds.length;
      const tabIndex = openFileIds.indexOf(node.id);
      const hasTabsToRight = tabIndex >= 0 && tabIndex < openCount - 1;
      return [
        { id: "open-file", label: "Open", icon: <MenuIconOpenFile />, shortcut: shortcuts.open, onSelect: () => onSelectFile(node.id) },
        {
          id: "close-file",
          label: "Close",
          icon: <MenuIconClose />,
          disabled: !isOpen,
          shortcut: shortcuts.close,
          onSelect: () => onCloseFile(node.id),
        },
        {
          id: "close-file-others",
          label: "Close Others",
          icon: <MenuIconCloseOthers />,
          disabled: !isOpen || openCount <= 1,
          shortcut: shortcuts.closeOthers,
          onSelect: () => onCloseOtherFiles(node.id),
        },
        {
          id: "close-file-right",
          label: "Close Tabs to the Right",
          icon: <MenuIconCloseRight />,
          disabled: !isOpen || !hasTabsToRight,
          shortcut: shortcuts.closeRight,
          onSelect: () => onCloseTabsToRight(node.id),
        },
        {
          id: "close-file-all",
          label: "Close All",
          dividerAbove: true,
          disabled: openCount === 0,
          icon: <MenuIconCloseAll />,
          shortcut: shortcuts.closeAll,
          onSelect: () => onCloseAllFiles(),
        },
        {
          id: "copy-path",
          label: "Copy Path",
          dividerAbove: true,
          icon: <MenuIconCopyPath />,
          shortcut: shortcuts.copyPath,
          onSelect: () => {
            void handleCopyPath(node.id);
          },
        },
      ];
    }
    const isExpanded = expanded.has(node.id);
    return [
      {
        id: "toggle-folder",
        label: isExpanded ? "Collapse Folder" : "Expand Folder",
        icon: isExpanded ? <MenuIconCollapse /> : <MenuIconExpand />,
        onSelect: () => setFolderExpanded(node.id, !isExpanded),
      },
      {
        id: "collapse-all",
        label: "Collapse All",
        icon: <MenuIconCollapseAll />,
        shortcut: shortcuts.collapseAll,
        dividerAbove: true,
        onSelect: () => collapseAll(),
      },
      {
        id: "copy-path",
        label: "Copy Path",
        dividerAbove: true,
        icon: <MenuIconCopyPath />,
        shortcut: shortcuts.copyPath,
        onSelect: () => {
          void handleCopyPath(node.id);
        },
      },
    ];
  }, [
    contextMenu,
    openFileIds,
    onSelectFile,
    onCloseFile,
    onCloseOtherFiles,
    onCloseTabsToRight,
    onCloseAllFiles,
    handleCopyPath,
    expanded,
    setFolderExpanded,
    collapseAll,
  ]);
  const tokens = EXPLORER_THEME_TOKENS[theme];
  const focusRingClass = FOCUS_RING_CLASS[theme];

  return (
    <>
      <aside
        className="flex h-full min-h-0 flex-col border-r text-[13px]"
        style={{
          width,
          backgroundColor: tokens.surface,
          borderColor: tokens.border,
          color: tokens.textPrimary,
        }}
        aria-label="Config files explorer"
      >
        <div
          className="flex items-center justify-between border-b px-3 py-2"
          style={{ borderColor: tokens.border, backgroundColor: theme === "dark" ? "#181818" : "#ececec" }}
        >
          <div className="text-[11px] font-semibold uppercase tracking-[0.3em]" style={{ color: tokens.heading }}>
            Explorer
          </div>
          <button
            type="button"
            onClick={onHide}
            aria-label="Hide explorer"
            className={clsx(
              "flex h-7 w-7 items-center justify-center rounded-md transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#007acc]",
              theme === "dark"
                ? "text-slate-300 hover:bg-white/10 hover:text-white"
                : "text-slate-600 hover:bg-black/10 hover:text-slate-900",
            )}
          >
            <HideSidebarIcon />
          </button>
        </div>
        <nav className="flex-1 overflow-auto px-2 py-2" aria-label="Workspace files tree">
          <ul className="space-y-0.5">
            {rootChildren.map((node) => (
              <ExplorerNode
                key={node.id}
                node={node}
                depth={0}
                expanded={expanded}
                activeFileId={activeFileId}
                openFileIds={openFileIds}
                onToggleFolder={toggleFolder}
                onSelectFile={onSelectFile}
                tokens={tokens}
                focusRingClass={focusRingClass}
                onContextMenu={handleNodeContextMenu}
              />
            ))}
          </ul>
        </nav>
      </aside>
      <ContextMenu
        open={Boolean(contextMenu)}
        position={contextMenu && contextMenu.position}
        onClose={() => setContextMenu(null)}
        items={explorerMenuItems}
        appearance={menuAppearance}
      />
    </>
  );
}

interface ExplorerNodeProps {
  readonly node: WorkbenchFileNode;
  readonly depth: number;
  readonly expanded: ReadonlySet<string>;
  readonly activeFileId: string;
  readonly openFileIds: readonly string[];
  readonly onToggleFolder: (nodeId: string) => void;
  readonly onSelectFile: (fileId: string) => void;
  readonly tokens: ExplorerThemeTokens;
  readonly focusRingClass: string;
  readonly onContextMenu: (event: React.MouseEvent, node: WorkbenchFileNode) => void;
}

function ExplorerNode({
  node,
  depth,
  expanded,
  activeFileId,
  openFileIds,
  onToggleFolder,
  onSelectFile,
  tokens,
  focusRingClass,
  onContextMenu,
}: ExplorerNodeProps) {
  const paddingLeft = 8 + depth * 16;
  const baseStyle: CSSProperties & { ["--tree-hover-bg"]?: string } = {
    paddingLeft,
    ["--tree-hover-bg"]: tokens.rowHover,
  };

  if (node.kind === "folder") {
    const isOpen = expanded.has(node.id);
    const folderStyle: CSSProperties = {
      ...baseStyle,
      color: isOpen ? tokens.textPrimary : tokens.textMuted,
    };
    if (isOpen && tokens.folderActiveBg !== "transparent") {
      folderStyle.backgroundColor = tokens.folderActiveBg;
    }

    return (
      <li className="relative">
        <button
          type="button"
          onClick={() => onToggleFolder(node.id)}
          onContextMenu={(event) => onContextMenu(event, node)}
          className={clsx(
            "group flex w-full items-center gap-2 rounded-md px-2 py-1 text-left font-medium transition hover:bg-[var(--tree-hover-bg)]",
            focusRingClass,
          )}
          style={folderStyle}
          aria-expanded={isOpen}
        >
          <ChevronIcon open={isOpen} tokens={tokens} />
          <FolderIcon open={isOpen} tokens={tokens} />
          <span className="truncate">{node.name}</span>
        </button>
        {isOpen && node.children?.length ? (
          <ul className="mt-0.5 space-y-0.5">
            {node.children.map((child) => (
              <ExplorerNode
                key={child.id}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              activeFileId={activeFileId}
              openFileIds={openFileIds}
              onToggleFolder={onToggleFolder}
              onSelectFile={onSelectFile}
              tokens={tokens}
              focusRingClass={focusRingClass}
              onContextMenu={onContextMenu}
            />
            ))}
          </ul>
        ) : null}
      </li>
    );
  }

  const isActive = activeFileId === node.id;
  const isOpen = openFileIds.includes(node.id);
  const fileAccent = getFileAccent(node.name, node.language);
  const fileStyle: CSSProperties = { ...baseStyle, color: tokens.textPrimary };
  if (isActive) {
    fileStyle.backgroundColor = tokens.selectionBg;
    fileStyle.color = tokens.selectionText;
  }

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelectFile(node.id)}
        onContextMenu={(event) => onContextMenu(event, node)}
        className={clsx(
          "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left transition hover:bg-[var(--tree-hover-bg)]",
          focusRingClass,
          isActive && "shadow-inner shadow-[#00000033]",
        )}
        style={fileStyle}
      >
        <span className="inline-flex w-4 justify-center">
          <FileIcon className={fileAccent} />
        </span>
        <span className="flex-1 truncate">{node.name}</span>
        {isActive ? (
          <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: tokens.badgeActive }}>
            Active
          </span>
        ) : isOpen ? (
          <span className="text-[9px] uppercase tracking-wide" style={{ color: tokens.badgeOpen }}>
            Open
          </span>
        ) : null}
      </button>
    </li>
  );
}

const FILE_ICON_COLORS: Record<string, string> = {
  json: "text-[#f1d06b]",
  py: "text-[#519aba]",
  ts: "text-[#519aba]",
  tsx: "text-[#519aba]",
  js: "text-[#f4d13d]",
  jsx: "text-[#519aba]",
  md: "text-[#4ec9b0]",
  env: "text-[#b5cea8]",
  txt: "text-[#9cdcfe]",
  lock: "text-[#c586c0]",
};

function getFileAccent(name: string, language?: string) {
  if (language === "python") {
    return "text-sky-300";
  }
  const segments = name.toLowerCase().split(".");
  const extension = segments.length > 1 ? segments.pop() ?? "" : "";
  if (extension && FILE_ICON_COLORS[extension]) {
    return FILE_ICON_COLORS[extension];
  }
  return "text-slate-400";
}

function ChevronIcon({ open, tokens }: { readonly open: boolean; readonly tokens: ExplorerThemeTokens }) {
  return (
    <svg
      className={clsx(
        "h-3 w-3 flex-shrink-0 transition-transform duration-150",
        open ? "rotate-90" : undefined,
      )}
      viewBox="0 0 10 10"
      aria-hidden
    >
      <path
        d="M3 1l4 4-4 4"
        stroke={open ? tokens.chevronActive : tokens.chevronIdle}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function FolderIcon({ open, tokens }: { readonly open: boolean; readonly tokens: ExplorerThemeTokens }) {
  return (
    <svg className="h-4 w-4 flex-shrink-0 transition-colors" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M3.5 5.5h4l1.5 1.5H16a1 1 0 0 1 1 1V15a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6.5a1 1 0 0 1 1-1Z"
        stroke={open ? tokens.folderIconActive : tokens.folderIcon}
        strokeWidth={1.4}
        strokeLinejoin="round"
        fill={open ? tokens.folderIconActive : "none"}
        opacity={open ? 0.25 : 1}
      />
    </svg>
  );
}

function FileIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={clsx("h-4 w-4 flex-shrink-0", className)} viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6 3h4l4 4v9a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth={1.3}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M10 3v4h4" stroke="currentColor" strokeWidth={1.3} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HideSidebarIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M3 3h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 13h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 8h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M11 5l2 3-2 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

function MenuIconOpenFile() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3 4.5h3l1 1H13a1 1 0 0 1 1 1V12.5a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.2"
        fill="none"
      />
    </svg>
  );
}

function MenuIconCopyPath() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6 4.5h5.5a1 1 0 0 1 1 1V13"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
      <rect x="3.5" y="2.5" width="6" height="9" rx="1" stroke="currentColor" strokeWidth="1.1" fill="none" />
    </svg>
  );
}

function MenuIconCollapse() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 6l3 3 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MenuIconExpand() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 10l3-3 3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MenuIconCollapseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M3 5h10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 8h6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 11h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconClose() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M4 4l8 8m0-8l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseOthers() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <rect x="2.5" y="3" width="8" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.2" fill="none" />
      <path d="M7 7l5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseRight() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 3v10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M7 5l5 3-5 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 6v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 4.5h3.5a1 1 0 0 1 1 1V13M12.5 11.5h-3.5a1 1 0 0 1-1-1V3"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
      <path d="M4.5 6.5l7 7m0-7-7 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Inspector.tsx
```tsx
import type { WorkbenchFileTab } from "../types";

interface InspectorProps {
  readonly width: number;
  readonly file: WorkbenchFileTab | null;
}

export function Inspector({ width, file }: InspectorProps) {
  if (!file) {
    return null;
  }
  const isDirty = file.status === "ready" && file.content !== file.initialContent;
  const metadata = file.metadata;

  return (
    <aside className="flex h-full min-h-0 flex-shrink-0 flex-col border-l border-slate-200 bg-slate-50" style={{ width }}>
      <header className="border-b border-slate-200 px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Inspector</h2>
      </header>
      <div className="flex-1 space-y-4 overflow-auto px-3 py-4 text-sm text-slate-600">
        <section className="space-y-2 text-xs">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-slate-500">File</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-slate-500">Name</dt>
              <dd className="text-slate-700">{file.name}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Path</dt>
              <dd className="break-words text-slate-700">{file.id}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Language</dt>
              <dd className="text-slate-700">{file.language ?? "plain text"}</dd>
            </div>
          </dl>
        </section>

        <section className="space-y-2 text-xs">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-slate-500">Metadata</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-slate-500">Size</dt>
              <dd className="text-slate-700">{formatFileSize(metadata?.size)}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Last modified</dt>
              <dd className="text-slate-700">{formatTimestamp(metadata?.modifiedAt)}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Content type</dt>
              <dd className="text-slate-700">{metadata?.contentType ?? "—"}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">ETag</dt>
              <dd className="break-words text-slate-700">{metadata?.etag ?? "—"}</dd>
            </div>
          </dl>
        </section>

        <section className="space-y-2 text-xs">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-slate-500">Editor</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-slate-500">Load status</dt>
              <dd className="text-slate-700 capitalize">{file.status}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Dirty</dt>
              <dd className="text-slate-700">{isDirty ? "Yes" : "No"}</dd>
            </div>
          </dl>
        </section>

        <p className="text-xs leading-relaxed text-slate-500">
          The inspector stays in sync with the active tab. Future work can hydrate this panel with schema-aware helpers and
          quick actions without reworking the layout.
        </p>
      </div>
    </aside>
  );
}

function formatFileSize(size: number | null | undefined): string {
  if (size == null) {
    return "—";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  const units = ["KB", "MB", "GB"];
  let value = size / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`;
}

function formatTimestamp(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return "—";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/PanelResizeHandle.tsx
```tsx
import type { PointerEventHandler } from "react";

interface PanelResizeHandleProps {
  readonly orientation: "horizontal" | "vertical";
  readonly onPointerDown: PointerEventHandler<HTMLDivElement>;
}

export function PanelResizeHandle({ orientation, onPointerDown }: PanelResizeHandleProps) {
  const isVertical = orientation === "vertical";
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={
        isVertical
          ? "w-1 cursor-col-resize select-none bg-transparent"
          : "h-1 cursor-row-resize select-none bg-transparent"
      }
      style={{ touchAction: "none" }}
      onPointerDown={onPointerDown}
    >
      <span className="sr-only">Resize panel</span>
    </div>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/index.tsx
```tsx
import { useEffect } from "react";

import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@features/Workspace/context/WorkspaceContext";
import { useWorkbenchWindow } from "@features/Workspace/context/WorkbenchWindowContext";
import { useConfigQuery } from "@shared/configs/hooks/useConfigsQuery";

import { Workbench } from "./Workbench";

interface ConfigEditorWorkbenchRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function ConfigEditorWorkbenchRoute({ params }: ConfigEditorWorkbenchRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const {
    session,
    windowState,
    openSession,
    closeSession,
    minimizeWindow,
    maximizeWindow,
    restoreWindow,
    shouldBypassUnsavedGuard,
  } = useWorkbenchWindow();
  const configId = params?.configId;
  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId });

  useEffect(() => {
    if (configId) {
      return;
    }
    closeSession();
  }, [configId, closeSession]);

  useEffect(() => {
    if (!configId) {
      return;
    }
    const resolvedName = configQuery.data?.display_name ?? configId;
    openSession({
      workspaceId: workspace.id,
      configId,
      configName: `${workspace.name} · ${resolvedName}`,
    });
  }, [configId, configQuery.data?.display_name, workspace.id, workspace.name, openSession]);

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Select a configuration"
        description="Choose a configuration from the list to open the workbench."
      />
    );
  }

  const activeSession = session && session.configId === configId ? session : null;
  const isDocked = Boolean(activeSession && windowState === "minimized");
  const showWorkbenchInline = Boolean(activeSession && windowState === "restored");
  const showMaximizedNotice = Boolean(activeSession && windowState === "maximized");

  if (showWorkbenchInline && activeSession) {
    return (
      <div className="flex h-full min-h-0 flex-1 flex-col">
        <Workbench
          workspaceId={workspace.id}
          configId={activeSession.configId}
          configName={activeSession.configName}
          windowState="restored"
          onMinimizeWindow={minimizeWindow}
          onMaximizeWindow={maximizeWindow}
          onRestoreWindow={restoreWindow}
          onCloseWorkbench={closeSession}
          shouldBypassUnsavedGuard={shouldBypassUnsavedGuard}
        />
      </div>
    );
  }

  if (showMaximizedNotice) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
        <PageState
          variant="empty"
          title="Immersive focus active"
          description="Exit immersive mode from the workbench focus menu to return here."
        />
      </div>
    );
  }

  if (isDocked) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
        <PageState
          variant="empty"
          title="Workbench docked"
          description="Use the dock at the bottom of the screen to resume editing."
        />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
      <PageState
        variant="loading"
        title="Launching config workbench"
        description="If the editor does not appear, refresh the page."
      />
    </div>
  );
}
```

# apps/ade-web/vite.config.ts
```typescript
import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";
import react from "@vitejs/plugin-react";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));
const resolveSrc = (relativePath: string) => path.resolve(projectRoot, "src", relativePath);

const frontendPort = Number.parseInt(process.env.DEV_FRONTEND_PORT ?? "8000", 10);
const backendPort = process.env.DEV_BACKEND_PORT ?? "8000";

export default defineConfig({
  plugins: [tailwindcss(), react(), tsconfigPaths()],
  resolve: {
    alias: {
      "@app": resolveSrc("app"),
      "@features": resolveSrc("screens"),
      "@ui": resolveSrc("ui"),
      "@shared": resolveSrc("shared"),
      "@schema": resolveSrc("schema"),
      "@generated-types": resolveSrc("generated-types"),
      "@test": resolveSrc("test"),
    },
  },
  server: {
    port: Number.isNaN(frontendPort) ? 8000 : frontendPort,
    host: process.env.DEV_FRONTEND_HOST ?? "0.0.0.0",
    proxy: {
      "/api": {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
});
```

# apps/ade-web/vitest.config.ts
```typescript
import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@app": fileURLToPath(new URL("./src/app", import.meta.url)),
      "@features": fileURLToPath(new URL("./src/screens", import.meta.url)),
      "@shared": fileURLToPath(new URL("./src/shared", import.meta.url)),
      "@ui": fileURLToPath(new URL("./src/ui", import.meta.url)),
      "@schema": fileURLToPath(new URL("./src/schema", import.meta.url)),
      "@generated-types": fileURLToPath(new URL("./src/generated-types", import.meta.url)),
      "@test": fileURLToPath(new URL("./src/test", import.meta.url)),
    },
  },
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
});
```
