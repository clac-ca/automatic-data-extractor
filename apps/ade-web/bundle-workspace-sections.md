# Logical module layout (source -> sections below):
# - apps/ade-web/README.md
# - apps/ade-web/src/app/App.tsx
# - apps/ade-web/src/app/AppProviders.tsx
# - apps/ade-web/src/app/nav/Link.tsx
# - apps/ade-web/src/app/nav/history.tsx
# - apps/ade-web/src/app/nav/urlState.ts
# - apps/ade-web/src/main.tsx
# - apps/ade-web/src/screens/Workspace/sections/Documents/components/DocumentDetail.tsx
# - apps/ade-web/src/screens/Workspace/sections/Documents/index.tsx - route.tsx — Workspace Documents (polished, compact UI)
# - apps/ade-web/src/screens/Workspace/sections/Jobs/index.tsx
# - apps/ade-web/src/screens/Workspace/sections/Overview/index.tsx
# - apps/ade-web/src/screens/Workspace/sections/Settings/components/SafeModeControls.tsx
# - apps/ade-web/src/screens/Workspace/sections/Settings/components/WorkspaceMembersSection.tsx
# - apps/ade-web/src/screens/Workspace/sections/Settings/components/WorkspaceRolesSection.tsx
# - apps/ade-web/src/screens/Workspace/sections/Settings/index.tsx
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
    - Jobs
    - Config Builder
    - Settings
  - Collapse/expand state is persisted **per workspace** (so each workspace “remembers” whether you prefer a compact nav).

- **Top bar**:
  - Workspace name and optional environment label (e.g. “Production”, “Staging”).
  - Context‑aware **search**:
    - On the **Documents** section, it acts as a document‑scoped search.
    - Elsewhere, it can search within the workspace (sections, configs, jobs).
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

- Owns **documents**, **jobs/runs**, **config packages**, and **membership/roles**.
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
    - `processing` – currently being processed by a job.
    - `processed` – last job completed successfully.
    - `failed` – last job ended in error.
    - `archived` – kept for history, not actively used.
  - **Timestamps** (created/uploaded at).
  - **Uploader** (user who uploaded the file).
  - **Last run summary** (`last_run`):
    - Status (`succeeded`, `failed`, `running`, etc.),
    - A short message (if provided),
    - When it last ran.

Documents are treated as **immutable inputs**:

- Re‑uploading a revised file results in a **new document**.
- Jobs always refer to the original uploaded file by ID.

Multi‑sheet spreadsheets can expose **worksheet metadata**:

- ADE Web calls a document‑sheets endpoint to learn about sheets:
  - `name`, index, and whether a sheet is “active”.
- Run dialogs (including the Config Builder’s *Run extraction* flow) can then offer sheet‑level selection.

---

### Runs (jobs)

A **run** (or **job**) is a single execution of ADE against a set of inputs with a particular config version.

Key ideas:

- Jobs are **workspace‑scoped** and usually tied to at least one document.
- Each job includes:
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

The backend exposes **streaming NDJSON APIs** for job events:

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
- Running **jobs** and **test runs**.
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
- `/jobs` – Jobs ledger.
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

### Workbench return path (Settings ↔ Config Builder / Documents / Jobs)

To keep flows smooth between operational views and config editing, a helper key is used:

```ts
export function getWorkbenchReturnPathStorageKey(workspaceId: string) {
  return `ade.ui.workspace.${workspaceId}.workbench.returnPath`;
}
```

When entering the workbench from any workspace section:

* The app can store the originating URL (e.g. filtered Documents view, Jobs query, or Settings tab).

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

This arrangement allows:

* Frontend and backend running on separate ports during development.
* Avoiding CORS pain by proxying API calls through the dev server.

### Testing (Vitest)

`apps/ade-web/vitest.config.ts`:

* Module resolution aliases mirror Vite’s (`@app`, `@screens`, etc.).
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

* **Analysts** use it to upload documents, run extractions, inspect jobs, and download outputs.
* **Workspace owners / engineers** use it to evolve Python‑based config packages, validate and test changes, and safely roll out new versions.
* **Admins** use it to manage workspaces, members, roles, SSO hints, and safe mode.

This README captures:

* The **conceptual model** (workspaces, documents, jobs, configs, safe mode, roles),
* The **navigation and URL‑state conventions** (custom history, search params, deep linking),
* The **workbench model** for config packages (file tree, tabs, layout, editor theme, unsaved changes, build & run integration),
* And the **backend contracts** ADE Web expects.

As long as backend implementations respect these concepts and contracts, ADE Web can remain stable, even as internals and infrastructure evolve.
```

# apps/ade-web/src/app/App.tsx
```tsx
import { NavProvider, useLocation } from "@app/nav/history";

import { AppProviders } from "./AppProviders";
import HomeScreen from "@screens/Home";
import LoginScreen from "@screens/Login";
import AuthCallbackScreen from "@screens/AuthCallback";
import SetupScreen from "@screens/Setup";
import WorkspacesScreen from "@screens/Workspaces";
import WorkspaceCreateScreen from "@screens/Workspaces/New";
import WorkspaceScreen from "@screens/Workspace";
import LogoutScreen from "@screens/Logout";
import NotFoundScreen from "@screens/NotFound";

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

# apps/ade-web/src/screens/Workspace/sections/Documents/components/DocumentDetail.tsx
```tsx
export const handle = { workspaceSectionId: "documents" } as const;

interface DocumentRouteParams {
  readonly documentId?: string;
}

export default function DocumentDetailRoute({ params }: { readonly params: DocumentRouteParams }) {
  return (
    <section>
      <h1 className="text-lg font-semibold">Document {params.documentId}</h1>
      <p className="mt-2 text-sm text-slate-600">TODO: render document details or drawer.</p>
    </section>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/Documents/index.tsx
```tsx
// route.tsx — Workspace Documents (polished, compact UI)

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useId,
  type ChangeEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";

import { useSearchParams } from "@app/nav/urlState";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useSession } from "@shared/auth/context/SessionContext";
import {
  findActiveVersion,
  findLatestInactiveVersion,
  useConfigVersionsQuery,
  useConfigsQuery,
} from "@shared/configs";
import { client } from "@shared/api/client";
import { useFlattenedPages } from "@shared/api/pagination";
import { createScopedStorage } from "@shared/storage";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@shared/system";
import type { components } from "@schema";
import { fetchDocumentSheets, type DocumentSheet } from "@shared/documents";
import {
  fetchJob,
  fetchJobOutputs,
  fetchJobArtifact,
  fetchJobTelemetry,
  type JobOutputListing,
  type JobRecord,
  type JobStatus,
} from "@shared/jobs";
import { ArtifactSummary, TelemetrySummary } from "@shared/runs/RunInsights";

import { Alert } from "@ui/Alert";
import { Select } from "@ui/Select";
import { Button } from "@ui/Button";

/* -------------------------------- Types & constants ------------------------------- */

type DocumentStatus = components["schemas"]["DocumentStatus"];
type DocumentRecord = components["schemas"]["DocumentOut"];
type JobSubmissionPayload = components["schemas"]["JobSubmissionRequest"];
type DocumentListPage = components["schemas"]["DocumentPage"];

type ListDocumentsQuery = {
  status?: DocumentStatus[];
  q?: string;
  sort?: string;
  uploader?: string;
  page?: number;
  page_size?: number;
  include_total?: boolean;
};

type DocumentsView = "mine" | "team" | "attention" | "recent";

const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  processed: "Processed",
  failed: "Failed",
  archived: "Archived",
};

const SORT_OPTIONS = [
  "-created_at",
  "created_at",
  "-last_run_at",
  "last_run_at",
  "-byte_size",
  "byte_size",
  "name",
  "-name",
  "status",
  "-status",
  "source",
  "-source",
] as const;
type SortOption = (typeof SORT_OPTIONS)[number];

const DEFAULT_VIEW: DocumentsView = "mine";
const DOCUMENT_VIEW_PRESETS: Record<
  DocumentsView,
  {
    readonly label: string;
    readonly description: string;
    readonly presetStatuses?: readonly DocumentStatus[];
    readonly presetSort?: SortOption;
    readonly uploader?: "me" | null;
  }
> = {
  mine: {
    label: "My uploads",
    description: "Documents you uploaded",
    uploader: "me",
  },
  team: {
    label: "All documents",
    description: "Everything in this workspace",
  },
  attention: {
    label: "Needs attention",
    description: "Failed or processing files",
    presetStatuses: ["failed", "processing"],
  },
  recent: {
    label: "Recently run",
    description: "Latest run activity",
    presetSort: "-last_run_at",
  },
};

function parseView(value: string | null): DocumentsView {
  if (!value) return DEFAULT_VIEW;
  return (Object.keys(DOCUMENT_VIEW_PRESETS) as DocumentsView[]).includes(value as DocumentsView)
    ? (value as DocumentsView)
    : DEFAULT_VIEW;
}

function parseStatusParam(value: string | null): Set<DocumentStatus> {
  if (!value) return new Set();
  const tokens = value
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean) as DocumentStatus[];
  const valid = tokens.filter((token): token is DocumentStatus =>
    ["uploaded", "processing", "processed", "failed", "archived"].includes(token),
  );
  return new Set(valid);
}

function parseSort(value: string | null): SortOption {
  const allowed = new Set<string>(SORT_OPTIONS);
  return (allowed.has(value ?? "") ? (value as SortOption) : "-created_at") as SortOption;
}

const uploadedFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const documentsKeys = {
  all: () => ["documents"] as const,
  workspace: (workspaceId: string) => [...documentsKeys.all(), workspaceId] as const,
  list: (
    workspaceId: string,
    sort: string | null,
    uploader: string | null,
  ) => [...documentsKeys.workspace(workspaceId), "list", { sort, uploader }] as const,
};

const DOCUMENTS_PAGE_SIZE = 50;
/* -------------------------------- Route component -------------------------------- */

