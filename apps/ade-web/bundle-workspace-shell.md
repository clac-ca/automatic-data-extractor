# Logical module layout (source -> sections below):
# - apps/ade-web/README.md
# - apps/ade-web/src/app/App.tsx
# - apps/ade-web/src/app/AppProviders.tsx
# - apps/ade-web/src/app/nav/Link.tsx
# - apps/ade-web/src/app/nav/history.tsx
# - apps/ade-web/src/app/nav/urlState.ts
# - apps/ade-web/src/main.tsx
# - apps/ade-web/src/screens/Workspace/components/WorkspaceNav.tsx
# - apps/ade-web/src/screens/Workspace/components/workspace-navigation.tsx
# - apps/ade-web/src/screens/Workspace/index.tsx
# - apps/ade-web/src/screens/Workspaces/New/hooks/useCreateWorkspaceMutation.ts
# - apps/ade-web/src/screens/Workspaces/New/index.tsx
# - apps/ade-web/src/screens/Workspaces/components/WorkspaceDirectoryLayout.tsx
# - apps/ade-web/src/screens/Workspaces/index.tsx
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

# apps/ade-web/src/screens/Workspace/components/WorkspaceNav.tsx
```tsx
import { NavLink } from "@app/nav/Link";
import clsx from "clsx";

import { getWorkspacePrimaryNavigation, type WorkspaceNavigationItem } from "@features/Workspace/components/workspace-navigation";
import type { WorkspaceProfile } from "@features/Workspace/api/workspaces-api";

const COLLAPSED_NAV_WIDTH = "4.25rem";
const EXPANDED_NAV_WIDTH = "18.75rem";

export interface WorkspaceNavProps {
  readonly workspace: WorkspaceProfile;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly items?: readonly WorkspaceNavigationItem[];
  readonly onGoToWorkspaces: () => void;
}

export function WorkspaceNav({ workspace, collapsed, onToggleCollapse, items, onGoToWorkspaces }: WorkspaceNavProps) {
  const navItems = items ?? getWorkspacePrimaryNavigation(workspace);
  const workspaceInitials = getWorkspaceInitials(workspace.name);

  return (
    <aside
      className="hidden h-screen flex-shrink-0 bg-gradient-to-b from-slate-50/80 via-white to-slate-50/60 px-3 py-4 transition-[width] duration-200 ease-out lg:flex"
      style={{ width: collapsed ? COLLAPSED_NAV_WIDTH : EXPANDED_NAV_WIDTH }}
      aria-label="Primary workspace navigation"
      aria-expanded={!collapsed}
    >
      <div
        className={clsx(
          "flex h-full w-full flex-col rounded-[1.7rem] border border-white/70 bg-white/90 shadow-[0_25px_60px_-40px_rgba(15,23,42,0.7)] ring-1 ring-slate-100/60 backdrop-blur-sm",
          collapsed ? "items-center gap-4 px-2 py-5" : "gap-5 px-4 py-6",
        )}
      >
        <div
          className={clsx(
            "flex w-full items-center gap-3 rounded-2xl border border-white/80 bg-gradient-to-r from-slate-50 via-white to-slate-50 px-3 py-4 text-sm font-semibold text-slate-700 shadow-inner shadow-white/60",
            collapsed ? "flex-col text-center text-xs" : "",
          )}
        >
          <button
            type="button"
            onClick={onGoToWorkspaces}
            className="flex flex-1 items-center gap-3 text-left"
          >
            <span
              className={clsx(
                "inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-bold uppercase text-white shadow-[0_10px_25px_-10px_rgba(79,70,229,0.7)]",
                collapsed && "h-9 w-9 text-xs",
              )}
            >
              {workspaceInitials}
            </span>
            {collapsed ? (
              <span className="sr-only">{workspace.name}</span>
            ) : (
              <div className="min-w-0">
                <p className="truncate">{workspace.name}</p>
                <p className="text-xs font-normal text-slate-500">Switch workspace</p>
              </div>
            )}
          </button>
          <button
            type="button"
            onClick={onToggleCollapse}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-transparent text-slate-500 hover:border-brand-200 hover:text-brand-600"
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? <ExpandIcon /> : <CollapseIcon />}
          </button>
        </div>
        <nav className="mt-4 flex-1 overflow-y-auto pr-1" aria-label="Workspace sections">
          <WorkspaceNavList items={navItems} collapsed={collapsed} />
        </nav>
      </div>
    </aside>
  );
}

interface WorkspaceNavListProps {
  readonly items: readonly WorkspaceNavigationItem[];
  readonly collapsed?: boolean;
  readonly onNavigate?: () => void;
  readonly className?: string;
  readonly showHeading?: boolean;
}

export function WorkspaceNavList({
  items,
  collapsed = false,
  onNavigate,
  className,
  showHeading = true,
}: WorkspaceNavListProps) {
  return (
    <>
      {showHeading && !collapsed ? (
        <p className="mb-3 px-1 text-[0.63rem] font-semibold uppercase tracking-[0.4em] text-slate-400/90">Workspace</p>
      ) : null}
      <ul className={clsx("flex flex-col gap-1.5", collapsed ? "items-center" : undefined, className)} role="list">
        {items.map((item) => (
          <li key={item.id} className="w-full">
            <NavLink
              to={item.href}
              end
              title={collapsed ? item.label : undefined}
              onClick={onNavigate}
              className={({ isActive }) =>
                clsx(
                  "group relative flex w-full items-center rounded-2xl border border-transparent text-sm font-medium text-slate-600 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white/80",
                  collapsed ? "h-11 justify-center px-0" : "gap-3 px-3 py-2.5",
                  isActive
                    ? "border-brand-100 bg-white/90 text-slate-900 shadow-[0_12px_30px_-20px_rgba(79,70,229,0.55)]"
                    : "border-transparent hover:border-slate-200 hover:bg-white/70",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    aria-hidden
                    className={clsx(
                      "absolute left-1.5 top-2 bottom-2 w-1 rounded-full bg-gradient-to-b from-brand-400 to-brand-500 opacity-0 transition-opacity duration-150",
                      collapsed && "hidden",
                      isActive ? "opacity-100" : "group-hover:opacity-60",
                    )}
                  />
                  <span
                    aria-hidden
                    className={clsx(
                      "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500 transition",
                      collapsed && "h-9 w-9 rounded-lg",
                      isActive ? "bg-brand-50 text-brand-600" : "group-hover:bg-slate-100/80",
                    )}
                  >
                    <item.icon
                      className={clsx(
                        "h-5 w-5 flex-shrink-0 transition-colors duration-150",
                        isActive ? "text-brand-600" : "text-slate-500",
                      )}
                    />
                  </span>
                  <div className={clsx("flex min-w-0 flex-col text-left", collapsed && "sr-only")}>
                    <span className="truncate text-sm font-semibold text-slate-900">{item.label}</span>
                  </div>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </>
  );
}

function CollapseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path d="M12.5 6 9 10l3.5 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ExpandIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path d="m7.5 6 3.5 4-3.5 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function getWorkspaceInitials(name: string) {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) {
    return "WS";
  }
  const initials = parts.slice(0, 2).map((part) => part[0] ?? "");
  return initials.join("").toUpperCase();
}
```