export default function WorkspaceDocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const session = useSession();

  // URL-synced state
  const [searchParams, setSearchParams] = useSearchParams();
  const setSearchParamsRef = useRef(setSearchParams);
  useEffect(() => {
    setSearchParamsRef.current = setSearchParams;
  }, [setSearchParams]);
  const initialViewFromParams = parseView(searchParams.get("view"));
  const [viewFilter, setViewFilter] = useState<DocumentsView>(initialViewFromParams);
  const [statusFilters, setStatusFilters] = useState<Set<DocumentStatus>>(() => {
    const statusParam = searchParams.get("status");
    if (statusParam) return parseStatusParam(statusParam);
    const preset = DOCUMENT_VIEW_PRESETS[initialViewFromParams].presetStatuses ?? [];
    return new Set(preset);
  });
  const [sortOrder, setSortOrder] = useState<SortOption>(() => {
    const sortParam = searchParams.get("sort");
    if (sortParam) return parseSort(sortParam);
    const presetSort = DOCUMENT_VIEW_PRESETS[initialViewFromParams].presetSort;
    return presetSort ?? "-created_at";
  });
  const [searchTerm, setSearchTerm] = useState(searchParams.get("q") ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(searchTerm.trim());
  const statusFiltersArray = useMemo(() => Array.from(statusFilters), [statusFilters]);
  const viewPreset = DOCUMENT_VIEW_PRESETS[viewFilter];
  const uploaderFilter = viewPreset.uploader ?? null;

  // File input + selection
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const selectedIdsSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const selectedIdsArray = useMemo(() => Array.from(selectedIdsSet), [selectedIdsSet]);
  const selectedCount = selectedIdsSet.size;

  // Operations
  const uploadDocuments = useUploadWorkspaceDocuments(workspace.id);
  const deleteDocuments = useDeleteWorkspaceDocuments(workspace.id);
  const safeModeStatus = useSafeModeStatus();
  const safeModeEnabled = safeModeStatus.data?.enabled ?? false;
  const safeModeDetail = safeModeStatus.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;
  const safeModeLoading = safeModeStatus.isPending;

  const [banner, setBanner] = useState<{ tone: "error"; message: string } | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [runDrawerDocument, setRunDrawerDocument] = useState<DocumentRecord | null>(null);

  const isUploading = uploadDocuments.isPending;
  const isDeleting = deleteDocuments.isPending;

  // Query
  const documentsQuery = useWorkspaceDocuments(workspace.id, {
    statuses: statusFiltersArray,
    search: debouncedSearch,
    sort: sortOrder,
    uploader: uploaderFilter,
  });
  const { refetch: refetchDocuments } = documentsQuery;
  const getDocumentKey = useCallback((document: DocumentRecord) => document.id, []);
  const documentsRaw = useFlattenedPages(documentsQuery.data?.pages, getDocumentKey);
  const documents = useMemo(() => {
    const normalizedSearch = debouncedSearch.toLowerCase();
    const uploaderId = uploaderFilter === "me" ? session.user.id : null;
    const uploaderEmail = uploaderFilter === "me" ? session.user.email ?? null : null;
    return documentsRaw.filter((doc) => {
      if (statusFiltersArray.length > 0 && !statusFiltersArray.includes(doc.status)) {
        return false;
      }
      if (uploaderFilter === "me") {
        const docUploaderId = (doc as { uploader_id?: string | null }).uploader_id ?? doc.uploader?.id ?? null;
        const docUploaderEmail = doc.uploader?.email ?? null;
        if (uploaderId && docUploaderId && docUploaderId !== uploaderId) {
          return false;
        }
        if (!docUploaderId && uploaderEmail && docUploaderEmail && docUploaderEmail !== uploaderEmail) {
          return false;
        }
      }
      if (normalizedSearch) {
        const haystack = `${doc.name ?? ""} ${(doc as { source?: string | null }).source ?? ""}`.toLowerCase();
        if (!haystack.includes(normalizedSearch)) {
          return false;
        }
      }
      return true;
    });
  }, [debouncedSearch, documentsRaw, session.user.email, session.user.id, statusFiltersArray, uploaderFilter]);
  const fetchingNextPage = documentsQuery.isFetchingNextPage;
  const backgroundFetch = documentsQuery.isFetching && !fetchingNextPage;
  const totalDocuments = documents.length;

  /* ----------------------------- URL sync ----------------------------- */
  useEffect(() => {
    const paramValue = searchParams.get("q") ?? "";
    setSearchTerm((current) => (current === paramValue ? current : paramValue));
    const normalized = paramValue.trim();
    setDebouncedSearch((current) => (current === normalized ? current : normalized));
  }, [searchParams]);

  useEffect(() => {
    const s = new URLSearchParams();
    if (statusFilters.size > 0) s.set("status", Array.from(statusFilters).join(","));
    if (sortOrder !== "-created_at") s.set("sort", sortOrder);
    if (debouncedSearch) s.set("q", debouncedSearch);
    if (viewFilter !== DEFAULT_VIEW) s.set("view", viewFilter);
    setSearchParamsRef.current(s, { replace: true });
  }, [statusFilters, sortOrder, debouncedSearch, viewFilter]);

  /* --------------------------- Search debounce --------------------------- */
  useEffect(() => {
    const h = window.setTimeout(() => setDebouncedSearch(searchTerm.trim()), 250);
    return () => window.clearTimeout(h);
  }, [searchTerm]);

  /* ------------------------- Selection integrity ------------------------- */
  useEffect(() => {
    setSelectedIds((current) => {
      if (current.size === 0) return current;
      const next = new Set<string>();
      const valid = new Set(documents.map((d) => d.id));
      let changed = false;
      for (const id of current) {
        if (valid.has(id)) next.add(id);
        else changed = true;
      }
      return changed ? next : current;
    });
  }, [documents]);

  const firstSelectedDocument = useMemo(() => {
    for (const d of documents) if (selectedIdsSet.has(d.id)) return d;
    return null;
  }, [documents, selectedIdsSet]);

  const handleSelectView = useCallback((nextView: DocumentsView) => {
    const preset = DOCUMENT_VIEW_PRESETS[nextView];
    setViewFilter(nextView);
    setStatusFilters(new Set(preset.presetStatuses ?? []));
    setSortOrder(preset.presetSort ?? "-created_at");
    setSearchTerm("");
    setDebouncedSearch("");
  }, []);

  const toggleStatusFilter = useCallback((status: DocumentStatus) => {
    setStatusFilters((current) => {
      const next = new Set(current);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  }, []);

  const clearStatusFilters = useCallback(() => {
    setStatusFilters(new Set());
  }, []);

  /* --------------------------- Keyboard shortcuts --------------------------- */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Upload
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "u") {
        e.preventDefault();
        fileInputRef.current?.click();
        return;
      }
      // Delete selection
      if ((e.key === "Delete" || e.key === "Backspace") && selectedCount > 0) {
        e.preventDefault();
        void handleDeleteSelected();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCount]);

  /* ------------------------------- Helpers ------------------------------- */

  const statusFormatter = useCallback(
    (status: DocumentStatus) => DOCUMENT_STATUS_LABELS[status] ?? status,
    [],
  );

  const renderJobStatus = useCallback((documentItem: DocumentRecord) => <DocumentJobStatus document={documentItem} />, []);

  const handleOpenFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleUploadFiles = useCallback(
    async (files: readonly File[]) => {
      if (!files.length) return;
      setBanner(null);
      try {
        await uploadDocuments.mutateAsync({ files });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to upload documents.";
        setBanner({ tone: "error", message });
      }
    },
    [uploadDocuments],
  );

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    await handleUploadFiles(files);
    event.target.value = "";
  };

  const handleToggleDocument = (documentId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(documentId)) next.delete(documentId);
      else next.add(documentId);
      return next;
    });
  };

  const handleToggleAll = () => {
    setSelectedIds((current) => {
      if (documents.length === 0) return new Set();
      const allIds = documents.map((doc) => doc.id);
      if (current.size === documents.length && allIds.every((id) => current.has(id))) return new Set();
      return new Set(allIds);
    });
  };

  const handleDeleteSelected = useCallback(async () => {
    const ids = selectedIdsArray;
    if (!ids.length) return;
    setBanner(null);
    try {
      await deleteDocuments.mutateAsync({ documentIds: ids });
      setSelectedIds(new Set());
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to delete documents.";
      setBanner({ tone: "error", message });
    }
  }, [deleteDocuments, selectedIdsArray]);

  const handleDeleteSingle = useCallback(
    async (document: DocumentRecord) => {
      setBanner(null);
      try {
        await deleteDocuments.mutateAsync({ documentIds: [document.id] });
        setSelectedIds((current) => {
          const next = new Set(current);
          next.delete(document.id);
          return next;
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to delete document.";
        setBanner({ tone: "error", message });
      }
    },
    [deleteDocuments],
  );

  const handleDownloadDocument = useCallback(
    async (document: DocumentRecord) => {
      try {
        setDownloadingId(document.id);
        const { blob, filename } = await downloadDocument(workspace.id, document.id);
        triggerBrowserDownload(blob, filename ?? document.name);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to download document.";
        setBanner({ tone: "error", message });
      } finally {
        setDownloadingId(null);
      }
    },
    [workspace.id],
  );

  const handleOpenRunDrawer = useCallback((document: DocumentRecord) => {
    setRunDrawerDocument(document);
  }, []);

  const handleRunSuccess = useCallback(() => {
    void refetchDocuments();
  }, [refetchDocuments]);

  const handleRunError = useCallback((message: string) => {
    setBanner({ tone: "error", message });
  }, []);

  const onResetFilters = () => {
    setViewFilter(DEFAULT_VIEW);
    setSearchTerm("");
    setDebouncedSearch("");
    setStatusFilters(new Set());
    setSortOrder("-created_at");
  };

  const isDefaultFilters =
    viewFilter === DEFAULT_VIEW && statusFilters.size === 0 && sortOrder === "-created_at" && !debouncedSearch;

  /* -------------------------------- Render -------------------------------- */

  return (
    <>
      {/* Global drop-anywhere overlay */}
      <DropAnywhereOverlay
        workspaceName={workspace.name ?? undefined}
        disabled={isUploading}
        onFiles={async (files) => {
          await handleUploadFiles(files);
        }}
      />

      <div className="space-y-3">
        {/* Hidden file input (paired with Upload) */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.pdf,.tsv,.xls,.xlsx,.xlsm,.xlsb"
          multiple
          className="hidden"
          onChange={handleFileChange}
        />

        <DocumentsHeader
          workspaceName={workspace.name}
          totalDocuments={totalDocuments}
          view={viewFilter}
          onChangeView={handleSelectView}
          sort={sortOrder}
          onSort={setSortOrder}
          onReset={onResetFilters}
          isFetching={documentsQuery.isFetching}
          isDefault={isDefaultFilters}
          onUploadClick={handleOpenFilePicker}
          uploadDisabled={isUploading}
          selectedStatuses={statusFilters}
          onToggleStatus={toggleStatusFilter}
          onClearStatuses={clearStatusFilters}
        />

        {banner ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
            {banner.message}
          </div>
        ) : null}

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white text-sm text-slate-700">
          {documentsQuery.isLoading ? (
            <div className="p-4">
              <SkeletonList />
            </div>
          ) : documentsQuery.isError ? (
            <p className="p-4 text-rose-600">Failed to load documents.</p>
          ) : documents.length === 0 ? (
            <div className="p-6">
              <EmptyState onUploadClick={handleOpenFilePicker} />
            </div>
          ) : (
            <>
              <div className="overflow-x-auto p-2 sm:p-3">
                <DocumentsTable
                  documents={documents}
                  selectedIds={selectedIdsSet}
                  onToggleDocument={handleToggleDocument}
                  onToggleAll={handleToggleAll}
                  disableSelection={backgroundFetch || isDeleting || uploadDocuments.isPending}
                  disableRowActions={deleteDocuments.isPending}
                  formatStatusLabel={statusFormatter}
                  onDeleteDocument={handleDeleteSingle}
                  onDownloadDocument={handleDownloadDocument}
                  onRunDocument={handleOpenRunDrawer}
                  downloadingId={downloadingId}
                  renderJobStatus={renderJobStatus}
                  safeModeEnabled={safeModeEnabled}
                  safeModeMessage={safeModeDetail}
                  safeModeLoading={safeModeLoading}
                />
              </div>
              {documentsQuery.hasNextPage ? (
                <div className="flex justify-center border-t border-slate-200 bg-slate-50/60 px-3 py-2">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => documentsQuery.fetchNextPage()}
                    disabled={fetchingNextPage}
                  >
                    {fetchingNextPage ? "Loading more documents…" : "Load more documents"}
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>

      {/* Bottom bulk action bar */}
      <BulkBar
        count={selectedCount}
        onClear={() => setSelectedIds(new Set())}
        onRun={() => {
          if (firstSelectedDocument && !safeModeEnabled && !safeModeLoading) {
            handleOpenRunDrawer(firstSelectedDocument);
          }
        }}
        onDelete={handleDeleteSelected}
        busy={isDeleting}
        safeModeEnabled={safeModeEnabled}
        safeModeMessage={safeModeDetail}
        safeModeLoading={safeModeLoading}
      />

      {/* Run drawer */}
      <RunExtractionDrawer
        open={Boolean(runDrawerDocument)}
        workspaceId={workspace.id}
        documentRecord={runDrawerDocument}
        onClose={() => setRunDrawerDocument(null)}
        onRunSuccess={handleRunSuccess}
        onRunError={handleRunError}
        safeModeEnabled={safeModeEnabled}
        safeModeMessage={safeModeDetail}
        safeModeLoading={safeModeLoading}
      />
    </>
  );
}
/* ------------------------------- Data hooks ------------------------------- */

interface WorkspaceDocumentsOptions {
  readonly statuses: readonly DocumentStatus[];
  readonly search: string;
  readonly sort: SortOption;
  readonly uploader?: string | null;
}

function useWorkspaceDocuments(workspaceId: string, options: WorkspaceDocumentsOptions) {
  const sort = options.sort.trim() || null;

  return useInfiniteQuery<DocumentListPage>({
    queryKey: documentsKeys.list(workspaceId, sort, options.uploader ?? null),
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          sort,
          page: typeof pageParam === "number" ? pageParam : 1,
          pageSize: DOCUMENTS_PAGE_SIZE,
        },
        signal,
      ),
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: workspaceId.length > 0,
    placeholderData: (previous) => previous,
    staleTime: 15_000,
  });
}

function useUploadWorkspaceDocuments(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { files: readonly File[] }>({
    mutationFn: async ({ files }) => {
      const uploads = Array.from(files);
      for (const file of uploads) {
        await client.POST("/api/v1/workspaces/{workspace_id}/documents", {
          params: { path: { workspace_id: workspaceId } },
          body: { file: "" },
          bodySerializer: () => {
            const formData = new FormData();
            formData.append("file", file);
            return formData;
          },
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
    },
  });
}

function useDeleteWorkspaceDocuments(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { documentIds: readonly string[] }>({
    mutationFn: async ({ documentIds }) => {
      await Promise.all(
        documentIds.map((documentId) =>
          client.DELETE("/api/v1/workspaces/{workspace_id}/documents/{document_id}", {
            params: { path: { workspace_id: workspaceId, document_id: documentId } },
          })
        )
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
    },
  });
}

function useSubmitJob(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<JobRecord, Error, JobSubmissionPayload>({
    mutationFn: async (payload) => {
      const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/jobs", {
        params: { path: { workspace_id: workspaceId } },
        body: payload,
      });
      if (!data) throw new Error("Expected job payload.");
      return data as JobRecord;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKeys.workspace(workspaceId) });
    },
  });
}

function useDocumentRunPreferences(workspaceId: string, documentId: string) {
  const storage = useMemo(
    () => createScopedStorage(`ade.workspace.${workspaceId}.document_runs`),
    [workspaceId],
  );

  const [preferences, setPreferencesState] = useState<DocumentRunPreferences>(() =>
    readRunPreferences(storage, documentId),
  );

  useEffect(() => {
    setPreferencesState(readRunPreferences(storage, documentId));
  }, [storage, documentId]);

  const setPreferences = useCallback(
    (next: DocumentRunPreferences) => {
      setPreferencesState(next);
      const all = storage.get<Record<string, DocumentRunPreferences>>() ?? {};
      storage.set({
        ...all,
        [documentId]: {
          configId: next.configId,
          configVersionId: next.configVersionId,
          sheetNames: next.sheetNames && next.sheetNames.length > 0 ? [...next.sheetNames] : null,
        },
      });
    },
    [storage, documentId],
  );

  return { preferences, setPreferences } as const;
}

type DocumentRunPreferences = {
  readonly configId: string | null;
  readonly configVersionId: string | null;
  readonly sheetNames: readonly string[] | null;
};
/* ------------------------ API helpers & small utilities ------------------------ */

async function fetchWorkspaceDocuments(
  workspaceId: string,
  options: {
    sort: string | null;
    page: number;
    pageSize: number;
  },
  signal?: AbortSignal,
): Promise<DocumentListPage> {
  const query: ListDocumentsQuery = {
    sort: options.sort ?? undefined,
    page: options.page > 0 ? options.page : 1,
    page_size: options.pageSize > 0 ? options.pageSize : DOCUMENTS_PAGE_SIZE,
    include_total: false,
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected document page payload.");
  }

  return data;
}

async function downloadDocument(workspaceId: string, documentId: string) {
  const { data, response } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/documents/{document_id}/download",
    {
      params: { path: { workspace_id: workspaceId, document_id: documentId } },
      parseAs: "blob",
    },
  );
  if (!data) throw new Error("Expected document download payload.");
  const filename = extractFilename(response.headers.get("content-disposition")) ?? `document-${documentId}`;
  return { blob: data, filename };
}

function extractFilename(header: string | null) {
  if (!header) return null;
  const filenameStarMatch = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStarMatch?.[1]) {
    try {
      return decodeURIComponent(filenameStarMatch[1]);
    } catch {
      return filenameStarMatch[1];
    }
  }
  const filenameMatch = header.match(/filename="?([^";]+)"?/i);
  return filenameMatch?.[1] ?? null;
}

function readRunPreferences(
  storage: ReturnType<typeof createScopedStorage>,
  documentId: string,
): DocumentRunPreferences {
  const all = storage.get<Record<string, DocumentRunPreferences>>();
  if (all && typeof all === "object" && documentId in all) {
    const entry = all[documentId];
    if (entry && typeof entry === "object") {
      const legacySheetNames: string[] = [];
      if ("sheetName" in entry) {
        const sheetNameValue = (entry as { sheetName?: string | null }).sheetName;
        if (typeof sheetNameValue === "string") {
          legacySheetNames.push(sheetNameValue);
        }
      }
      const providedSheetNames = Array.isArray((entry as { sheetNames?: unknown }).sheetNames)
        ? ((entry as { sheetNames?: unknown }).sheetNames as unknown[]).filter(
            (value): value is string => typeof value === "string" && value.length > 0,
          )
        : null;
      const mergedSheetNames = providedSheetNames ?? (legacySheetNames.length > 0 ? legacySheetNames : null);

      return {
        configId: entry.configId ?? null,
        configVersionId: entry.configVersionId ?? null,
        sheetNames: mergedSheetNames,
      };
    }
  }
  return { configId: null, configVersionId: null, sheetNames: null };
}
/* ---------------------- Command header + filter rail ---------------------- */