# apps/ade-web/src/screens/Workspace/components/workspace-navigation.tsx
```tsx
import type { ComponentType, SVGProps } from "react";

import type { WorkspaceProfile } from "@features/Workspace/api/workspaces-api";

interface IconProps extends SVGProps<SVGSVGElement> {
  readonly title?: string;
}

function createIcon(path: string) {
  return function Icon({ title, ...props }: IconProps) {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden={title ? undefined : true}
        role={title ? "img" : "presentation"}
        {...props}
      >
        {title ? <title>{title}</title> : null}
        <path d={path} />
      </svg>
    );
  };
}

const DocumentsIcon = createIcon(
  "M7 3h7l7 7v11a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM14 3v5a1 1 0 0 0 1 1h5",
);

const RunsIcon = createIcon(
  "M5 6h14M5 12h14M5 18h8M7 4v4M12 10v4M15 16v4",
);

const ConfigureIcon = createIcon(
  "M5 5h5v5H5zM14 5h5v5h-5zM5 14h5v5H5zM16.5 12a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM10 7.5h4M7.5 10v4M15.5 10.5 12 14",
);

const SettingsIcon = createIcon(
  "M5 7h14M5 17h14M9 7a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm10 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm-7-5h7m-9 0H5",
);

export const DirectoryIcon = createIcon(
  "M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4v-5h-6v5H5a1 1 0 0 1-1-1v-8.5Z",
);

type WorkspaceSectionId = "documents" | "runs" | "config-builder" | "settings";

interface WorkspaceSectionDescriptor {
  readonly id: WorkspaceSectionId;
  readonly path: string;
  readonly label: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
}

const workspaceSections: readonly WorkspaceSectionDescriptor[] = [
  {
    id: "documents",
    path: "documents",
    label: "Documents",
    icon: DocumentsIcon,
  },
  {
    id: "runs",
    path: "runs",
    label: "Runs",
    icon: RunsIcon,
  },
  {
    id: "config-builder",
    path: "config-builder",
    label: "Config Builder",
    icon: ConfigureIcon,
  },
  {
    id: "settings",
    path: "settings",
    label: "Workspace Settings",
    icon: SettingsIcon,
  },
] as const;

export const defaultWorkspaceSection = workspaceSections[0];

export interface WorkspaceNavigationItem {
  readonly id: WorkspaceSectionId;
  readonly label: string;
  readonly href: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
}

export function getWorkspacePrimaryNavigation(workspace: WorkspaceProfile): WorkspaceNavigationItem[] {
  return workspaceSections.map((section) => ({
    id: section.id,
    label: section.label,
    href: `/workspaces/${workspace.id}/${section.path}`,
    icon: section.icon,
  }));
}
```

# apps/ade-web/src/screens/Workspace/index.tsx
```tsx
import { useCallback, useEffect, useMemo, useState, type ReactElement } from "react";

import clsx from "clsx";

import { useLocation, useNavigate } from "@app/nav/history";
import { useQueryClient } from "@tanstack/react-query";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useWorkspacesQuery, workspacesKeys, WORKSPACE_LIST_DEFAULT_PARAMS, type WorkspaceProfile } from "@features/Workspace/api/workspaces-api";
import { WorkspaceProvider } from "@features/Workspace/context/WorkspaceContext";
import { WorkbenchWindowProvider, useWorkbenchWindow } from "@features/Workspace/context/WorkbenchWindowContext";
import { createScopedStorage } from "@shared/storage";
import { writePreferredWorkspace } from "@features/Workspace/state/workspace-preferences";
import { GlobalTopBar } from "@app/shell/GlobalTopBar";
import { ProfileDropdown } from "@app/shell/ProfileDropdown";
import { WorkspaceNav, WorkspaceNavList } from "@features/Workspace/components/WorkspaceNav";
import { defaultWorkspaceSection, getWorkspacePrimaryNavigation } from "@features/Workspace/components/workspace-navigation";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@shared/system";
import { Alert } from "@ui/Alert";
import { PageState } from "@ui/PageState";
import { useShortcutHint } from "@shared/hooks/useShortcutHint";
import type { GlobalSearchSuggestion } from "@app/shell/GlobalTopBar";
import { NotificationsProvider } from "@shared/notifications";

import WorkspaceOverviewRoute from "@features/Workspace/sections/Overview";
import WorkspaceDocumentsRoute from "@features/Workspace/sections/Documents";
import DocumentDetailRoute from "@features/Workspace/sections/Documents/components/DocumentDetail";
import WorkspaceRunsRoute from "@features/Workspace/sections/Runs";
import WorkspaceConfigsIndexRoute from "@features/Workspace/sections/ConfigBuilder";
import WorkspaceConfigRoute from "@features/Workspace/sections/ConfigBuilder/detail";
import ConfigEditorWorkbenchRoute from "@features/Workspace/sections/ConfigBuilder/workbench";
import WorkspaceSettingsRoute from "@features/Workspace/sections/Settings";

type WorkspaceSectionRender =
  | { readonly kind: "redirect"; readonly to: string }
  | { readonly kind: "content"; readonly key: string; readonly element: ReactElement; readonly fullHeight?: boolean };

export default function WorkspaceScreen() {
  return (
    <RequireSession>
      <WorkspaceContent />
    </RequireSession>
  );
}

function WorkspaceContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces = useMemo(
    () => workspacesQuery.data?.items ?? [],
    [workspacesQuery.data?.items],
  );
  const identifier = extractWorkspaceIdentifier(location.pathname);
  const workspace = useMemo(() => findWorkspace(workspaces, identifier), [workspaces, identifier]);

  useEffect(() => {
    if (workspacesQuery.data) {
      queryClient.setQueryData(
        workspacesKeys.list(WORKSPACE_LIST_DEFAULT_PARAMS),
        workspacesQuery.data,
      );
    }
  }, [queryClient, workspacesQuery.data]);

  useEffect(() => {
    if (!workspacesQuery.isLoading && !workspacesQuery.isError && workspaces.length === 0) {
      navigate("/workspaces", { replace: true });
    }
  }, [workspacesQuery.isLoading, workspacesQuery.isError, workspaces.length, navigate]);

  useEffect(() => {
    if (workspace && !identifier) {
      navigate(`/workspaces/${workspace.id}/${defaultWorkspaceSection.path}${location.search}${location.hash}`, {
        replace: true,
      });
    }
  }, [workspace, identifier, location.search, location.hash, navigate]);

  useEffect(() => {
    if (!workspace || !identifier) {
      return;
    }

    if (identifier !== workspace.id) {
      const canonical = buildCanonicalPath(location.pathname, location.search, workspace.id, identifier);
      if (canonical !== location.pathname + location.search) {
        navigate(canonical + location.hash, { replace: true });
      }
    }
  }, [workspace, identifier, location.pathname, location.search, location.hash, navigate]);

  useEffect(() => {
    if (workspace) {
      writePreferredWorkspace(workspace);
    }
  }, [workspace]);


  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState title="Loading workspace" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 px-6 text-center">
        <PageState
          title="Unable to load workspace"
          description="We were unable to fetch workspace information. Refresh the page to try again."
          variant="error"
        />
        <button
          type="button"
          className="focus-ring rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100"
          onClick={() => workspacesQuery.refetch()}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!workspace) {
    return null;
  }

  return (
    <WorkspaceProvider workspace={workspace} workspaces={workspaces}>
      <WorkspaceShell workspace={workspace} />
    </WorkspaceProvider>
  );
}

interface WorkspaceShellProps {
  readonly workspace: WorkspaceProfile;
}

function WorkspaceShell({ workspace }: WorkspaceShellProps) {
  return (
    <NotificationsProvider>
      <WorkbenchWindowProvider workspaceId={workspace.id}>
        <WorkspaceShellLayout workspace={workspace} />
      </WorkbenchWindowProvider>
    </NotificationsProvider>
  );
}

function WorkspaceShellLayout({ workspace }: WorkspaceShellProps) {
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const { session: workbenchSession, windowState } = useWorkbenchWindow();
  const safeMode = useSafeModeStatus();
  const safeModeEnabled = safeMode.data?.enabled ?? false;
  const safeModeDetail = safeMode.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;
  const shortcutHint = useShortcutHint();
  const workspaceNavItems = useMemo(
    () => getWorkspacePrimaryNavigation(workspace),
    [workspace],
  );
  const [workspaceSearchQuery, setWorkspaceSearchQuery] = useState("");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const workspaceSearchNormalized = workspaceSearchQuery.trim().toLowerCase();
  const immersiveWorkbenchActive = Boolean(workbenchSession && windowState === "maximized");
  const workspaceSearchSuggestions = useMemo(
    () =>
      workspaceNavItems.map((item) => ({
        id: item.id,
        label: item.label,
        description: `Jump to ${item.label}`,
        icon: <item.icon className="h-4 w-4 text-slate-400" aria-hidden />,
      })),
    [workspaceNavItems],
  );

  const navStorage = useMemo(
    () => createScopedStorage(`ade.ui.workspace.${workspace.id}.navCollapsed`),
    [workspace.id],
  );
  const [isNavCollapsed, setIsNavCollapsed] = useState(() => {
    const stored = navStorage.get<boolean>();
    return typeof stored === "boolean" ? stored : false;
  });

  useEffect(() => {
    const stored = navStorage.get<boolean>();
    setIsNavCollapsed(typeof stored === "boolean" ? stored : false);
  }, [navStorage]);

  useEffect(() => {
    navStorage.set(isNavCollapsed);
  }, [isNavCollapsed, navStorage]);

  useEffect(() => {
    setWorkspaceSearchQuery("");
  }, [workspace.id]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setIsMobileNavOpen(false);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    const originalOverflow = document.body.style.overflow;
    if (isMobileNavOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = originalOverflow || "";
    }
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isMobileNavOpen]);

  useEffect(() => {
    if (immersiveWorkbenchActive) {
      setIsMobileNavOpen(false);
    }
  }, [immersiveWorkbenchActive]);

  const handleWorkspaceSearchSubmit = useCallback(() => {
    if (!workspaceSearchNormalized) {
      return;
    }
    const match =
      workspaceNavItems.find((item) => item.label.toLowerCase().includes(workspaceSearchNormalized)) ??
      workspaceNavItems.find((item) => item.id.toLowerCase().includes(workspaceSearchNormalized));
    if (match) {
      navigate(match.href);
    }
  }, [workspaceSearchNormalized, workspaceNavItems, navigate]);
  const handleWorkspaceSuggestionSelect = useCallback(
    (suggestion: GlobalSearchSuggestion) => {
      const match = workspaceNavItems.find((item) => item.id === suggestion.id);
      if (match) {
        navigate(match.href);
        setWorkspaceSearchQuery("");
      }
    },
    [workspaceNavItems, navigate],
  );

  const openMobileNav = useCallback(() => setIsMobileNavOpen(true), []);
  const closeMobileNav = useCallback(() => setIsMobileNavOpen(false), []);

  const topBarBrand = (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={openMobileNav}
        className="focus-ring inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-600 shadow-sm lg:hidden"
        aria-label="Open workspace navigation"
      >
        <MenuIcon />
      </button>
    </div>
  );

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const topBarTrailing = (
    <div className="flex items-center gap-2">
      <ProfileDropdown displayName={displayName} email={email} />
    </div>
  );
  const workspaceSearch = {
    value: workspaceSearchQuery,
    onChange: setWorkspaceSearchQuery,
    onSubmit: handleWorkspaceSearchSubmit,
    placeholder: `Search ${workspace.name} or jump to a section`,
    shortcutHint,
    scopeLabel: workspace.name,
    suggestions: workspaceSearchSuggestions,
    onSelectSuggestion: handleWorkspaceSuggestionSelect,
  };

  const segments = extractSectionSegments(location.pathname, workspace.id);
  const section = resolveWorkspaceSection(workspace.id, segments, location.search, location.hash);
  const isDocumentsSection = section?.kind === "content" && section.key.startsWith("documents");
  const documentSearchValue = isDocumentsSection ? new URLSearchParams(location.search).get("q") ?? "" : "";
  const handleDocumentSearchChange = useCallback(
    (nextValue: string) => {
      if (!isDocumentsSection) {
        return;
      }
      const params = new URLSearchParams(location.search);
      if (nextValue) {
        params.set("q", nextValue);
      } else {
        params.delete("q");
      }
      const searchParams = params.toString();
      navigate(
        `${location.pathname}${searchParams ? `?${searchParams}` : ""}${location.hash}`,
        { replace: true },
      );
    },
    [isDocumentsSection, location.hash, location.pathname, location.search, navigate],
  );
  const handleDocumentSearchSubmit = useCallback(
    (value: string) => {
      handleDocumentSearchChange(value);
    },
    [handleDocumentSearchChange],
  );
  const handleDocumentSearchClear = useCallback(() => {
    handleDocumentSearchChange("");
  }, [handleDocumentSearchChange]);
  const documentsSearch = isDocumentsSection
    ? {
        value: documentSearchValue,
        onChange: handleDocumentSearchChange,
        onSubmit: handleDocumentSearchSubmit,
        onClear: handleDocumentSearchClear,
        placeholder: "Search documents",
        shortcutHint,
        scopeLabel: "Documents",
        enableShortcut: true,
      }
    : undefined;
  const topBarSearch = documentsSearch ?? workspaceSearch;

  useEffect(() => {
    if (section?.kind === "redirect") {
      navigate(section.to, { replace: true });
    }
  }, [section, navigate]);

  if (!section || section.kind === "redirect") {
    return null;
  }

  const fullHeightLayout = section.fullHeight ?? false;

  return (
    <div
      className={clsx(
        "flex min-w-0 bg-slate-50 text-slate-900",
        fullHeightLayout ? "h-screen overflow-hidden" : "min-h-screen",
      )}
    >
      {!immersiveWorkbenchActive ? (
        <WorkspaceNav
          workspace={workspace}
          items={workspaceNavItems}
          collapsed={isNavCollapsed}
          onToggleCollapse={() => setIsNavCollapsed((current) => !current)}
          onGoToWorkspaces={() => navigate("/workspaces")}
        />
      ) : null}
      <div className="flex flex-1 min-w-0 flex-col">
        {!immersiveWorkbenchActive ? (
          <GlobalTopBar brand={topBarBrand} trailing={topBarTrailing} search={topBarSearch} />
        ) : null}
        {!immersiveWorkbenchActive && isMobileNavOpen ? (
          <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
            <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={closeMobileNav} />
            <div className="absolute inset-y-0 left-0 flex h-full w-[min(20rem,85vw)] max-w-xs flex-col rounded-r-3xl border-r border-slate-100/70 bg-gradient-to-b from-white via-slate-50 to-white/95 shadow-[0_45px_90px_-50px_rgba(15,23,42,0.85)]">
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                <div className="flex flex-col leading-tight">
                  <span className="text-sm font-semibold text-slate-900">{workspace.name}</span>
                  <span className="text-xs text-slate-400">Workspace navigation</span>
                </div>
                <button
                  type="button"
                  onClick={closeMobileNav}
                  className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-500"
                  aria-label="Close navigation"
                >
                  <CloseIcon />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-3 py-4">
                <WorkspaceNavList items={workspaceNavItems} onNavigate={closeMobileNav} showHeading={false} />
              </div>
            </div>
          </div>
        ) : null}
        <div className="relative flex flex-1 min-w-0 overflow-hidden" key={`section-${section.key}`}>
          <main
            className={clsx(
              "relative flex-1 min-w-0",
              fullHeightLayout ? "flex min-h-0 flex-col overflow-hidden" : "overflow-y-auto",
            )}
          >
            <div
              className={clsx(
                fullHeightLayout
                  ? "flex w-full flex-1 min-h-0 flex-col px-0 py-0"
                  : "mx-auto flex w-full max-w-7xl flex-col px-4 py-6",
              )}
            >
              {safeModeEnabled ? (
                <div className={clsx("mb-4", fullHeightLayout ? "px-6 pt-4" : "")}>
                  <Alert tone="warning" heading="Safe mode active">
                    {safeModeDetail}
                  </Alert>
                </div>
              ) : null}
              <div className={clsx(fullHeightLayout ? "flex min-h-0 min-w-0 flex-1 flex-col" : "flex min-w-0 flex-1 flex-col")}>
                {section.element}
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

function extractWorkspaceIdentifier(pathname: string) {
  const match = pathname.match(/^\/workspaces\/([^/]+)/);
  return match?.[1] ?? null;
}

function extractSectionSegments(pathname: string, workspaceId: string) {
  const base = `/workspaces/${workspaceId}`;
  if (!pathname.startsWith(base)) {
    return [];
  }
  const remainder = pathname.slice(base.length);
  return remainder
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0);
}

function findWorkspace(workspaces: WorkspaceProfile[], identifier: string | null) {
  if (!identifier) {
    return workspaces[0] ?? null;
  }
  return (
    workspaces.find((workspace) => workspace.id === identifier) ??
    workspaces.find((workspace) => workspace.slug === identifier) ??
    workspaces[0] ??
    null
  );
}

function buildCanonicalPath(pathname: string, search: string, resolvedId: string, currentId: string) {
  const base = `/workspaces/${currentId}`;
  const trailing = pathname.startsWith(base) ? pathname.slice(base.length) : "";
  const normalized = trailing && trailing !== "/" ? trailing : `/${defaultWorkspaceSection.path}`;
  return `/workspaces/${resolvedId}${normalized}${search}`;
}

function MenuIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M4 6h12" strokeLinecap="round" />
      <path d="M4 10h12" strokeLinecap="round" />
      <path d="M4 14h8" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M6 6l8 8" strokeLinecap="round" />
      <path d="M14 6l-8 8" strokeLinecap="round" />
    </svg>
  );
}

export function resolveWorkspaceSection(
  workspaceId: string,
  segments: string[],
  search: string,
  hash: string,
): WorkspaceSectionRender | null {
  const suffix = `${search}${hash}`;

  if (segments.length === 0) {
    return {
      kind: "redirect",
      to: `/workspaces/${workspaceId}/${defaultWorkspaceSection.path}${suffix}`,
    };
  }

  const [first, second, third] = segments;
  switch (first) {
    case "overview":
      return { kind: "content", key: "overview", element: <WorkspaceOverviewRoute /> };
    case defaultWorkspaceSection.path:
    case "documents": {
      if (!second) {
        return { kind: "content", key: "documents", element: <WorkspaceDocumentsRoute /> };
      }
      return {
        kind: "content",
        key: `documents:${second}`,
        element: <DocumentDetailRoute params={{ documentId: decodeURIComponent(second) }} />,
      };
    }
    case "runs":
      return { kind: "content", key: "runs", element: <WorkspaceRunsRoute /> };
    case "config-builder": {
      if (!second) {
        return { kind: "content", key: "config-builder", element: <WorkspaceConfigsIndexRoute /> };
      }
      if (third === "editor") {
        return {
          kind: "content",
          key: `config-builder:${second}:editor`,
          element: <ConfigEditorWorkbenchRouteWithParams configId={decodeURIComponent(second)} />,
          fullHeight: true,
        };
      }
      return {
        kind: "content",
        key: `config-builder:${second}`,
        element: <WorkspaceConfigRoute params={{ configId: decodeURIComponent(second) }} />,
      };
    }
    case "configs": {
      const legacyTarget = `/workspaces/${workspaceId}/config-builder${second ? `/${second}` : ""}${third ? `/${third}` : ""}`;
      return {
        kind: "redirect",
        to: `${legacyTarget}${suffix}`,
      };
    }
    case "settings":
      return { kind: "content", key: "settings", element: <WorkspaceSettingsRoute /> };
    default:
      return {
        kind: "content",
        key: `not-found:${segments.join("/")}`,
        element: (
          <PageState
            title="Section not found"
            description="The requested workspace section could not be located."
            variant="error"
          />
        ),
      };
  }
}
function ConfigEditorWorkbenchRouteWithParams({ configId }: { readonly configId: string }) {
  return <ConfigEditorWorkbenchRoute params={{ configId }} />;
}

export function getDefaultWorkspacePath(workspaceId: string) {
  return `/workspaces/${workspaceId}/${defaultWorkspaceSection.path}`;
}
```