function DocumentsHeader({
  workspaceName,
  totalDocuments,
  view,
  onChangeView,
  sort,
  onSort,
  onReset,
  isFetching,
  isDefault,
  onUploadClick,
  uploadDisabled,
  selectedStatuses,
  onToggleStatus,
  onClearStatuses,
}: {
  workspaceName?: string | null;
  totalDocuments?: number | null;
  view: DocumentsView;
  onChangeView: (view: DocumentsView) => void;
  sort: SortOption;
  onSort: (v: SortOption) => void;
  onReset: () => void;
  isFetching?: boolean;
  isDefault: boolean;
  onUploadClick: () => void;
  uploadDisabled?: boolean;
  selectedStatuses: ReadonlySet<DocumentStatus>;
  onToggleStatus: (status: DocumentStatus) => void;
  onClearStatuses: () => void;
}) {
  const subtitle =
    typeof totalDocuments === "number"
      ? `${totalDocuments.toLocaleString()} files`
      : workspaceName
        ? `Uploads and runs for ${workspaceName}`
        : "Manage workspace uploads and runs";

  return (
    <section
      className="rounded-xl border border-slate-200 bg-white/95 p-3 sm:p-4"
      role="region"
      aria-label="Documents header and filters"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold text-slate-900 sm:text-xl">
            {workspaceName ? `${workspaceName} documents` : "Documents"}
          </h1>
          <p className="text-xs text-slate-500">{subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onReset}
            disabled={isDefault}
            className={clsx(
              "rounded border border-transparent px-3 py-1 text-sm font-medium",
              isDefault
                ? "cursor-default text-slate-300"
                : "text-slate-600 hover:border-slate-200 hover:bg-slate-50 hover:text-slate-900",
            )}
          >
            Reset
          </button>
          <Button
            className="shrink-0"
            onClick={onUploadClick}
            disabled={uploadDisabled}
            isLoading={uploadDisabled}
            aria-label="Upload documents"
          >
            Upload
          </Button>
      </div>
    </div>

    <div className="mt-3 flex flex-wrap items-center gap-2">
      <DocumentsViewTabs view={view} onChange={onChangeView} />
        <StatusFilterControl
          selectedStatuses={selectedStatuses}
          onToggleStatus={onToggleStatus}
          onClearStatuses={onClearStatuses}
        />
        <Select
          value={sort}
          onChange={(e) => onSort(e.target.value as SortOption)}
          className="w-40"
          aria-label="Sort documents"
        >
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="-last_run_at">Recent runs</option>
          <option value="last_run_at">Least recently run</option>
          <option value="-byte_size">Largest files</option>
          <option value="byte_size">Smallest files</option>
          <option value="name">Name A–Z</option>
          <option value="-name">Name Z–A</option>
        </Select>
        <span
          className={clsx(
            "ml-auto inline-flex items-center gap-1 text-[11px] text-slate-500",
            isFetching ? "opacity-100" : "opacity-0",
          )}
          role="status"
          aria-live="polite"
        >
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" />
          Updating…
        </span>
      </div>
    </section>
  );
}

function DocumentsViewTabs({ view, onChange }: { view: DocumentsView; onChange: (view: DocumentsView) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {(Object.keys(DOCUMENT_VIEW_PRESETS) as DocumentsView[]).map((key) => {
        const preset = DOCUMENT_VIEW_PRESETS[key];
        const active = key === view;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={clsx(
              "rounded-full px-3 py-1 text-xs font-medium transition",
              active
                ? "bg-brand-600 text-white shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900",
            )}
            title={preset.description}
          >
            {preset.label}
          </button>
        );
      })}
    </div>
  );
}