# apps/ade-web/src/screens/Workspaces/New/hooks/useCreateWorkspaceMutation.ts
```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createWorkspace,
  workspacesKeys,
  type WorkspaceCreatePayload,
  type WorkspaceListPage,
  type WorkspaceProfile,
} from "@features/Workspace/api/workspaces-api";

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation<WorkspaceProfile, Error, WorkspaceCreatePayload>({
    mutationFn: createWorkspace,
    onSuccess(workspace) {
      queryClient.setQueryData(workspacesKeys.detail(workspace.id), workspace);

      queryClient
        .getQueriesData<WorkspaceListPage>({ queryKey: workspacesKeys.all() })
        .forEach(([key, page]) => {
          if (!Array.isArray(key) || key[0] !== "workspaces" || key[1] !== "list" || !page) {
            return;
          }

          const existingIndex = page.items.findIndex((item) => item.id === workspace.id);
          const mergedItems =
            existingIndex >= 0
              ? page.items.map((item) => (item.id === workspace.id ? workspace : item))
              : [...page.items, workspace];

          const sortedItems = [...mergedItems].sort((a, b) => a.name.localeCompare(b.name));
          const total = typeof page.total === "number" && existingIndex === -1 ? page.total + 1 : page.total;

          queryClient.setQueryData(key, { ...page, items: sortedItems, total });
        });

      queryClient.invalidateQueries({ queryKey: workspacesKeys.all() });
    },
  });
}
```

# apps/ade-web/src/screens/Workspaces/New/index.tsx
```tsx
import { useEffect, useMemo } from "react";

import { useNavigate } from "@app/nav/history";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { ApiError } from "@shared/api";
import type { UserSummary } from "@shared/users/api";
import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useCreateWorkspaceMutation } from "./hooks/useCreateWorkspaceMutation";
import { useWorkspacesQuery, type WorkspaceProfile } from "@features/Workspace/api/workspaces-api";
import { useUsersQuery } from "@shared/users/hooks/useUsersQuery";
import { WorkspaceDirectoryLayout } from "@features/Workspaces/components/WorkspaceDirectoryLayout";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";

const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const workspaceSchema = z.object({
  name: z.string().min(1, "Workspace name is required.").max(100, "Keep the name under 100 characters."),
  slug: z
    .string()
    .min(1, "Workspace slug is required.")
    .max(100, "Keep the slug under 100 characters.")
    .regex(slugPattern, "Use lowercase letters, numbers, and dashes."),
  ownerUserId: z.string().optional(),
});

type WorkspaceFormValues = z.infer<typeof workspaceSchema>;

export default function WorkspaceCreateRoute() {
  return (
    <RequireSession>
      <WorkspaceCreateContent />
    </RequireSession>
  );
}

function WorkspaceCreateContent() {
  const navigate = useNavigate();
  const session = useSession();
  const workspacesQuery = useWorkspacesQuery();
  const createWorkspace = useCreateWorkspaceMutation();

  const canSelectOwner = session.user.permissions?.includes("Users.Read.All") ?? false;
  const usersQuery = useUsersQuery({ enabled: canSelectOwner, pageSize: 50 });
  const ownerOptions = useMemo<UserSummary[]>(() => usersQuery.users, [usersQuery.users]);
  const filteredOwnerOptions = useMemo(() => {
    if (!session.user.id) {
      return ownerOptions;
    }
    return ownerOptions.filter((user) => user.id !== session.user.id);
  }, [ownerOptions, session.user.id]);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    setError,
    clearErrors,
    formState: { errors, dirtyFields },
  } = useForm<WorkspaceFormValues>({
    resolver: zodResolver(workspaceSchema),
    defaultValues: {
      name: "",
      slug: "",
      ownerUserId: session.user.id ?? "",
    },
  });

  const nameValue = watch("name");
  const slugValue = watch("slug");

  useEffect(() => {
    if (dirtyFields.slug) {
      return;
    }
    const generated = slugify(nameValue);
    if (generated !== slugValue) {
      setValue("slug", generated, { shouldValidate: Boolean(generated) });
    }
  }, [dirtyFields.slug, nameValue, setValue, slugValue]);

  useEffect(() => {
    if (!canSelectOwner && session.user.id) {
      setValue("ownerUserId", session.user.id, { shouldDirty: false });
    }
  }, [canSelectOwner, session.user.id, setValue]);

  const isSubmitting = createWorkspace.isPending;
  const usersLoading = usersQuery.isPending && usersQuery.users.length === 0;
  const ownerSelectDisabled = isSubmitting || usersLoading || !canSelectOwner;
  const currentUserLabel = session.user.display_name
    ? `${session.user.display_name} (you)`
    : `${session.user.email ?? "Current user"} (you)`;
  const ownerField = register("ownerUserId");

  const onSubmit = handleSubmit((values) => {
    clearErrors("root");

    if (canSelectOwner && !values.ownerUserId) {
      setError("ownerUserId", { type: "manual", message: "Select a workspace owner." });
      return;
    }

    createWorkspace.mutate(
      {
        name: values.name.trim(),
        slug: values.slug.trim(),
        owner_user_id: canSelectOwner ? values.ownerUserId || undefined : undefined,
      },
      {
        onSuccess(workspace: WorkspaceProfile) {
          workspacesQuery.refetch();
          navigate(`/workspaces/${workspace.id}`);
        },
        onError(error: unknown) {
          if (error instanceof ApiError) {
            const detail = error.problem?.detail ?? error.message;
            const fieldErrors = error.problem?.errors ?? {};
            setError("root", { type: "server", message: detail });
            if (fieldErrors.name?.[0]) {
              setError("name", { type: "server", message: fieldErrors.name[0] });
            }
            if (fieldErrors.slug?.[0]) {
              setError("slug", { type: "server", message: fieldErrors.slug[0] });
            }
            if (fieldErrors.owner_user_id?.[0]) {
              setError("ownerUserId", { type: "server", message: fieldErrors.owner_user_id[0] });
            }
            return;
          }
          setError("root", {
            type: "server",
            message: error instanceof Error ? error.message : "Workspace creation failed.",
          });
        },
      },
    );
  });

  return (
    <WorkspaceDirectoryLayout>
      <div className="space-y-6">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold text-slate-900">Create a workspace</h1>
          <p className="text-sm text-slate-600">
            Name the workspace and choose who should own it. You can adjust settings and permissions after the workspace
            is created.
          </p>
        </header>

        <form className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft" onSubmit={onSubmit}>
          <div className="grid gap-5 md:grid-cols-2">
            <FormField label="Workspace name" required error={errors.name?.message}>
              <Input
                id="workspaceName"
                placeholder="Finance Operations"
                {...register("name")}
                invalid={Boolean(errors.name)}
                disabled={isSubmitting}
              />
            </FormField>

            <FormField
              label="Workspace slug"
              hint="Lowercase, URL-friendly identifier"
              required
              error={errors.slug?.message}
            >
              <Input
                id="workspaceSlug"
                placeholder="finance-ops"
                {...register("slug")}
                invalid={Boolean(errors.slug)}
                disabled={isSubmitting}
              />
            </FormField>
          </div>

          {canSelectOwner ? (
            <FormField
              label="Workspace owner"
              hint="Owner receives workspace-level permissions immediately."
              error={errors.ownerUserId?.message}
            >
              <select
                id="workspaceOwner"
                {...ownerField}
                onChange={(event) => {
                  ownerField.onChange(event);
                  clearErrors("ownerUserId");
                }}
                disabled={ownerSelectDisabled}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
              >
                <option value={session.user.id ?? ""}>{currentUserLabel}</option>
                {filteredOwnerOptions.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.display_name ? `${user.display_name} (${user.email})` : user.email}
                  </option>
                ))}
              </select>
              {usersQuery.hasNextPage ? (
                <div className="pt-2">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => usersQuery.fetchNextPage()}
                    disabled={usersQuery.isFetchingNextPage}
                  >
                    {usersQuery.isFetchingNextPage ? "Loading more users…" : "Load more users"}
                  </Button>
                </div>
              ) : null}
            </FormField>
          ) : null}

          {errors.root ? <Alert tone="danger">{errors.root.message}</Alert> : null}
          {canSelectOwner && usersQuery.isError ? (
            <Alert tone="warning">
              Unable to load the user list. Continue with yourself as the workspace owner or try again later.
            </Alert>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button type="button" variant="secondary" onClick={() => navigate(-1)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSubmitting}>
              {isSubmitting ? "Creating workspace…" : "Create workspace"}
            </Button>
          </div>
        </form>
      </div>
    </WorkspaceDirectoryLayout>
  );
}


function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}
```