function StatusFilterControl({
  selectedStatuses,
  onToggleStatus,
  onClearStatuses,
}: {
  selectedStatuses: ReadonlySet<DocumentStatus>;
  onToggleStatus: (status: DocumentStatus) => void;
  onClearStatuses: () => void;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const statusEntries = Object.entries(DOCUMENT_STATUS_LABELS) as [DocumentStatus, string][];
  const hasSelection = selectedStatuses.size > 0;
  const summaryLabel = hasSelection
    ? `${selectedStatuses.size} ${selectedStatuses.size === 1 ? "status" : "statuses"}`
    : "All statuses";

  useEffect(() => {
    if (!open) return undefined;
    const onClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", onClickOutside);
    return () => window.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 shadow-sm hover:border-slate-300"
        aria-haspopup="true"
        aria-expanded={open}
      >
        Status: {summaryLabel}
        <ChevronDownIcon className="h-3 w-3" />
      </button>
      {open ? (
        <div className="absolute z-30 mt-2 w-60 rounded-xl border border-slate-200 bg-white p-3 text-sm shadow-xl">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span>Status filters</span>
            <button
              type="button"
              onClick={() => {
                onClearStatuses();
                setOpen(false);
              }}
              className={clsx(
                "text-[11px]",
                hasSelection ? "text-slate-500 underline underline-offset-4" : "text-slate-300",
              )}
            >
              Clear
            </button>
          </div>
          <ul className="space-y-1 text-xs text-slate-600">
            {statusEntries.map(([status, label]) => {
              const active = selectedStatuses.has(status);
              return (
                <li key={status}>
                  <label className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={active}
                      onChange={() => onToggleStatus(status)}
                      className="h-3.5 w-3.5 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                    />
                      <span className="truncate">{label}</span>
                  </label>
                </li>
              );
            })}
          </ul>
          <div className="mt-3 flex justify-end">
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
              Done
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
/* ----------------------------- Documents table ----------------------------- */

interface DocumentsTableProps {
  readonly documents: readonly DocumentRecord[];
  readonly selectedIds: ReadonlySet<string>;
  readonly onToggleDocument: (documentId: string) => void;
  readonly onToggleAll: () => void;
  readonly disableSelection?: boolean;
  readonly disableRowActions?: boolean;
  readonly formatStatusLabel?: (status: DocumentRecord["status"]) => string;
  readonly onDeleteDocument?: (document: DocumentRecord) => void;
  readonly onDownloadDocument?: (document: DocumentRecord) => void;
  readonly onRunDocument?: (document: DocumentRecord) => void;
  readonly downloadingId?: string | null;
  readonly renderJobStatus?: (document: DocumentRecord) => ReactNode;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function DocumentsTable({
  documents,
  selectedIds,
  onToggleDocument,
  onToggleAll,
  disableSelection = false,
  disableRowActions = false,
  formatStatusLabel,
  onDeleteDocument,
  onDownloadDocument,
  onRunDocument,
  downloadingId = null,
  renderJobStatus,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: DocumentsTableProps) {
  const headerCheckboxRef = useRef<HTMLInputElement | null>(null);

  const { allSelected, someSelected } = useMemo(() => {
    if (documents.length === 0) return { allSelected: false, someSelected: false };
    const selectedCount = documents.reduce(
      (count, d) => (selectedIds.has(d.id) ? count + 1 : count),
      0,
    );
    return { allSelected: selectedCount === documents.length, someSelected: selectedCount > 0 && selectedCount < documents.length };
  }, [documents, selectedIds]);

  useEffect(() => {
    if (headerCheckboxRef.current) headerCheckboxRef.current.indeterminate = someSelected;
  }, [someSelected]);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full table-fixed border-separate border-spacing-0 text-sm text-slate-700">
        <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          <tr className="border-b border-slate-200">
            <th scope="col" className="w-10 px-2 py-2">
              <input
                ref={headerCheckboxRef}
                type="checkbox"
                className="h-4 w-4 rounded border border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                checked={allSelected}
                onChange={onToggleAll}
                disabled={disableSelection || documents.length === 0}
              />
            </th>
            <th scope="col" className="w-20 px-2 py-2 text-left">ID</th>
            <th scope="col" className="px-2 py-2 text-left">Document</th>
            <th scope="col" className="w-40 px-2 py-2 text-left">Uploaded</th>
            <th scope="col" className="w-48 px-2 py-2 text-left">Uploader</th>
            <th scope="col" className="w-48 px-2 py-2 text-left">Latest run</th>
            <th scope="col" className="w-32 px-2 py-2 text-left">Status</th>
            <th scope="col" className="w-36 px-2 py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => {
            const isSelected = selectedIds.has(document.id);
            return (
              <tr
                key={document.id}
                className={clsx(
                  "border-b border-slate-200 last:border-b-0 transition-colors hover:bg-slate-50",
                  isSelected ? "bg-brand-50/50" : "bg-white"
                )}
              >
                <td className="px-2 py-2 align-middle">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                    checked={isSelected}
                    onChange={() => onToggleDocument(document.id)}
                    disabled={disableSelection}
                  />
                </td>
                <td className="px-2 py-2 align-middle font-mono text-xs text-slate-500">
                  {document.id.slice(-6)}
                </td>
                <td className="px-2 py-2 align-middle">
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-slate-900" title={document.name}>
                      {document.name}
                    </div>
                    <div className="text-xs text-slate-500">{formatFileDescription(document)}</div>
                  </div>
                </td>
                <td className="px-2 py-2 align-middle">
                  <time
                    dateTime={document.created_at}
                    className="block text-xs text-slate-600"
                    title={uploadedFormatter.format(new Date(document.created_at))}
                  >
                    {formatUploadedAt(document)}
                  </time>
                </td>
                <td className="px-2 py-2 align-middle">
                  <span className="block truncate text-xs text-slate-600">
                    {document.uploader?.name ?? document.uploader?.email ?? "—"}
                  </span>
                </td>
                <td className="px-2 py-2 align-middle">
                  {renderJobStatus ? renderJobStatus(document) : null}
                </td>
                <td className="px-2 py-2 align-middle">
                  <span
                    className={clsx(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                      statusBadgeClass(document.status),
                    )}
                  >
                    {formatStatusLabel ? formatStatusLabel(document.status) : document.status}
                  </span>
                </td>
                <td className="px-2 py-2 align-middle text-right">
                  <DocumentActionsMenu
                    document={document}
                    onDownload={onDownloadDocument}
                    onDelete={onDeleteDocument}
                    onRun={onRunDocument}
                    disabled={disableRowActions}
                    downloading={downloadingId === document.id}
                    safeModeEnabled={safeModeEnabled}
                    safeModeMessage={safeModeMessage}
                    safeModeLoading={safeModeLoading}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------- Row actions ------------------------------- */

interface DocumentActionsMenuProps {
  readonly document: DocumentRecord;
  readonly onDownload?: (document: DocumentRecord) => void;
  readonly onDelete?: (document: DocumentRecord) => void;
  readonly onRun?: (document: DocumentRecord) => void;
  readonly disabled?: boolean;
  readonly downloading?: boolean;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function DocumentActionsMenu({
  document,
  onDownload,
  onDelete,
  onRun,
  disabled = false,
  downloading = false,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: DocumentActionsMenuProps) {
  const runDisabled = disabled || !onRun || safeModeEnabled || safeModeLoading;
  const runTitle = safeModeEnabled
    ? safeModeMessage ?? DEFAULT_SAFE_MODE_MESSAGE
    : safeModeLoading
      ? "Checking ADE safe mode status..."
      : undefined;

  return (
    <div className="inline-flex items-center gap-1.5">
      <Button
        type="button"
        size="sm"
        variant="primary"
        onClick={() => {
          if (runDisabled) return;
          onRun?.(document);
        }}
        disabled={runDisabled}
        title={runTitle}
      >
        Run
      </Button>

      <button
        type="button"
        onClick={() => onDownload?.(document)}
        className={clsx(
          "px-2 py-1 text-xs font-medium text-slate-600 underline underline-offset-4 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
          downloading && "opacity-60"
        )}
        disabled={disabled || downloading}
      >
        {downloading ? "Downloading…" : "Download"}
      </button>

      <button
        type="button"
        onClick={() => onDelete?.(document)}
        className="px-2 py-1 text-xs font-semibold text-danger-600 hover:text-danger-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500"
        disabled={disabled}
      >
        Delete
      </button>
    </div>
  );
}

/* --------------------------- Formatting helpers --------------------------- */

function formatFileDescription(document: DocumentRecord) {
  const parts: string[] = [];
  if (document.content_type) parts.push(humanizeContentType(document.content_type));
  if (typeof document.byte_size === "number" && document.byte_size >= 0) parts.push(formatFileSize(document.byte_size));
  return parts.join(" • ") || "Unknown type";
}

function humanizeContentType(contentType: string) {
  const mapping: Record<string, string> = {
    "application/pdf": "PDF document",
    "text/csv": "CSV file",
    "text/tab-separated-values": "TSV file",
    "application/vnd.ms-excel": "Excel spreadsheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel spreadsheet",
    "application/vnd.ms-excel.sheet.macroEnabled.12": "Excel macro spreadsheet",
  };
  return mapping[contentType] ?? contentType;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const formatted = value >= 10 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${formatted} ${units[unitIndex]}`;
}

function statusBadgeClass(status: DocumentRecord["status"]) {
  switch (status) {
    case "processed":
      return "bg-success-100 text-success-700";
    case "processing":
      return "bg-warning-100 text-warning-700";
    case "failed":
      return "bg-danger-100 text-danger-700";
    case "archived":
      return "bg-slate-200 text-slate-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

function formatUploadedAt(document: DocumentRecord) {
  return uploadedFormatter.format(new Date(document.created_at));
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.8} className={className}>
      <path d="M5 8l5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={clsx("animate-spin text-slate-500", className)}
      role="presentation"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        className="opacity-75"
        d="M22 12c0-5.523-4.477-10-10-10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}
/* --------------------------------- Run Drawer --------------------------------- */

interface RunExtractionDrawerProps {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly documentRecord: DocumentRecord | null;
  readonly onClose: () => void;
  readonly onRunSuccess?: (job: JobRecord) => void;
  readonly onRunError?: (message: string) => void;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function RunExtractionDrawer({
  open,
  workspaceId,
  documentRecord,
  onClose,
  onRunSuccess,
  onRunError,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: RunExtractionDrawerProps) {
  const previouslyFocusedElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (open) {
      previouslyFocusedElementRef.current =
        window.document.activeElement instanceof HTMLElement ? window.document.activeElement : null;
    } else {
      previouslyFocusedElementRef.current?.focus();
      previouslyFocusedElementRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (!open || typeof window === "undefined") return;
    const originalOverflow = window.document.body.style.overflow;
    window.document.body.style.overflow = "hidden";
    return () => {
      window.document.body.style.overflow = originalOverflow;
    };
  }, [open]);

  if (typeof window === "undefined" || !open || !documentRecord) return null;

  return createPortal(
    <RunExtractionDrawerContent
      workspaceId={workspaceId}
      documentRecord={documentRecord}
      onClose={onClose}
      onRunSuccess={onRunSuccess}
      onRunError={onRunError}
      safeModeEnabled={safeModeEnabled}
      safeModeMessage={safeModeMessage}
      safeModeLoading={safeModeLoading}
    />,
    window.document.body,
  );
}

interface DrawerContentProps {
  readonly workspaceId: string;
  readonly documentRecord: DocumentRecord;
  readonly onClose: () => void;
  readonly onRunSuccess?: (job: JobRecord) => void;
  readonly onRunError?: (message: string) => void;
  readonly safeModeEnabled?: boolean;
  readonly safeModeMessage?: string;
  readonly safeModeLoading?: boolean;
}

function RunExtractionDrawerContent({
  workspaceId,
  documentRecord,
  onClose,
  onRunSuccess,
  onRunError,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: DrawerContentProps) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();
  const configsQuery = useConfigsQuery({ workspaceId });
  const [selectedConfigId, setSelectedConfigId] = useState<string>("");
  const [selectedVersionId, setSelectedVersionId] = useState<string>("");
  const submitJob = useSubmitJob(workspaceId);
  const { preferences, setPreferences } = useDocumentRunPreferences(
    workspaceId,
    documentRecord.id,
  );
  const [activeJobId, setActiveJobId] = useState<string | null>(
    documentRecord.last_run?.job_id ?? null,
  );

  useEffect(() => {
    setActiveJobId(documentRecord.last_run?.job_id ?? null);
  }, [documentRecord.id, documentRecord.last_run?.job_id]);

  const allConfigs = useMemo(() => configsQuery.data?.items ?? [], [configsQuery.data]);
  const selectableConfigs = useMemo(
    () =>
      allConfigs.filter(
        (config) => !("deleted_at" in config && (config as { deleted_at?: string | null }).deleted_at),
      ),
    [allConfigs],
  );

  const preferredConfigId = useMemo(() => {
    if (preferences.configId) {
      const match = selectableConfigs.find((config) => config.config_id === preferences.configId);
      if (match) {
        return match.config_id;
      }
    }
    return selectableConfigs[0]?.config_id ?? "";
  }, [preferences.configId, selectableConfigs]);

  useEffect(() => {
    setSelectedConfigId(preferredConfigId);
  }, [preferredConfigId]);

  const versionsQuery = useConfigVersionsQuery({
    workspaceId,
    configId: selectedConfigId,
    enabled: Boolean(selectedConfigId),
  });
  const versionOptions = useMemo(
    () => versionsQuery.data ?? [],
    [versionsQuery.data],
  );
  const selectedConfig = useMemo(
    () => selectableConfigs.find((config) => config.config_id === selectedConfigId) ?? null,
    [selectableConfigs, selectedConfigId],
  );
  const selectedVersion = useMemo(
    () => versionOptions.find((version) => version.config_version_id === selectedVersionId) ?? null,
    [versionOptions, selectedVersionId],
  );
  const activeVersion = useMemo(() => findActiveVersion(versionOptions), [versionOptions]);
  const latestDraftVersion = useMemo(
    () => findLatestInactiveVersion(versionOptions),
    [versionOptions],
  );
  const preferredVersionId = useMemo(() => {
    if (!selectedConfigId) return "";
    if (preferences.configId === selectedConfigId && preferences.configVersionId) {
      const preferred = versionOptions.find(
        (version) => version.config_version_id === preferences.configVersionId,
      );
      if (preferred) {
        return preferred.config_version_id;
      }
    }
    if (activeVersion) return activeVersion.config_version_id;
    if (latestDraftVersion) return latestDraftVersion.config_version_id;
    return versionOptions[0]?.config_version_id ?? "";
  }, [
    activeVersion,
    latestDraftVersion,
    preferences.configId,
    preferences.configVersionId,
    selectedConfigId,
    versionOptions,
  ]);

  useEffect(() => {
    setSelectedVersionId(preferredVersionId);
  }, [preferredVersionId]);

  const formatConfigLabel = useCallback((config: (typeof selectableConfigs)[number]) => {
    const statusLabel = typeof config.status === "string" ? config.status : "draft";
    const title = (config as { title?: string | null }).title ?? config.display_name ?? "Untitled configuration";
    return `${title} (${statusLabel.charAt(0).toUpperCase()}${statusLabel.slice(1)})`;
  }, []);

  const formatVersionLabel = useCallback((version: (typeof versionOptions)[number]) => {
    const status =
      version.status === "active"
        ? "Active"
        : version.status === "published"
          ? "Published"
          : version.status === "inactive"
            ? "Inactive"
            : "Draft";
    const semver = version.semver ?? "–";
    return `v${semver} (${status})`;
  }, []);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const safeModeDetail = safeModeMessage ?? DEFAULT_SAFE_MODE_MESSAGE;

  const jobQuery = useQuery({
    queryKey: ["job", workspaceId, activeJobId],
    queryFn: ({ signal }) =>
      activeJobId
        ? fetchJob(workspaceId, activeJobId, signal)
        : Promise.reject(new Error("No job selected")),
    enabled: Boolean(activeJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "queued" ? 2000 : false;
    },
  });

  const outputsQuery = useQuery({
    queryKey: ["job-outputs", workspaceId, activeJobId],
    queryFn: ({ signal }) =>
      activeJobId
        ? fetchJobOutputs(workspaceId, activeJobId, signal)
        : Promise.reject(new Error("No job selected")),
    enabled:
      Boolean(activeJobId) &&
      (jobQuery.data?.status === "succeeded" || jobQuery.data?.status === "failed"),
    staleTime: 5_000,
  });

  const artifactQuery = useQuery({
    queryKey: ["job-artifact", workspaceId, activeJobId],
    queryFn: ({ signal }) =>
      activeJobId
        ? fetchJobArtifact(workspaceId, activeJobId, signal)
        : Promise.reject(new Error("No job selected")),
    enabled:
      Boolean(activeJobId) &&
      (jobQuery.data?.status === "succeeded" || jobQuery.data?.status === "failed"),
    staleTime: 5_000,
  });

  const telemetryQuery = useQuery({
    queryKey: ["job-telemetry", workspaceId, activeJobId],
    queryFn: ({ signal }) =>
      activeJobId
        ? fetchJobTelemetry(workspaceId, activeJobId, signal)
        : Promise.reject(new Error("No job selected")),
    enabled:
      Boolean(activeJobId) &&
      (jobQuery.data?.status === "succeeded" || jobQuery.data?.status === "failed"),
    staleTime: 5_000,
  });

  const sheetQuery = useQuery<DocumentSheet[]>({
    queryKey: ["document-sheets", workspaceId, documentRecord.id],
    queryFn: ({ signal }) => fetchDocumentSheets(workspaceId, documentRecord.id, signal),
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
    const preferred = (preferences.sheetNames ?? []).filter((sheetName) =>
      sheetOptions.some((sheet) => sheet.name === sheetName),
    );
    const uniquePreferred = Array.from(new Set(preferred));
    setSelectedSheets(uniquePreferred);
  }, [sheetOptions, preferences.sheetNames]);

  const normalizedSheetSelection = useMemo(
    () =>
      Array.from(
        new Set(selectedSheets.filter((name) => sheetOptions.some((sheet) => sheet.name === name))),
      ),
    [selectedSheets, sheetOptions],
  );

  useEffect(() => {
    if (!selectedConfig || !selectedVersionId) {
      return;
    }
    setPreferences({
      configId: selectedConfig.config_id,
      configVersionId: selectedVersionId,
      sheetNames: normalizedSheetSelection.length ? normalizedSheetSelection : null,
    });
  }, [normalizedSheetSelection, selectedConfig, selectedVersionId, setPreferences]);

  const toggleWorksheet = useCallback((name: string) => {
    setSelectedSheets((current) =>
      current.includes(name) ? current.filter((sheet) => sheet !== name) : [...current, name],
    );
  }, []);

  const currentJob = jobQuery.data ?? null;
  const jobStatus = currentJob?.status ?? null;
  const jobRunning = jobStatus === "running" || jobStatus === "queued";
  const downloadBase = activeJobId
    ? `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/jobs/${encodeURIComponent(activeJobId)}`
    : null;
  const outputFiles: JobOutputListing["files"] = outputsQuery.data?.files ?? [];
  const artifact = artifactQuery.data ?? null;
  const telemetryEvents = telemetryQuery.data ?? [];

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const focusable = getFocusableElements(dialog);
    (focusable[0] ?? dialog).focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const focusableElements = getFocusableElements(dialog);
      if (focusableElements.length === 0) {
        event.preventDefault();
        return;
      }
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = window.document.activeElement;

      if (event.shiftKey) {
        if (!dialog.contains(activeElement) || activeElement === firstElement) {
          event.preventDefault();
          lastElement.focus();
        }
        return;
      }

      if (activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    dialog.addEventListener("keydown", handleKeyDown);
    return () => dialog.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const hasConfigurations = selectableConfigs.length > 0;
  const runDisabled =
    submitJob.isPending ||
    jobRunning ||
    safeModeLoading ||
    safeModeEnabled ||
    !hasConfigurations ||
    !selectedVersionId;
  const runButtonTitle = safeModeEnabled
    ? safeModeDetail
    : safeModeLoading
      ? "Checking ADE safe mode status..."
      : undefined;

  const handleSubmit = () => {
    if (safeModeEnabled || safeModeLoading) {
      return;
    }
    if (!selectedConfig || !selectedVersion || !selectedVersionId) {
      setErrorMessage("Select a configuration before running the extractor.");
      return;
    }
    setErrorMessage(null);
    setActiveJobId(null);
    const sheetList = normalizedSheetSelection;
    const runOptions =
      sheetList.length > 0
        ? { dry_run: false, validate_only: false, input_sheet_names: sheetList }
        : { dry_run: false, validate_only: false };
    submitJob.mutate(
      {
        input_document_id: documentRecord.id,
        config_version_id: selectedVersionId,
        options: runOptions,
      },
      {
        onSuccess: (job) => {
          setPreferences({
            configId: selectedConfig.config_id,
            configVersionId: selectedVersionId,
            sheetNames: sheetList.length ? sheetList : null,
          });
          onRunSuccess?.(job);
          setActiveJobId(job.id);
        },
        onError: (error) => {
          const message = error instanceof Error ? error.message : "Unable to submit extraction job.";
          setErrorMessage(message);
          onRunError?.(message);
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        className="flex-1 bg-slate-900/30 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="relative flex h-full w-[min(28rem,92vw)] flex-col border-l border-slate-200 bg-white shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 id={titleId} className="text-lg font-semibold text-slate-900">Run extraction</h2>
            <p id={descriptionId} className="text-xs text-slate-500">Prepare and submit a processing job.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={submitJob.isPending}>
            Close
          </Button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 text-sm text-slate-600">
          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Document</p>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold text-slate-800" title={documentRecord.name}>{documentRecord.name}</p>
              <p className="text-xs text-slate-500">Uploaded {new Date(documentRecord.created_at).toLocaleString()}</p>
              {documentRecord.last_run_at ? (
                <p className="text-xs text-slate-500">
                  Last run {new Date(documentRecord.last_run_at).toLocaleString()}
                </p>
              ) : null}
            </div>
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Configuration</p>
            {configsQuery.isLoading ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                Loading configurations…
              </div>
            ) : configsQuery.isError ? (
              <Alert tone="danger">
                Unable to load configurations.{" "}
                {configsQuery.error instanceof Error ? configsQuery.error.message : "Try again later."}
              </Alert>
            ) : hasConfigurations ? (
              <div className="space-y-2">
                <Select
                  value={selectedConfigId}
                  onChange={(event) => {
                    const value = event.target.value;
                    setSelectedConfigId(value);
                    setSelectedVersionId("");
                  }}
                  disabled={submitJob.isPending}
                >
                  <option value="">Select configuration</option>
                  {selectableConfigs.map((config) => (
                    <option key={config.config_id} value={config.config_id}>
                      {formatConfigLabel(config)}
                    </option>
                  ))}
                </Select>

                {selectedConfigId ? (
                  versionsQuery.isLoading ? (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                      Loading versions…
                    </div>
                  ) : versionsQuery.isError ? (
                    <Alert tone="danger">
                      Unable to load configuration versions.{" "}
                      {versionsQuery.error instanceof Error ? versionsQuery.error.message : "Try again later."}
                    </Alert>
                  ) : versionOptions.length > 0 ? (
                    <Select
                      value={selectedVersionId}
                      onChange={(event) => setSelectedVersionId(event.target.value)}
                      disabled={submitJob.isPending}
                    >
                      <option value="">Select version</option>
                      {versionOptions.map((version) => (
                        <option key={version.config_version_id} value={version.config_version_id}>
                          {formatVersionLabel(version)}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <Alert tone="info">No versions available for this configuration.</Alert>
                  )
                ) : null}
              </div>
            ) : (
              <Alert tone="info">No configurations available. Create one before running extraction.</Alert>
            )}
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Advanced options</p>
            {sheetQuery.isLoading ? (
              <p className="text-xs text-slate-500">Loading worksheets…</p>
            ) : sheetQuery.isError ? (
              <Alert tone="warning">
                <div className="space-y-2">
                  <p className="text-xs text-slate-700">
                    Worksheet metadata is temporarily unavailable. The run will process the entire
                    file unless you retry and pick specific sheets.
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
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedSheets([])}
                      disabled={submitJob.isPending}
                    >
                      Use all worksheets
                    </Button>
                  </div>
                </div>
              </Alert>
            ) : sheetOptions.length > 0 ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-slate-600">Worksheets</p>
                    <p className="text-[11px] text-slate-500">
                      {normalizedSheetSelection.length === 0
                        ? "All worksheets will be processed by default. Select any subset to narrow the run."
                        : `${normalizedSheetSelection.length.toLocaleString()} worksheet${
                            normalizedSheetSelection.length === 1 ? "" : "s"
                          } selected. Clear selections to process every sheet.`}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedSheets([])}
                disabled={submitJob.isPending}
              >
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
              <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                This document does not expose multiple worksheets, so ADE will ingest the uploaded file directly.
              </p>
            )}
          </section>

          {activeJobId ? (
            <section className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Latest run</p>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-slate-800" title={activeJobId}>
                      Job {activeJobId}
                    </p>
                    <p className="text-xs text-slate-500">
                      Status: {jobStatus ?? "loading…"}
                    </p>
                  </div>
                  {jobRunning ? <SpinnerIcon className="h-4 w-4 text-slate-500" /> : null}
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  <a
                    href={downloadBase ? `${downloadBase}/artifact` : undefined}
                    className={clsx(
                      "inline-flex items-center rounded border px-3 py-1 text-xs font-semibold transition",
                      downloadBase && !jobRunning
                        ? "border-slate-300 text-slate-700 hover:bg-slate-100"
                        : "cursor-not-allowed border-slate-200 text-slate-400",
                    )}
                    aria-disabled={jobRunning || !downloadBase}
                  >
                    Download artifact
                  </a>
                  <a
                    href={downloadBase ? `${downloadBase}/logs` : undefined}
                    className={clsx(
                      "inline-flex items-center rounded border px-3 py-1 text-xs font-semibold transition",
                      downloadBase ? "border-slate-300 text-slate-700 hover:bg-slate-100" : "cursor-not-allowed border-slate-200 text-slate-400",
                    )}
                    aria-disabled={!downloadBase}
                  >
                    Download telemetry
                  </a>
                </div>

                <div className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2">
                  <p className="text-xs font-semibold text-slate-700">Output files</p>
                  {outputsQuery.isLoading ? (
                    <p className="text-xs text-slate-500">Loading outputs…</p>
                  ) : outputFiles.length > 0 ? (
                    <ul className="mt-1 space-y-1 text-xs text-slate-700">
                      {outputFiles.map((file) => (
                        <li key={file.path} className="flex items-center justify-between gap-2 break-all rounded border border-slate-100 px-2 py-1">
                          <a
                            href={downloadBase ? `${downloadBase}/outputs/${file.path.split("/").map(encodeURIComponent).join("/")}` : undefined}
                            className="text-emerald-700 hover:underline"
                            aria-disabled={!downloadBase}
                          >
                            {file.path}
                          </a>
                          <span className="text-[11px] text-slate-500">{file.byte_size.toLocaleString()} bytes</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-slate-500">Outputs will appear here after the run completes.</p>
                  )}
                </div>
                <div className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2">
                  <p className="text-xs font-semibold text-slate-700">Artifact summary</p>
                  {artifactQuery.isLoading ? (
                    <p className="text-xs text-slate-500">Loading artifact…</p>
                  ) : artifactQuery.isError ? (
                    <p className="text-xs text-rose-600">Unable to load artifact.</p>
                  ) : artifact ? (
                    <ArtifactSummary artifact={artifact} />
                  ) : (
                    <p className="text-xs text-slate-500">Artifact not available.</p>
                  )}
                </div>
                <div className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2">
                  <p className="text-xs font-semibold text-slate-700">Telemetry summary</p>
                  {telemetryQuery.isLoading ? (
                    <p className="text-xs text-slate-500">Loading telemetry…</p>
                  ) : telemetryQuery.isError ? (
                    <p className="text-xs text-rose-600">Unable to load telemetry events.</p>
                  ) : telemetryEvents.length > 0 ? (
                    <TelemetrySummary events={telemetryEvents} />
                  ) : (
                    <p className="text-xs text-slate-500">No telemetry events captured.</p>
                  )}
                </div>
              </div>
            </section>
          ) : null}

          {safeModeEnabled ? <Alert tone="warning">{safeModeDetail}</Alert> : null}
          {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <Button type="button" variant="ghost" onClick={onClose} disabled={submitJob.isPending}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            isLoading={submitJob.isPending}
            disabled={runDisabled}
            title={runButtonTitle}
          >
            Run extraction
          </Button>
        </footer>
      </aside>
    </div>
  );
}
/* ------------------------ Global drag & drop overlay ------------------------ */

function DropAnywhereOverlay({
  onFiles,
  disabled,
  workspaceName,
}: {
  onFiles: (files: File[]) => void | Promise<void>;
  disabled?: boolean;
  workspaceName?: string;
}) {
  const [active, setActive] = useState(false);
  const counterRef = useRef(0);

  useEffect(() => {
    if (disabled) return;

    const onDragEnter = (e: DragEvent) => {
      if (!e.dataTransfer || ![...e.dataTransfer.types].includes("Files")) return;
      counterRef.current += 1;
      setActive(true);
    };
    const onDragOver = (e: DragEvent) => {
      if (!active) return;
      e.preventDefault();
    };
    const onDragLeave = () => {
      counterRef.current = Math.max(0, counterRef.current - 1);
      if (counterRef.current === 0) setActive(false);
    };
    const onDrop = (e: DragEvent) => {
      e.preventDefault();
      setActive(false);
      counterRef.current = 0;
      const files = Array.from(e.dataTransfer?.files ?? []);
      if (files.length) void onFiles(files);
    };

    window.addEventListener("dragenter", onDragEnter);
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("dragleave", onDragLeave);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragenter", onDragEnter);
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("dragleave", onDragLeave);
      window.removeEventListener("drop", onDrop);
    };
  }, [active, disabled, onFiles]);

  return (
    <div
      aria-hidden={!active}
      className={clsx(
        "pointer-events-none fixed inset-0 z-[60] transition",
        active ? "opacity-100" : "opacity-0"
      )}
    >
      <div className="absolute inset-0 bg-slate-900/25 backdrop-blur-[2px]" />
      <div className="absolute inset-0 flex items-center justify-center p-6">
        <div className="pointer-events-none rounded-2xl border border-white/70 bg-white/90 px-6 py-5 shadow-2xl">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-white shadow">
              <svg viewBox="0 0 24 24" className="h-5 w-5 text-slate-700" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M12 16V4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M6 10l6-6 6 6" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <div className="text-center sm:text-left">
              <p className="text-base font-semibold text-slate-900">Drop to upload</p>
              <p className="text-sm text-slate-600">
                Files will upload to <span className="font-medium">{workspaceName ?? "this workspace"}</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------- UI helpers -------------------------------- */

function SkeletonList() {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <div className="h-4 w-4 rounded bg-slate-100" />
          <div className="h-4 flex-1 rounded bg-slate-100" />
          <div className="h-4 w-24 rounded bg-slate-100" />
          <div className="h-4 w-40 rounded bg-slate-100" />
          <div className="h-8 w-40 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

function BulkBar({
  count,
  onClear,
  onRun,
  onDelete,
  busy,
  safeModeEnabled = false,
  safeModeMessage,
  safeModeLoading = false,
}: {
  count: number;
  onClear: () => void;
  onRun: () => void;
  onDelete: () => void;
  busy?: boolean;
  safeModeEnabled?: boolean;
  safeModeMessage?: string;
  safeModeLoading?: boolean;
}) {
  if (count === 0) return null;
  const runDisabled = busy || safeModeEnabled || safeModeLoading;
  const runTitle = safeModeEnabled
    ? safeModeMessage ?? DEFAULT_SAFE_MODE_MESSAGE
    : safeModeLoading
      ? "Checking ADE safe mode status..."
      : undefined;
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 mx-auto max-w-7xl px-2 pb-2 sm:px-4 sm:pb-4">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white/95 p-3 text-sm text-slate-700 shadow-lg backdrop-blur">
        <span className="mr-2"><strong>{count}</strong> selected</span>
        <Button variant="ghost" size="sm" onClick={onClear}>Clear</Button>
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" onClick={() => !runDisabled && onRun()} disabled={runDisabled} title={runTitle}>
            Run extraction
          </Button>
          <Button size="sm" variant="danger" onClick={onDelete} disabled={busy} isLoading={busy}>
            Delete selected
          </Button>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onUploadClick }: { onUploadClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-50">
        <svg className="h-6 w-6 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M12 16V4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M6 10l6-6 6 6" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-base font-semibold text-slate-900">No documents yet</p>
      <p className="max-w-md text-sm text-slate-600">Tap Upload or drag files anywhere in the window.</p>
      <Button onClick={onUploadClick} className="w-full sm:w-auto">Upload</Button>
    </div>
  );
}

/* ------------------------------ Job status chip ------------------------------ */

function DocumentJobStatus({ document }: { document: DocumentRecord }) {
  const lastRun = document.last_run;
  if (!lastRun) return <span className="text-xs text-slate-400">No runs yet</span>;

  return (
    <div className="flex flex-col gap-1">
      <span
        className={clsx(
          "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
          jobStatusBadgeClass(lastRun.status as JobStatus),
        )}
      >
        {formatJobStatus(lastRun.status as JobStatus)}
        {lastRun.run_at ? (
          <span className="ml-1 font-normal text-slate-500">{formatRelativeTime(lastRun.run_at)}</span>
        ) : null}
      </span>
      {lastRun.message ? <span className="text-[11px] text-slate-500">{lastRun.message}</span> : null}
    </div>
  );
}

function jobStatusBadgeClass(status: JobStatus) {
  switch (status) {
    case "succeeded":
      return "bg-success-100 text-success-700";
    case "failed":
      return "bg-danger-100 text-danger-700";
    case "running":
      return "bg-brand-100 text-brand-700";
    default:
      return "bg-slate-200 text-slate-700";
  }
}

function formatJobStatus(status: JobStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
function formatRelativeTime(value?: string | null) {
  if (!value) return "unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  const diffMs = date.getTime() - Date.now();
  const diffSeconds = Math.round(diffMs / 1000);
  const absSeconds = Math.abs(diffSeconds);
  if (absSeconds < 60) return relativeTimeFormatter.format(diffSeconds, "second");
  const diffMinutes = Math.round(diffSeconds / 60);
  const absMinutes = Math.abs(diffMinutes);
  if (absMinutes < 60) return relativeTimeFormatter.format(diffMinutes, "minute");
  const diffHours = Math.round(diffMinutes / 60);
  const absHours = Math.abs(diffHours);
  if (absHours < 24) return relativeTimeFormatter.format(diffHours, "hour");
  const diffDays = Math.round(diffHours / 24);
  if (Math.abs(diffDays) < 30) return relativeTimeFormatter.format(diffDays, "day");
  const diffMonths = Math.round(diffDays / 30);
  if (Math.abs(diffMonths) < 12) return relativeTimeFormatter.format(diffMonths, "month");
  const diffYears = Math.round(diffDays / 365);
  return relativeTimeFormatter.format(diffYears, "year");
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function getFocusableElements(container: HTMLElement) {
  const selectors = [
    'a[href]',
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ];
  return Array.from(container.querySelectorAll<HTMLElement>(selectors.join(','))).filter(
    (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true',
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/Jobs/index.tsx
```tsx
import { useMemo, useState } from "react";
import clsx from "clsx";

import { useInfiniteQuery } from "@tanstack/react-query";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { fetchWorkspaceJobs, workspaceJobsKeys, type JobRecord, type JobStatus } from "@shared/jobs";

import { Button } from "@ui/Button";
import { Select } from "@ui/Select";
import { PageState } from "@ui/PageState";

const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  succeeded: "Succeeded",
  failed: "Failed",
  running: "Running",
  queued: "Queued",
  cancelled: "Cancelled",
};

const JOB_STATUS_CLASSES: Record<JobStatus, string> = {
  succeeded: "bg-success-100 text-success-700",
  failed: "bg-rose-100 text-rose-700",
  running: "bg-brand-50 text-brand-700",
  queued: "bg-slate-100 text-slate-700",
  cancelled: "bg-slate-200 text-slate-700",
};

const TIME_RANGE_OPTIONS = [
  { value: "24h", label: "Last 24 hours", durationMs: 24 * 60 * 60 * 1000 },
  { value: "7d", label: "Last 7 days", durationMs: 7 * 24 * 60 * 60 * 1000 },
  { value: "30d", label: "Last 30 days", durationMs: 30 * 24 * 60 * 60 * 1000 },
  { value: "all", label: "All time", durationMs: null },
  { value: "custom", label: "Custom range", durationMs: null },
] as const;

const SORT_OPTIONS = [
  { value: "recent", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "duration_desc", label: "Longest duration" },
] as const;

const JOBS_PAGE_SIZE = 100;

export default function WorkspaceJobsRoute() {
  const { workspace } = useWorkspaceContext();
  const [selectedStatuses, setSelectedStatuses] = useState<Set<JobStatus>>(new Set());
  const [timeRange, setTimeRange] = useState<(typeof TIME_RANGE_OPTIONS)[number]["value"]>("7d");
  const [sortOrder, setSortOrder] = useState<(typeof SORT_OPTIONS)[number]["value"]>("recent");
  const [searchTerm, setSearchTerm] = useState("");
  const [customRange, setCustomRange] = useState<{ start: string; end: string }>({ start: "", end: "" });

  const singleStatusForQuery = selectedStatuses.size === 1 ? Array.from(selectedStatuses)[0] : null;

  const jobsQuery = useInfiniteQuery<JobRecord[]>({
    queryKey: workspaceJobsKeys.list(workspace.id, { status: singleStatusForQuery ?? "all" }),
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceJobs(
        workspace.id,
        {
          status: singleStatusForQuery,
          limit: JOBS_PAGE_SIZE,
          offset: pageParam,
        },
        signal,
      ),
    getNextPageParam: (lastPage, pages) =>
      lastPage.length === JOBS_PAGE_SIZE ? pages.length * JOBS_PAGE_SIZE : undefined,
    enabled: Boolean(workspace.id),
    staleTime: 30_000,
  });

  const jobs = useMemo(() => {
    const pages = jobsQuery.data?.pages ?? [];
    return pages.flat();
  }, [jobsQuery.data?.pages]);

  const filteredJobs = useMemo(() => {
    const now = Date.now();
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const timeConfig = TIME_RANGE_OPTIONS.find((option) => option.value === timeRange);
    const horizon = timeConfig?.value === "custom" ? null : timeConfig?.durationMs ?? null;
    let customStartMs = customRange.start ? new Date(customRange.start).getTime() : null;
    let customEndMs = customRange.end ? new Date(customRange.end).getTime() : null;
    if (customStartMs && customEndMs && customStartMs > customEndMs) {
      [customStartMs, customEndMs] = [customEndMs, customStartMs];
    }

    return jobs
      .filter((job) => {
        if (selectedStatuses.size > 0 && !selectedStatuses.has(job.status as JobStatus)) {
          return false;
        }
        if (timeRange === "custom") {
          const startedAt = getJobStartTimestamp(job);
          if (customStartMs && startedAt < customStartMs) return false;
          if (customEndMs && startedAt > customEndMs) return false;
        } else if (horizon) {
          const startedAt = getJobStartTimestamp(job);
          if (now - startedAt > horizon) return false;
        }
        if (normalizedSearch) {
          if (!jobSearchHaystack(job).includes(normalizedSearch)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        switch (sortOrder) {
          case "oldest":
            return getJobStartTimestamp(a) - getJobStartTimestamp(b);
          case "duration_desc":
            return durationMs(b) - durationMs(a);
          case "recent":
          default:
            return getJobStartTimestamp(b) - getJobStartTimestamp(a);
        }
      });
  }, [jobs, selectedStatuses, timeRange, sortOrder, searchTerm, customRange]);

  const toggleStatus = (status: JobStatus) => {
    setSelectedStatuses((current) => {
      const next = new Set(current);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  };

  const clearFilters = () => {
    setSelectedStatuses(new Set());
    setTimeRange("7d");
    setSortOrder("recent");
    setSearchTerm("");
    setCustomRange({ start: "", end: "" });
  };

  const handleExport = () => {
    if (filteredJobs.length === 0) return;
    const rows = filteredJobs.map((job) => [
      job.id,
      deriveDocumentName(job) ?? "—",
      deriveConfigLabel(job),
      deriveTriggeredBy(job) ?? "—",
      job.status,
      formatTimestamp(getJobStartTimestamp(job)),
      formatTimestamp(getJobEndTimestamp(job)),
      (durationMs(job) / 1000).toFixed(1),
      (job as { error_message?: string }).error_message ?? "",
    ]);
    const header = [
      "Job ID",
      "Document",
      "Config",
      "Triggered by",
      "Status",
      "Started",
      "Finished",
      "Duration (s)",
      "Error message",
    ];
    const csv = [header, ...rows]
      .map((cols) => cols.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `jobs-${new Date().toISOString()}.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white/95 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Jobs</p>
            <h1 className="text-lg font-semibold text-slate-900 sm:text-xl">{workspace.name ?? "Workspace"} jobs</h1>
            <p className="text-xs text-slate-500">Review previous runs, filter by status, and export job history.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={handleExport} disabled={filteredJobs.length === 0}>
              Export CSV
            </Button>
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Reset filters
            </Button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <StatusPillBar selected={selectedStatuses} onToggle={toggleStatus} />
          <Select value={timeRange} onChange={(event) => setTimeRange(event.target.value as typeof timeRange)} className="w-48">
            {TIME_RANGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          {timeRange === "custom" ? (
            <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              <label className="flex flex-col gap-1">
                Start
                <input
                  type="datetime-local"
                  value={customRange.start}
                  onChange={(event) => setCustomRange((prev) => ({ ...prev, start: event.target.value }))}
                  className="rounded-lg border border-slate-200 px-2 py-1 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
                />
              </label>
              <label className="flex flex-col gap-1">
                End
                <input
                  type="datetime-local"
                  value={customRange.end}
                  onChange={(event) => setCustomRange((prev) => ({ ...prev, end: event.target.value }))}
                  className="rounded-lg border border-slate-200 px-2 py-1 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
                />
              </label>
            </div>
          ) : null}
          <Select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as typeof sortOrder)} className="w-48">
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <div className="flex-1 min-w-[220px]">
            <input
              type="search"
              placeholder="Search jobs by ID, document, or config"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        {jobsQuery.isError ? (
          <div className="py-16">
            <PageState
              variant="error"
              title="Unable to load jobs"
              description="We couldn’t fetch job history right now. Try reloading the page."
            />
          </div>
        ) : jobsQuery.isLoading ? (
          <div className="py-16 text-center text-sm text-slate-500">Loading jobs…</div>
        ) : filteredJobs.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-sm text-slate-500">No jobs match the current filters.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full table-fixed border-separate border-spacing-0 text-sm text-slate-700">
                <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2 text-left">Job ID</th>
                    <th className="px-3 py-2 text-left">Document</th>
                    <th className="px-3 py-2 text-left">Config</th>
                    <th className="px-3 py-2 text-left">Triggered by</th>
                    <th className="px-3 py-2 text-left">Started</th>
                    <th className="px-3 py-2 text-left">Duration</th>
                    <th className="px-3 py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredJobs.map((job) => {
                    const documentName = deriveDocumentName(job);
                    const configLabel = deriveConfigLabel(job);
                    const triggeredBy = deriveTriggeredBy(job);
                    const status = job.status as JobStatus;
                    return (
                      <tr key={job.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 font-mono text-xs text-slate-500">{job.id}</td>
                        <td className="px-3 py-2">
                          <p className="truncate font-semibold text-slate-900">{documentName ?? "—"}</p>
                          <p className="text-xs text-slate-500">
                            {Array.isArray((job as { input_documents?: unknown[] }).input_documents)
                              ? `${(job as { input_documents?: unknown[] }).input_documents?.length ?? 0} document(s)`
                              : "—"}
                          </p>
                        </td>
                        <td className="px-3 py-2">
                          <p className="truncate text-slate-800">{configLabel}</p>
                        </td>
                        <td className="px-3 py-2 text-slate-600">{triggeredBy ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-600">
                          <time dateTime={new Date(getJobStartTimestamp(job)).toISOString()}>
                            {formatTimestamp(getJobStartTimestamp(job))}
                          </time>
                        </td>
                        <td className="px-3 py-2 text-slate-600">{formatDuration(durationMs(job))}</td>
                        <td className="px-3 py-2">
                          <span
                            className={clsx(
                              "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                              JOB_STATUS_CLASSES[status] ?? "bg-slate-200 text-slate-700",
                            )}
                          >
                            {JOB_STATUS_LABELS[status] ?? status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {jobsQuery.hasNextPage ? (
              <div className="border-t border-slate-200 bg-slate-50/60 px-3 py-2 text-center">
                <Button
                  variant="ghost"
                  onClick={() => jobsQuery.fetchNextPage()}
                  disabled={jobsQuery.isFetchingNextPage}
                  isLoading={jobsQuery.isFetchingNextPage}
                >
                  Load more jobs
                </Button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}

function StatusPillBar({
  selected,
  onToggle,
}: {
  selected: ReadonlySet<JobStatus>;
  onToggle: (status: JobStatus) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {(Object.keys(JOB_STATUS_LABELS) as JobStatus[]).map((status) => {
        const active = selected.has(status);
        return (
          <button
            key={status}
            type="button"
            onClick={() => onToggle(status)}
            className={clsx(
              "rounded-full px-3 py-1 text-xs font-medium",
              active
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900",
            )}
          >
            {JOB_STATUS_LABELS[status]}
          </button>
        );
      })}
    </div>
  );
}

function deriveDocumentName(job: JobRecord) {
  const documents = (job as { input_documents?: unknown[] }).input_documents;
  if (!Array.isArray(documents) || documents.length === 0) return null;
  const primary = documents[0] as Record<string, string> | undefined;
  if (!primary) return null;
  return primary.display_name ?? primary.name ?? primary.original_filename ?? primary.id ?? null;
}

function deriveConfigLabel(job: JobRecord) {
  const configVersion = (job as { config_version?: Record<string, string> }).config_version;
  if (configVersion) {
    return configVersion.title ?? configVersion.semver ?? configVersion.config_version_id ?? "—";
  }
  return (job as { config_title?: string }).config_title ?? (job as { config_id?: string }).config_id ?? "—";
}

function deriveTriggeredBy(job: JobRecord) {
  const submitted = (job as { submitted_by_user?: { display_name?: string; email?: string } }).submitted_by_user;
  if (submitted) return submitted.display_name ?? submitted.email ?? null;
  return (job as { submitted_by?: string }).submitted_by ?? null;
}

function jobSearchHaystack(job: JobRecord) {
  return [
    job.id,
    deriveDocumentName(job),
    deriveConfigLabel(job),
    deriveTriggeredBy(job),
    job.status,
    (job as { error_message?: string }).error_message,
    (job as { summary?: string }).summary,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function getJobStartTimestamp(job: JobRecord) {
  const ms =
    (job as { started_at?: string }).started_at ??
    (job as { queued_at?: string }).queued_at ??
    (job as { created_at?: string }).created_at ??
    ((job as { created?: number }).created ? (job as { created?: number }).created * 1000 : null);
  return typeof ms === "string" ? new Date(ms).getTime() : typeof ms === "number" ? ms : Date.now();
}

function getJobEndTimestamp(job: JobRecord) {
  const ms =
    (job as { completed_at?: string }).completed_at ??
    (job as { cancelled_at?: string }).cancelled_at ??
    (job as { updated_at?: string }).updated_at;
  return typeof ms === "string" ? new Date(ms).getTime() : typeof ms === "number" ? ms : Date.now();
}

function durationMs(job: JobRecord) {
  const start = getJobStartTimestamp(job);
  const end = getJobEndTimestamp(job);
  if (!start || !end) return 0;
  return Math.max(0, end - start);
}

function formatDuration(ms: number) {
  if (ms <= 0) return "—";
  const seconds = Math.round(ms / 100) / 10;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  return `${minutes}m ${remaining}s`;
}

function formatTimestamp(ms: number) {
  if (!ms) return "—";
  return new Date(ms).toLocaleString();
}
```

# apps/ade-web/src/screens/Workspace/sections/Overview/index.tsx
```tsx
export default function WorkspaceOverviewRoute() {
  return (
    <section>
      <h1 className="text-xl font-semibold">Workspace Overview</h1>
      <p className="mt-2 text-sm text-slate-600">TODO: add workspace summary widgets.</p>
    </section>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/Settings/components/SafeModeControls.tsx
```tsx
import { useEffect, useMemo, useState } from "react";

import { useSession } from "@shared/auth/context/SessionContext";
import {
  DEFAULT_SAFE_MODE_MESSAGE,
  useSafeModeStatus,
  useUpdateSafeModeStatus,
} from "@shared/system";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { TextArea } from "@ui/Input";

export function SafeModeControls() {
  const session = useSession();
  const safeModeStatus = useSafeModeStatus();
  const updateSafeMode = useUpdateSafeModeStatus();
  const [detail, setDetail] = useState(DEFAULT_SAFE_MODE_MESSAGE);

  const currentStatus = safeModeStatus.data;
  useEffect(() => {
    if (currentStatus?.detail) {
      setDetail(currentStatus.detail);
    }
  }, [currentStatus?.detail]);

  const canManageSafeMode = useMemo(() => {
    const permissions = session.user.permissions ?? [];
    return permissions.includes("System.Settings.ReadWrite");
  }, [session.user.permissions]);

  const isPending = safeModeStatus.isFetching || updateSafeMode.isPending;
  const normalizedDetail = detail.trim() || DEFAULT_SAFE_MODE_MESSAGE;

  const handleToggle = (enabled: boolean) => {
    updateSafeMode.mutate(
      { enabled, detail: normalizedDetail },
      {
        onSuccess: (nextStatus) => {
          setDetail(nextStatus.detail);
        },
      },
    );
  };

  return (
    <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-900">ADE safe mode</h2>
        <p className="text-sm text-slate-500">
          Toggle whether streamed runs should short-circuit before invoking the ADE engine. Use this to pause execution during
          maintenance or while verifying a new config release.
        </p>
      </header>

      {safeModeStatus.isError ? (
        <Alert tone="danger">Unable to load safe mode status.</Alert>
      ) : null}

      {!canManageSafeMode ? (
        <Alert tone="warning">
          You need the <strong>System.Settings.ReadWrite</strong> permission to change safe mode.
        </Alert>
      ) : null}

      <div className="flex items-center gap-3 text-sm">
        <span
          className={
            currentStatus?.enabled
              ? "inline-flex rounded-full bg-amber-100 px-3 py-1 font-semibold text-amber-800"
              : "inline-flex rounded-full bg-emerald-100 px-3 py-1 font-semibold text-emerald-800"
          }
        >
          {currentStatus?.enabled ? "Safe mode enabled" : "Safe mode disabled"}
        </span>
        <span className="text-slate-500">
          {safeModeStatus.isFetching
            ? "Checking safe mode state..."
            : currentStatus?.detail ?? DEFAULT_SAFE_MODE_MESSAGE}
        </span>
      </div>

      <FormField
        label="Safe mode message"
        hint="Shown in the health check and workspace banner when safe mode is active."
      >
        <TextArea
          value={detail}
          onChange={(event) => setDetail(event.target.value)}
          disabled={!canManageSafeMode || isPending}
        />
      </FormField>

      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          variant="secondary"
          onClick={() => setDetail(currentStatus?.detail ?? DEFAULT_SAFE_MODE_MESSAGE)}
          disabled={!canManageSafeMode || isPending}
        >
          Reset message
        </Button>
        <Button
          type="button"
          variant={currentStatus?.enabled ? "primary" : "danger"}
          onClick={() => handleToggle(!currentStatus?.enabled)}
          isLoading={updateSafeMode.isPending}
          disabled={!canManageSafeMode}
        >
          {currentStatus?.enabled ? "Disable safe mode" : "Enable safe mode"}
        </Button>
      </div>
    </div>
  );
}

SafeModeControls.displayName = "SafeModeControls";
```

# apps/ade-web/src/screens/Workspace/sections/Settings/components/WorkspaceMembersSection.tsx
```tsx
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useUsersQuery } from "@shared/users/hooks/useUsersQuery";
import { useInviteUserMutation } from "@shared/users/hooks/useInviteUserMutation";
import {
  useAddWorkspaceMemberMutation,
  useRemoveWorkspaceMemberMutation,
  useUpdateWorkspaceMemberRolesMutation,
  useWorkspaceMembersQuery,
} from "../hooks/useWorkspaceMembers";
import { useWorkspaceRolesQuery } from "../hooks/useWorkspaceRoles";
import type { WorkspaceMember, RoleDefinition } from "@screens/Workspace/api/workspaces-api";
import type { UserSummary } from "@shared/users/api";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { Select } from "@ui/Select";
import { Avatar } from "@ui/Avatar";

export function WorkspaceMembersSection() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const canManageMembers = hasPermission("Workspace.Members.ReadWrite");
  const membersQuery = useWorkspaceMembersQuery(workspace.id);
  const rolesQuery = useWorkspaceRolesQuery(workspace.id);

  const addMember = useAddWorkspaceMemberMutation(workspace.id);
  const updateMemberRoles = useUpdateWorkspaceMemberRolesMutation(workspace.id);
  const removeMember = useRemoveWorkspaceMemberMutation(workspace.id);
  const inviteUserMutation = useInviteUserMutation();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [roleDraft, setRoleDraft] = useState<string[]>([]);
  const [inviteUserId, setInviteUserId] = useState<string>("");
  const [inviteRoleIds, setInviteRoleIds] = useState<string[]>([]);
  const [inviteSearch, setInviteSearch] = useState<string>("");
  const [debouncedInviteSearch, setDebouncedInviteSearch] = useState<string>("");
  const [inviteOption, setInviteOption] = useState<"existing" | "new">("existing");
  const [inviteEmail, setInviteEmail] = useState<string>("");
  const [inviteDisplayName, setInviteDisplayName] = useState<string>("");
  const [memberSearch, setMemberSearch] = useState<string>("");
  const [feedbackMessage, setFeedbackMessage] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedInviteSearch(inviteSearch.trim());
    }, 250);
    return () => window.clearTimeout(handle);
  }, [inviteSearch]);

  const usersQuery = useUsersQuery({
    enabled: canManageMembers,
    search: debouncedInviteSearch,
    pageSize: 50,
  });

  const roleLookup = useMemo(() => {
    const map = new Map<string, RoleDefinition>();
    for (const role of rolesQuery.data?.items ?? []) {
      map.set(role.id, role);
    }
    return map;
  }, [rolesQuery.data]);

  const members = useMemo(() => {
    const list = membersQuery.data?.items ?? [];
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return Array.from(list).sort((a, b) => {
      const nameA = a.user.display_name ?? a.user.email;
      const nameB = b.user.display_name ?? b.user.email;
      return collator.compare(nameA ?? "", nameB ?? "");
    });
  }, [membersQuery.data]);
  const memberIds = useMemo(() => new Set(members.map((member) => member.user.id)), [members]);

  const normalizedMemberSearch = memberSearch.trim().toLowerCase();
  const filteredMembers = useMemo(() => {
    if (!normalizedMemberSearch) {
      return members;
    }
    return members.filter((member) => {
      const name = member.user.display_name ?? "";
      const email = member.user.email ?? "";
      return (
        name.toLowerCase().includes(normalizedMemberSearch) ||
        email.toLowerCase().includes(normalizedMemberSearch) ||
        member.id.toLowerCase().includes(normalizedMemberSearch)
      );
    });
  }, [members, normalizedMemberSearch]);

  const usersLoading = usersQuery.isPending && usersQuery.users.length === 0;
  const usersFetchingMore = usersQuery.isFetchingNextPage;

  const availableUsers: UserSummary[] = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return usersQuery.users
      .filter((user) => !memberIds.has(user.id))
      .sort((a, b) => {
        const nameA = a.display_name ?? a.email;
        const nameB = b.display_name ?? b.email;
        return collator.compare(nameA ?? "", nameB ?? "");
      });
  }, [memberIds, usersQuery.users]);

  const normalizedInviteSearch = inviteSearch.trim().toLowerCase();
  const serverInviteSearch = debouncedInviteSearch.trim().toLowerCase();
  const usingServerSearch = serverInviteSearch.length >= 2;
  const inviteSearchTooShort = inviteOption === "existing" && inviteSearch.trim().length > 0 && inviteSearch.trim().length < 2;
  const filteredAvailableUsers = useMemo(() => {
    if (!normalizedInviteSearch || usingServerSearch) {
      return availableUsers;
    }
    return availableUsers.filter((user) => {
      const name = user.display_name ?? "";
      return (
        name.toLowerCase().includes(normalizedInviteSearch) ||
        user.email.toLowerCase().includes(normalizedInviteSearch)
      );
    });
  }, [availableUsers, normalizedInviteSearch, usingServerSearch]);

  const selectedInviteUser = useMemo(
    () =>
      inviteOption === "existing"
        ? availableUsers.find((user) => user.id === inviteUserId)
        : undefined,
    [availableUsers, inviteOption, inviteUserId],
  );

  const availableRoles = useMemo(() => {
    const collator = new Intl.Collator("en", { sensitivity: "base" });
    return (rolesQuery.data?.items ?? [])
      .filter((role) => role.scope_type === "workspace")
      .sort((a, b) => collator.compare(a.name, b.name));
  }, [rolesQuery.data]);

  const handleToggleRoleDraft = (roleId: string, selected: boolean) => {
    setRoleDraft((current) => {
      if (selected) {
        return current.includes(roleId) ? current : [...current, roleId];
      }
      return current.filter((id) => id !== roleId);
    });
  };

  const handleToggleInviteRole = (roleId: string, selected: boolean) => {
    setInviteRoleIds((current) => {
      if (selected) {
        return current.includes(roleId) ? current : [...current, roleId];
      }
      return current.filter((id) => id !== roleId);
    });
  };

  const startEdit = (member: WorkspaceMember) => {
    setEditingId(member.id);
    setRoleDraft(member.roles);
    setFeedbackMessage(null);
  };

  const resetEditState = () => {
    setEditingId(null);
    setRoleDraft([]);
  };

  const handleUpdateRoles = () => {
    if (!editingId) {
      return;
    }
    setFeedbackMessage(null);
    updateMemberRoles.mutate(
      { membershipId: editingId, roleIds: roleDraft },
      {
        onSuccess: () => {
          setFeedbackMessage({ tone: "success", message: "Member roles updated." });
          resetEditState();
        },
        onError: (error) => {
          const message =
            error instanceof Error ? error.message : "Unable to update member roles.";
          setFeedbackMessage({ tone: "danger", message });
        },
      },
    );
  };

  const handleRemoveMember = (member: WorkspaceMember) => {
    if (!canManageMembers) {
      return;
    }
    const confirmed = window.confirm(`Remove ${member.user.display_name ?? member.user.email} from the workspace?`);
    if (!confirmed) {
      return;
    }
    setFeedbackMessage(null);
    removeMember.mutate(member.id, {
      onSuccess: () => {
        setFeedbackMessage({ tone: "success", message: "Member removed." });
      },
      onError: (error) => {
        const message =
          error instanceof Error ? error.message : "Unable to remove member.";
        setFeedbackMessage({ tone: "danger", message });
      },
    });
  };

  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const isInvitePending = addMember.isPending || inviteUserMutation.isPending;
  const canSubmitInvite =
    inviteOption === "existing"
      ? Boolean(inviteUserId)
      : emailPattern.test(inviteEmail.trim());

  const handleInvite = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedbackMessage(null);
    try {
      if (inviteOption === "existing") {
        if (!inviteUserId) {
          setFeedbackMessage({ tone: "danger", message: "Select a user to invite." });
          return;
        }
        const user = availableUsers.find((candidate) => candidate.id === inviteUserId);
        if (!user) {
          setFeedbackMessage({ tone: "danger", message: "Selected user is no longer available." });
          return;
        }
        await addMember.mutateAsync({ user, roleIds: inviteRoleIds });
        setInviteUserId("");
        setInviteRoleIds([]);
        setInviteSearch("");
        setFeedbackMessage({
          tone: "success",
          message: `${user.display_name ?? user.email} added to the workspace.`,
        });
        return;
      }

      const normalizedEmail = inviteEmail.trim().toLowerCase();
      if (!normalizedEmail || !emailPattern.test(normalizedEmail)) {
        setFeedbackMessage({ tone: "danger", message: "Enter a valid email address to send an invite." });
        return;
      }

      const invitedUser = await inviteUserMutation.mutateAsync({
        email: normalizedEmail,
        displayName: inviteDisplayName.trim() || undefined,
      });

      await addMember.mutateAsync({ user: invitedUser, roleIds: inviteRoleIds });
      setInviteEmail("");
      setInviteDisplayName("");
      setInviteRoleIds([]);
      setFeedbackMessage({
        tone: "success",
        message: `Invitation sent to ${invitedUser.display_name ?? invitedUser.email}.`,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to invite member.";
      setFeedbackMessage({ tone: "danger", message });
    }
  };

  useEffect(() => {
    if (inviteOption !== "existing" || !selectedInviteUser) {
      return;
    }
    if (!filteredAvailableUsers.some((user) => user.id === selectedInviteUser.id)) {
      setInviteSearch("");
    }
  }, [filteredAvailableUsers, inviteOption, selectedInviteUser]);

  useEffect(() => {
    setFeedbackMessage(null);
    if (inviteOption === "existing") {
      setInviteEmail("");
      setInviteDisplayName("");
      return;
    }
    setInviteUserId("");
    setInviteSearch("");
  }, [inviteOption]);

  const resetInviteDraft = () => {
    if (inviteOption === "existing") {
      setInviteUserId("");
      setInviteSearch("");
    } else {
      setInviteEmail("");
      setInviteDisplayName("");
    }
    setInviteRoleIds([]);
  };

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {membersQuery.isError ? (
        <Alert tone="danger">
          {membersQuery.error instanceof Error ? membersQuery.error.message : "Unable to load workspace members."}
        </Alert>
      ) : null}
      {rolesQuery.isError ? (
        <Alert tone="warning">
          {rolesQuery.error instanceof Error ? rolesQuery.error.message : "Unable to load workspace roles."}
        </Alert>
      ) : null}

      {canManageMembers ? (
        <form
          onSubmit={handleInvite}
          className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft"
        >
          <header className="space-y-1">
            <h2 className="text-lg font-semibold text-slate-900">Invite member</h2>
            <p className="text-sm text-slate-500">
              Invite someone new by email or add an existing teammate, then choose the roles that reflect what they should be able
              to do here.
            </p>
          </header>
          {usersQuery.isError ? (
            <Alert tone="warning">
              We couldn't load the user directory. Retry or invite later.
            </Alert>
          ) : null}
          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold text-slate-700">Invite method</legend>
            <p className="text-xs text-slate-500">Choose whether you are inviting someone who already has an account or sending a brand-new invite.</p>
            <div className="flex flex-wrap gap-2">
              <label
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                  inviteOption === "existing"
                    ? "border-brand-300 bg-brand-50 text-brand-700"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                <input
                  type="radio"
                  name="invite-method"
                  value="existing"
                  checked={inviteOption === "existing"}
                  onChange={() => setInviteOption("existing")}
                  disabled={isInvitePending}
                  className="h-4 w-4"
                />
                <span>Existing teammate</span>
              </label>
              <label
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                  inviteOption === "new"
                    ? "border-brand-300 bg-brand-50 text-brand-700"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                <input
                  type="radio"
                  name="invite-method"
                  value="new"
                  checked={inviteOption === "new"}
                  onChange={() => setInviteOption("new")}
                  disabled={isInvitePending}
                  className="h-4 w-4"
                />
                <span>Invite by email</span>
              </label>
            </div>
          </fieldset>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-4">
              {inviteOption === "existing" ? (
                <>
                  <FormField
                    label="Search directory"
                    hint="Filter by name or email to quickly find a teammate."
                  >
                    <Input
                      value={inviteSearch}
                      onChange={(event) => setInviteSearch(event.target.value)}
                      placeholder="e.g. Casey or casey@example.com"
                      disabled={isInvitePending || usersLoading}
                    />
                  </FormField>
                  {inviteSearchTooShort ? (
                    <p className="text-xs text-slate-500">
                      Enter at least two characters to search the full directory.
                    </p>
                  ) : null}
                  {usersQuery.isError ? (
                    <p className="text-xs text-rose-600">Unable to load users. Try again shortly.</p>
                  ) : null}
                  <FormField label="User" required>
                    <Select
                      value={inviteUserId}
                      onChange={(event) => {
                        setInviteUserId(event.target.value);
                        if (event.target.value) {
                          setInviteSearch("");
                        }
                      }}
                      disabled={isInvitePending || usersLoading}
                      required
                    >
                      <option value="">Select a user</option>
                      {selectedInviteUser &&
                      !filteredAvailableUsers.some((user) => user.id === selectedInviteUser.id) ? (
                        <option value={selectedInviteUser.id}>
                          {selectedInviteUser.display_name
                            ? `${selectedInviteUser.display_name} (${selectedInviteUser.email})`
                            : selectedInviteUser.email}
                        </option>
                      ) : null}
                      {filteredAvailableUsers.map((user) => (
                        <option key={user.id} value={user.id}>
                          {user.display_name ? `${user.display_name} (${user.email})` : user.email}
                        </option>
                      ))}
                    </Select>
                  </FormField>
                  {filteredAvailableUsers.length === 0 && inviteSearch ? (
                    <p className="text-xs text-slate-500">
                      No users matched "{inviteSearch}". Clear the search to see everyone.
                    </p>
                  ) : null}
                  {usersQuery.hasNextPage ? (
                    <div className="pt-2">
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => usersQuery.fetchNextPage()}
                        disabled={usersLoading || usersFetchingMore}
                      >
                        {usersFetchingMore ? "Loading more users…" : "Load more users"}
                      </Button>
                    </div>
                  ) : null}
                </>
              ) : (
                <>
                  <FormField label="Email" required>
                    <Input
                      type="email"
                      value={inviteEmail}
                      onChange={(event) => setInviteEmail(event.target.value)}
                      placeholder="name@example.com"
                      autoComplete="off"
                      disabled={isInvitePending}
                      required
                    />
                  </FormField>
                  <FormField
                    label="Display name"
                    hint="Optional – helps teammates recognise them."
                  >
                    <Input
                      value={inviteDisplayName}
                      onChange={(event) => setInviteDisplayName(event.target.value)}
                      placeholder="Casey Lee"
                      autoComplete="off"
                      disabled={isInvitePending}
                    />
                  </FormField>
                  <p className="text-xs text-slate-500">
                    We'll email an invitation so they can create their account and join this workspace.
                  </p>
                </>
              )}
            </div>

            <fieldset className="space-y-3">
              <legend className="text-sm font-semibold text-slate-700">Roles</legend>
              <p className="text-xs text-slate-500">
                Roles control which actions a member can perform inside this workspace.
              </p>
              <div className="flex flex-wrap gap-2">
                {availableRoles.length === 0 ? (
                  <p className="text-xs text-slate-500">No workspace roles available yet.</p>
                ) : (
                  availableRoles.map((role) => (
                    <label
                      key={role.id}
                      className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300"
                        checked={inviteRoleIds.includes(role.id)}
                        onChange={(event) => handleToggleInviteRole(role.id, event.target.checked)}
                        disabled={isInvitePending}
                      />
                      <span>{role.name}</span>
                    </label>
                  ))
                )}
              </div>
              {inviteRoleIds.length > 0 ? (
                <p className="text-xs text-slate-500">{inviteRoleIds.length} role(s) selected.</p>
              ) : null}
            </fieldset>
          </div>

          <div className="flex justify-end gap-2">
            {(inviteOption === "existing"
            ? inviteUserId || inviteSearch || inviteRoleIds.length > 0
            : inviteEmail || inviteDisplayName || inviteRoleIds.length > 0) ? (
              <Button type="button" variant="ghost" onClick={resetInviteDraft} disabled={isInvitePending}>
                Clear
              </Button>
            ) : null}
            <Button type="submit" isLoading={isInvitePending} disabled={!canSubmitInvite || isInvitePending}>
              {inviteOption === "existing" ? "Add member" : "Send invite"}
            </Button>
          </div>
        </form>
      ) : (
        <Alert tone="info">
          You do not have permission to manage workspace members. Contact an administrator for access.
        </Alert>
      )}

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Current members</h2>
            <p className="text-sm text-slate-500">
              {membersQuery.isLoading
                ? "Loading members…"
                : `${members.length} member${members.length === 1 ? "" : "s"}`}
            </p>
          </div>
          <FormField label="Search members" className="w-full max-w-xs">
            <Input
              value={memberSearch}
              onChange={(event) => setMemberSearch(event.target.value)}
              placeholder="Search by name, email, or ID"
              disabled={membersQuery.isLoading}
            />
          </FormField>
        </header>

        {membersQuery.isLoading ? (
          <p className="text-sm text-slate-600">Loading members…</p>
        ) : members.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            No members yet. Invite teammates to collaborate on this workspace.
          </p>
        ) : filteredMembers.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            No members match "{memberSearch}".
          </p>
        ) : (
          <ul className="space-y-4" role="list">
            {filteredMembers.map((member) => {
              const userLabel = member.user.display_name ?? member.user.email;
              const roleChips = member.roles.map((roleId) => roleLookup.get(roleId)?.name ?? roleId);
              const isEditing = editingId === member.id;
              return (
                <li
                  key={member.id}
                  className="rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <Avatar name={member.user.display_name} email={member.user.email} size="sm" />
                      <div className="space-y-1">
                        <p className="text-base font-semibold text-slate-900">{userLabel}</p>
                        <p className="text-sm text-slate-500">{member.user.email}</p>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                          {member.is_default ? (
                            <span className="inline-flex items-center rounded-full bg-brand-100 px-2 py-0.5 font-semibold text-brand-700">
                              Default workspace
                            </span>
                          ) : null}
                          <span>ID: {member.id}</span>
                        </div>
                      </div>
                    </div>
                    {canManageMembers ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => (isEditing ? resetEditState() : startEdit(member))}
                          disabled={
                            updateMemberRoles.isPending ||
                            removeMember.isPending ||
                            (isEditing && updateMemberRoles.isPending)
                          }
                        >
                          {isEditing ? "Cancel" : "Manage roles"}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveMember(member)}
                          disabled={removeMember.isPending}
                        >
                          Remove
                        </Button>
                      </div>
                    ) : null}
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {roleChips.length > 0 ? (
                      roleChips.map((roleName) => (
                        <span
                          key={`${member.id}-${roleName}`}
                          className="inline-flex items-center rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm"
                        >
                          {roleName}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-500">No roles assigned.</span>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="mt-4 space-y-3 rounded-lg border border-slate-200 bg-white p-4">
                      <p className="text-sm font-semibold text-slate-700">Assign roles</p>
                      <div className="flex flex-wrap gap-2">
                        {availableRoles.map((role) => (
                          <label
                            key={role.id}
                            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                          >
                            <input
                              type="checkbox"
                              className="h-4 w-4 rounded border-slate-300"
                              checked={roleDraft.includes(role.id)}
                              onChange={(event) => handleToggleRoleDraft(role.id, event.target.checked)}
                              disabled={updateMemberRoles.isPending}
                            />
                            <span>{role.name}</span>
                          </label>
                        ))}
                      </div>
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={resetEditState}
                          disabled={updateMemberRoles.isPending}
                        >
                          Cancel
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={handleUpdateRoles}
                          isLoading={updateMemberRoles.isPending}
                          disabled={updateMemberRoles.isPending}
                        >
                          Save roles
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/Settings/components/WorkspaceRolesSection.tsx
```tsx
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import {
  useCreateWorkspaceRoleMutation,
  useDeleteWorkspaceRoleMutation,
  usePermissionsQuery,
  useUpdateWorkspaceRoleMutation,
  useWorkspaceRolesQuery,
} from "../hooks/useWorkspaceRoles";
import type { RoleDefinition, PermissionDefinition } from "@screens/Workspace/api/workspaces-api";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { Input } from "@ui/Input";

const roleFormSchema = z.object({
  name: z.string().min(1, "Role name is required.").max(150, "Keep the name under 150 characters."),
  slug: z
    .string()
    .max(100, "Keep the slug under 100 characters.")
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Use lowercase letters, numbers, and dashes.")
    .optional()
    .or(z.literal("")),
  description: z.string().max(500, "Keep the description concise.").optional().or(z.literal("")),
  permissions: z.array(z.string()),
});

type RoleFormValues = z.infer<typeof roleFormSchema>;

export function WorkspaceRolesSection() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const canManageRoles = hasPermission("Workspace.Roles.ReadWrite");

  const rolesQuery = useWorkspaceRolesQuery(workspace.id);
  const permissionsQuery = usePermissionsQuery();

  const createRole = useCreateWorkspaceRoleMutation(workspace.id);
  const updateRole = useUpdateWorkspaceRoleMutation(workspace.id);
  const deleteRole = useDeleteWorkspaceRoleMutation(workspace.id);

  const [showCreate, setShowCreate] = useState(false);
  const [editingRoleId, setEditingRoleId] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  const permissions = useMemo(() => {
    return (permissionsQuery.data?.items ?? []).filter((permission) => permission.scope_type === "workspace");
  }, [permissionsQuery.data]);

  const permissionLookup = useMemo(() => {
    const map = new Map<string, PermissionDefinition>();
    for (const permission of permissions) {
      map.set(permission.key, permission);
    }
    return map;
  }, [permissions]);

  const roles = rolesQuery.data?.items ?? [];

  const openCreateForm = () => {
    setFeedbackMessage(null);
    setShowCreate(true);
    setEditingRoleId(null);
  };

  const closeCreateForm = () => {
    setShowCreate(false);
  };

  const startEditingRole = (role: RoleDefinition) => {
    setFeedbackMessage(null);
    setEditingRoleId(role.id);
    setShowCreate(false);
  };

  const cancelEditing = () => {
    setEditingRoleId(null);
  };

  const handleDeleteRole = (role: RoleDefinition) => {
    if (!canManageRoles || role.built_in) {
      return;
    }
    const confirmed = window.confirm(`Delete the role "${role.name}"? This action cannot be undone.`);
    if (!confirmed) {
      return;
    }
    setFeedbackMessage(null);
    deleteRole.mutate(role.id, {
      onSuccess: () => {
        setFeedbackMessage({ tone: "success", message: "Role deleted." });
      },
      onError: (error) => {
        const message = error instanceof Error ? error.message : "Unable to delete role.";
        setFeedbackMessage({ tone: "danger", message });
      },
    });
  };

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {rolesQuery.isError ? (
        <Alert tone="danger">
          {rolesQuery.error instanceof Error ? rolesQuery.error.message : "Unable to load workspace roles."}
        </Alert>
      ) : null}
      {permissionsQuery.isError ? (
        <Alert tone="warning">
          {permissionsQuery.error instanceof Error ? permissionsQuery.error.message : "Unable to load permission catalog."}
        </Alert>
      ) : null}

      {canManageRoles ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Create role</h2>
              <p className="text-sm text-slate-500">Compose a custom role by selecting workspace permissions.</p>
            </div>
            <Button
              type="button"
              variant={showCreate ? "ghost" : "primary"}
              onClick={() => (showCreate ? closeCreateForm() : openCreateForm())}
            >
              {showCreate ? "Hide form" : "New role"}
            </Button>
          </div>

          {showCreate ? (
            <div className="mt-4">
              <WorkspaceRoleForm
                key="create-role"
                availablePermissions={permissions}
                allowSlugEdit
                onCancel={closeCreateForm}
                onSubmit={(values) => {
                  setFeedbackMessage(null);
                  createRole.mutate(
                    {
                      name: values.name.trim(),
                      slug: values.slug ? values.slug.trim() : undefined,
                      description: values.description?.trim() ? values.description.trim() : undefined,
                      permissions: values.permissions,
                    },
                    {
                      onSuccess: () => {
                        setFeedbackMessage({ tone: "success", message: "Role created." });
                        closeCreateForm();
                      },
                      onError: (error) => {
                        const message = error instanceof Error ? error.message : "Unable to create role.";
                        setFeedbackMessage({ tone: "danger", message });
                      },
                    },
                  );
                }}
                isSubmitting={createRole.isPending}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Workspace roles</h2>
            <p className="text-sm text-slate-500">
              {rolesQuery.isLoading ? "Loading roles…" : `${roles.length} role${roles.length === 1 ? "" : "s"}`}
            </p>
          </div>
        </header>

        {rolesQuery.isLoading ? (
          <p className="text-sm text-slate-600">Loading roles…</p>
        ) : roles.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            No workspace roles yet. Create one to tailor permissions for your team.
          </p>
        ) : (
          <ul className="space-y-4" role="list">
            {roles.map((role) => {
              const isEditing = editingRoleId === role.id;
              const permissionLabels = role.permissions.map(
                (permission) => permissionLookup.get(permission)?.label ?? permission,
              );
              return (
                <li key={role.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-semibold text-slate-900">{role.name}</h3>
                        {role.built_in ? (
                          <span className="inline-flex items-center rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
                            Built-in
                          </span>
                        ) : null}
                        {!role.editable ? (
                          <span className="inline-flex items-center rounded-full bg-warning-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-warning-700">
                            Locked
                          </span>
                        ) : null}
                      </div>
                      <p className="text-sm text-slate-500">Slug: {role.slug}</p>
                      {role.description ? (
                        <p className="text-sm text-slate-600">{role.description}</p>
                      ) : null}
                    </div>
                    {canManageRoles && role.editable ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => (isEditing ? cancelEditing() : startEditingRole(role))}
                          disabled={updateRole.isPending || deleteRole.isPending}
                        >
                          {isEditing ? "Cancel" : "Edit"}
                        </Button>
                        {!role.built_in ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteRole(role)}
                            disabled={deleteRole.isPending}
                          >
                            Delete
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {permissionLabels.length > 0 ? (
                      permissionLabels.map((label) => (
                        <span
                          key={`${role.id}-${label}`}
                          className="inline-flex items-center rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm"
                        >
                          {label}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-500">No permissions assigned.</span>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="mt-4">
                      <WorkspaceRoleForm
                        key={role.id}
                        availablePermissions={permissions}
                        initialValues={{
                          name: role.name,
                          slug: role.slug,
                          description: role.description ?? "",
                          permissions: role.permissions,
                        }}
                        allowSlugEdit={false}
                        onCancel={cancelEditing}
                        onSubmit={(values) => {
                          setFeedbackMessage(null);
                          updateRole.mutate(
                            {
                              roleId: role.id,
                              payload: {
                                name: values.name.trim(),
                                description: values.description?.trim() ? values.description.trim() : undefined,
                                permissions: values.permissions,
                              },
                            },
                            {
                              onSuccess: () => {
                                setFeedbackMessage({ tone: "success", message: "Role updated." });
                                cancelEditing();
                              },
                              onError: (error) => {
                                const message =
                                  error instanceof Error ? error.message : "Unable to update role.";
                                setFeedbackMessage({ tone: "danger", message });
                              },
                            },
                          );
                        }}
                        isSubmitting={updateRole.isPending}
                      />
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}


interface WorkspaceRoleFormProps {
  readonly availablePermissions: readonly PermissionDefinition[];
  readonly initialValues?: RoleFormValues;
  readonly onSubmit: (values: RoleFormValues) => void;
  readonly onCancel?: () => void;
  readonly isSubmitting: boolean;
  readonly allowSlugEdit?: boolean;
}

function WorkspaceRoleForm({
  availablePermissions,
  initialValues,
  onSubmit,
  onCancel,
  isSubmitting,
  allowSlugEdit = true,
}: WorkspaceRoleFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
    reset,
  } = useForm<RoleFormValues, undefined, RoleFormValues>({
    resolver: zodResolver(roleFormSchema),
    defaultValues: initialValues ?? {
      name: "",
      slug: "",
      description: "",
      permissions: [],
    },
  });

  useEffect(() => {
    if (initialValues) {
      reset(initialValues);
    }
  }, [initialValues, reset]);

  const selectedPermissions = watch("permissions");

  const togglePermission = (permissionKey: string, selected: boolean) => {
    setValue(
      "permissions",
      selected
        ? Array.from(new Set([...(selectedPermissions ?? []), permissionKey]))
        : (selectedPermissions ?? []).filter((key) => key !== permissionKey),
    );
  };

  const submit = handleSubmit((values) => {
    const payload: RoleFormValues = {
      name: values.name.trim(),
      slug: allowSlugEdit ? values.slug?.trim() ?? "" : initialValues?.slug ?? "",
      description: values.description?.trim() ?? "",
      permissions: values.permissions ?? [],
    };
    onSubmit(payload);
  });

  return (
    <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4" onSubmit={submit} noValidate>
      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm font-medium text-slate-700">
          Role name
          <Input
            {...register("name")}
            placeholder="Data reviewer"
            invalid={Boolean(errors.name)}
            disabled={isSubmitting}
          />
          {errors.name ? (
            <span className="block text-xs font-semibold text-danger-600">{errors.name.message}</span>
          ) : null}
        </label>
        {allowSlugEdit ? (
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Role slug
            <Input
              {...register("slug")}
              placeholder="data-reviewer"
              invalid={Boolean(errors.slug)}
              disabled={isSubmitting}
            />
            <span className="block text-xs text-slate-500">Optional. Leave blank to auto-generate from the name.</span>
            {errors.slug ? (
              <span className="block text-xs font-semibold text-danger-600">{errors.slug.message}</span>
            ) : null}
          </label>
        ) : null}
      </div>

      <label className="space-y-2 text-sm font-medium text-slate-700">
        Description
        <Input
          {...register("description")}
          placeholder="What does this role control?"
          invalid={Boolean(errors.description)}
          disabled={isSubmitting}
        />
        {errors.description ? (
          <span className="block text-xs font-semibold text-danger-600">{errors.description.message}</span>
        ) : null}
      </label>

      <fieldset className="space-y-3">
        <legend className="text-sm font-semibold text-slate-700">Permissions</legend>
        <div className="flex flex-wrap gap-2">
          {availablePermissions.length === 0 ? (
            <p className="text-xs text-slate-500">No workspace permissions available.</p>
          ) : (
            availablePermissions.map((permission) => (
              <label
                key={permission.key}
                className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
              >
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300"
                  checked={selectedPermissions?.includes(permission.key) ?? false}
                  onChange={(event) => togglePermission(permission.key, event.target.checked)}
                  disabled={isSubmitting}
                />
                <span>
                  <span className="block font-semibold">{permission.label}</span>
                  <span className="block text-xs text-slate-500">{permission.description}</span>
                </span>
              </label>
            ))
          )}
        </div>
      </fieldset>

      <div className="flex justify-end gap-2">
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" isLoading={isSubmitting}>
          Save role
        </Button>
      </div>
    </form>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/Settings/index.tsx
```tsx
import { useEffect, useState } from "react";

import { useSearchParams } from "@app/nav/urlState";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useUpdateWorkspaceMutation } from "./hooks/useUpdateWorkspaceMutation";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";
import { WorkspaceMembersSection } from "./components/WorkspaceMembersSection";
import { WorkspaceRolesSection } from "./components/WorkspaceRolesSection";
import { SafeModeControls } from "./components/SafeModeControls";

export const handle = { workspaceSectionId: "settings" } as const;

const SETTINGS_VIEWS = [
  { id: "general", label: "General" },
  { id: "members", label: "Members" },
  { id: "roles", label: "Roles" },
] as const;

type SettingsViewId = typeof SETTINGS_VIEWS[number]["id"];

const SETTINGS_VIEW_IDS = new Set<SettingsViewId>(SETTINGS_VIEWS.map((view) => view.id));

const isSettingsViewId = (value: string | null): value is SettingsViewId =>
  Boolean(value && SETTINGS_VIEW_IDS.has(value as SettingsViewId));

export default function WorkspaceSettingsRoute() {
  useWorkspaceContext();
  const [searchParams, setSearchParams] = useSearchParams();

  const rawViewParam = searchParams.get("view");
  const currentView: SettingsViewId = isSettingsViewId(rawViewParam) ? rawViewParam : "general";

  useEffect(() => {
    if (rawViewParam && !isSettingsViewId(rawViewParam)) {
      const next = new URLSearchParams(searchParams);
      next.set("view", "general");
      setSearchParams(next, { replace: true });
    }
  }, [rawViewParam, searchParams, setSearchParams]);

  const handleChangeView = (viewId: string) => {
    if (!isSettingsViewId(viewId)) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.set("view", viewId);
    setSearchParams(next, { replace: true });
  };

  return (
    <TabsRoot value={currentView} onValueChange={handleChangeView}>
      <div className="space-y-6">
        <TabsList className="flex gap-2 rounded-full border border-slate-200 bg-white p-1 shadow-soft" aria-label="Workspace settings views">
          {SETTINGS_VIEWS.map((option) => {
            const isActive = option.id === currentView;
            return (
              <TabsTrigger
                key={option.id}
                value={option.id}
                className={`rounded-full px-4 py-1 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 ${
                  isActive ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {option.label}
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="general" aria-live="polite">
          {currentView === "general" ? <WorkspaceGeneralSettings /> : null}
        </TabsContent>
        <TabsContent value="members" aria-live="polite">
          {currentView === "members" ? <WorkspaceMembersSection /> : null}
        </TabsContent>
        <TabsContent value="roles" aria-live="polite">
          {currentView === "roles" ? <WorkspaceRolesSection /> : null}
        </TabsContent>
      </div>
    </TabsRoot>
  );
}

const generalSchema = z.object({
  name: z.string().min(1, "Workspace name is required.").max(255, "Keep the name under 255 characters."),
  slug: z
    .string()
    .min(1, "Workspace slug is required.")
    .max(100, "Keep the slug under 100 characters.")
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Use lowercase letters, numbers, and dashes."),
});

type GeneralSettingsFormValues = z.infer<typeof generalSchema>;

function WorkspaceGeneralSettings() {
  const { workspace } = useWorkspaceContext();
  const updateWorkspace = useUpdateWorkspaceMutation(workspace.id);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
    reset,
  } = useForm<GeneralSettingsFormValues>({
    resolver: zodResolver(generalSchema),
    defaultValues: {
      name: workspace.name,
      slug: workspace.slug,
    },
  });

  useEffect(() => {
    reset({
      name: workspace.name,
      slug: workspace.slug,
    });
  }, [reset, workspace.name, workspace.slug]);

  const onSubmit = handleSubmit((values) => {
    setSuccessMessage(null);
    updateWorkspace.mutate(
      {
        name: values.name.trim(),
        slug: values.slug.trim(),
      },
      {
        onSuccess: () => {
          setSuccessMessage("Workspace details saved.");
        },
      },
    );
  });

  return (
    <div className="space-y-6">
      <form
        className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft"
        onSubmit={onSubmit}
        noValidate
      >
        <header className="space-y-1">
          <h2 className="text-xl font-semibold text-slate-900">Workspace identity</h2>
          <p className="text-sm text-slate-500">
            Update the name and slug. Changes apply immediately across navigation and shared links.
          </p>
        </header>

        {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

        {updateWorkspace.isError ? (
          <Alert tone="danger">
            {updateWorkspace.error instanceof Error ? updateWorkspace.error.message : "Unable to save workspace details."}
          </Alert>
        ) : null}

        <div className="grid gap-6 md:grid-cols-2">
          <FormField label="Workspace name" required error={errors.name?.message}>
            <Input
              {...register("name")}
              placeholder="Finance Operations"
              invalid={Boolean(errors.name)}
              disabled={updateWorkspace.isPending}
            />
          </FormField>
          <FormField
            label="Workspace slug"
            hint="Lowercase, URL-friendly identifier."
            required
            error={errors.slug?.message}
          >
            <Input
              {...register("slug")}
              placeholder="finance-ops"
              invalid={Boolean(errors.slug)}
              disabled={updateWorkspace.isPending}
            />
          </FormField>
        </div>

        <div className="flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              reset();
              setSuccessMessage(null);
            }}
            disabled={updateWorkspace.isPending || !isDirty}
          >
            Reset
          </Button>
          <Button type="submit" isLoading={updateWorkspace.isPending} disabled={!isDirty}>
            Save changes
          </Button>
        </div>
      </form>

      <SafeModeControls />
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
      "@screens": resolveSrc("screens"),
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
      "@screens": fileURLToPath(new URL("./src/screens", import.meta.url)),
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