# apps/ade-web/src/screens/Workspaces/components/WorkspaceDirectoryLayout.tsx
```tsx
import { type ReactNode } from "react";
import { useNavigate } from "@app/nav/history";

import { useSession } from "@shared/auth/context/SessionContext";
import { GlobalTopBar, type GlobalTopBarSearchProps } from "@app/shell/GlobalTopBar";
import { ProfileDropdown } from "@app/shell/ProfileDropdown";
import { DirectoryIcon } from "@features/Workspace/components/workspace-navigation";

interface WorkspaceDirectoryLayoutProps {
  readonly children: ReactNode;
  readonly sidePanel?: ReactNode;
  readonly actions?: ReactNode;
  readonly search?: GlobalTopBarSearchProps;
}

export function WorkspaceDirectoryLayout({ children, sidePanel, actions, search }: WorkspaceDirectoryLayoutProps) {
  const session = useSession();
  const navigate = useNavigate();
  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <GlobalTopBar
        brand={
          <button
            type="button"
            onClick={() => navigate("/workspaces")}
            className="focus-ring inline-flex items-center gap-3 rounded-xl border border-transparent bg-white px-3 py-2 text-left text-sm font-semibold text-slate-900 shadow-sm transition hover:border-slate-200"
          >
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-white shadow-sm">
              <DirectoryIcon className="h-5 w-5" aria-hidden />
            </span>
            <span className="flex flex-col leading-tight">
              <span className="text-sm font-semibold text-slate-900">Workspace directory</span>
              <span className="text-xs text-slate-400">Automatic Data Extractor</span>
            </span>
          </button>
        }
        search={search}
        actions={actions ? <div className="flex items-center gap-2">{actions}</div> : undefined}
        trailing={
          <div className="flex items-center gap-2">
            <ProfileDropdown displayName={displayName} email={email} />
          </div>
        }
      />
      <main className="flex flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-6xl px-4 py-8">
          <div className={`grid gap-6 ${sidePanel ? "lg:grid-cols-[minmax(0,1fr)_280px]" : ""}`}>
            <div>{children}</div>
            {sidePanel ? <aside className="space-y-6">{sidePanel}</aside> : null}
          </div>
        </div>
      </main>
    </div>
  );
}
```

# apps/ade-web/src/screens/Workspaces/index.tsx
```tsx
import { useCallback, useMemo, useState } from "react";

import { Link } from "@app/nav/Link";
import { useNavigate } from "@app/nav/history";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useWorkspacesQuery, type WorkspaceProfile } from "@features/Workspace/api/workspaces-api";
import { Button } from "@ui/Button";
import { PageState } from "@ui/PageState";
import { defaultWorkspaceSection } from "@features/Workspace/components/workspace-navigation";
import { WorkspaceDirectoryLayout } from "@features/Workspaces/components/WorkspaceDirectoryLayout";
import { useShortcutHint } from "@shared/hooks/useShortcutHint";
import type { GlobalSearchSuggestion } from "@app/shell/GlobalTopBar";
import { GlobalSearchField } from "@app/shell/GlobalSearchField";

export default function WorkspacesIndexRoute() {
  return (
    <RequireSession>
      <WorkspacesIndexContent />
    </RequireSession>
  );
}

function WorkspacesIndexContent() {
  const navigate = useNavigate();
  const session = useSession();
  const workspacesQuery = useWorkspacesQuery();
  const userPermissions = session.user.permissions ?? [];
  const canCreateWorkspace = userPermissions.includes("Workspaces.Create");
  const [searchQuery, setSearchQuery] = useState("");
  const shortcutHint = useShortcutHint();
  const workspacesPage = workspacesQuery.data;
  const workspaces: WorkspaceProfile[] = useMemo(
    () => workspacesPage?.items ?? [],
    [workspacesPage?.items],
  );
  const normalizedSearch = searchQuery.trim().toLowerCase();
  const visibleWorkspaces = useMemo(() => {
    if (!normalizedSearch) {
      return workspaces;
    }
    return workspaces.filter((workspace) => {
      const name = workspace.name.toLowerCase();
      const slug = workspace.slug?.toLowerCase() ?? "";
      return name.includes(normalizedSearch) || slug.includes(normalizedSearch);
    });
  }, [workspaces, normalizedSearch]);

  const actions = canCreateWorkspace ? (
    <Button variant="primary" onClick={() => navigate("/workspaces/new")}>
      Create workspace
    </Button>
  ) : undefined;

  const handleWorkspaceSearchSubmit = useCallback(() => {
    if (!normalizedSearch) {
      return;
    }
    const firstMatch = visibleWorkspaces[0];
    if (firstMatch) {
      navigate(`/workspaces/${firstMatch.id}/${defaultWorkspaceSection.path}`);
    }
  }, [visibleWorkspaces, normalizedSearch, navigate]);

  const handleResetSearch = useCallback(() => setSearchQuery(""), []);

  const suggestionSeed = (normalizedSearch ? visibleWorkspaces : workspaces).slice(0, 5);
  const searchSuggestions = suggestionSeed.map((workspace) => ({
    id: workspace.id,
    label: workspace.name,
    description: workspace.slug ? `Slug • ${workspace.slug}` : "Workspace",
  }));

  const handleWorkspaceSuggestionSelect = useCallback(
    (suggestion: GlobalSearchSuggestion) => {
      setSearchQuery("");
      navigate(`/workspaces/${suggestion.id}/${defaultWorkspaceSection.path}`);
    },
    [navigate],
  );

  const directorySearch = {
    value: searchQuery,
    onChange: setSearchQuery,
    onSubmit: handleWorkspaceSearchSubmit,
    placeholder: "Search workspaces or jump to one instantly",
    shortcutHint,
    scopeLabel: "Workspace directory",
    suggestions: searchSuggestions,
    onSelectSuggestion: handleWorkspaceSuggestionSelect,
    onClear: handleResetSearch,
  };
  const inlineDirectorySearch = {
    ...directorySearch,
    shortcutHint: undefined,
    onClear: handleResetSearch,
    enableShortcut: false,
    variant: "minimal" as const,
  };

  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState title="Loading workspaces" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState
          title="We couldn't load your workspaces"
          description="Refresh the page or try again later."
          variant="error"
          action={
            <Button variant="secondary" onClick={() => workspacesQuery.refetch()}>
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  const mainContent =
    workspaces.length === 0 ? (
      canCreateWorkspace ? (
        <EmptyStateCreate onCreate={() => navigate("/workspaces/new")} />
      ) : (
        <div className="space-y-4">
          <h1 id="page-title" className="sr-only">
            Workspaces
          </h1>
          <PageState
            title="No workspaces available"
            description="You don't have access to any workspaces yet. Ask an administrator to add you or create one on your behalf."
            variant="empty"
          />
        </div>
      )
    ) : visibleWorkspaces.length === 0 ? (
      <div className="space-y-4">
        <PageState
          title={`No workspaces matching "${searchQuery}"`}
          description="Try searching by another workspace name or slug."
          action={
            <Button variant="secondary" onClick={handleResetSearch}>
              Clear search
            </Button>
          }
        />
      </div>
    ) : (
      <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <header>
          <h1 id="page-title" className="text-2xl font-semibold text-slate-900">
            Workspaces
          </h1>
          <p className="mt-1 text-sm text-slate-500">Select a workspace to jump straight into documents.</p>
        </header>
        <GlobalSearchField {...inlineDirectorySearch} className="w-full" />
        <section className="grid gap-5 lg:grid-cols-2">
          {visibleWorkspaces.map((workspace) => (
            <Link
              key={workspace.id}
              to={`/workspaces/${workspace.id}/${defaultWorkspaceSection.path}`}
              className="group rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900">{workspace.name}</h2>
                {workspace.is_default ? (
                  <span className="rounded-full bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-600">Default</span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-slate-500">Slug: {workspace.slug}</p>
              <p className="mt-4 text-xs font-medium uppercase tracking-wide text-slate-500">Permissions</p>
              <p className="text-sm text-slate-600">
                {workspace.permissions.length > 0 ? workspace.permissions.join(", ") : "None"}
              </p>
            </Link>
          ))}
        </section>
      </div>
    );

  return (
    <WorkspaceDirectoryLayout
      actions={actions}
      search={directorySearch}
      sidePanel={<DirectorySidebar canCreate={canCreateWorkspace} onCreate={() => navigate("/workspaces/new")} />}
    >
      {mainContent}
    </WorkspaceDirectoryLayout>
  );
}

function DirectorySidebar({ canCreate, onCreate }: { canCreate: boolean; onCreate: () => void }) {
  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
        <header className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Workspace tips</p>
          <h2 className="text-sm font-semibold text-slate-900">Why multiple workspaces?</h2>
        </header>
        <p className="text-xs text-slate-500 leading-relaxed">
          Segment teams by business unit or client, control access with roles, and tailor extraction settings per
          workspace. Everything stays organised and secure.
        </p>
        {canCreate ? (
          <Button variant="secondary" onClick={onCreate} className="w-full">
            New workspace
          </Button>
        ) : null}
      </section>
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
        <header className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Need a hand?</p>
          <h2 className="text-sm font-semibold text-slate-900">Workspace setup checklist</h2>
        </header>
        <ul className="space-y-2 text-xs text-slate-600">
          <li>Invite at least one additional administrator.</li>
          <li>Review configurations before uploading production files.</li>
          <li>Review workspace permissions for external collaborators.</li>
        </ul>
      </section>
    </div>
  );
}


function EmptyStateCreate({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="mx-auto max-w-3xl rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-soft">
      <h1 id="page-title" className="text-2xl font-semibold text-slate-900">No workspaces yet</h1>
      <p className="mt-2 text-sm text-slate-600">
        Create your first workspace to start uploading configuration sets and documents.
      </p>
      <Button variant="primary" onClick={onCreate} className="mt-6">
        Create workspace
      </Button>
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
