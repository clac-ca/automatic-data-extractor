# Logical module layout (source -> sections below):
# - apps/ade-web/README.md
# - apps/ade-web/src/app/App.tsx
# - apps/ade-web/src/app/AppProviders.tsx
# - apps/ade-web/src/app/nav/Link.tsx
# - apps/ade-web/src/app/nav/history.tsx
# - apps/ade-web/src/app/nav/urlState.ts
# - apps/ade-web/src/main.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/defaultConfig.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/seed/stubWorkbenchData.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useEditorThemePreference.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useUnsavedChangesGuard.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchFiles.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchUrlState.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/workbenchWindowState.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/types.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/drag.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/tree.ts
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

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/defaultConfig.ts
```typescript
export type WorkbenchFileKind = "file" | "folder";

export interface WorkbenchFileNode {
  readonly id: string;
  readonly name: string;
  readonly kind: WorkbenchFileKind;
  readonly language?: string;
  readonly children?: readonly WorkbenchFileNode[];
}

export const DEFAULT_FILE_TREE: WorkbenchFileNode = {
  id: "ade_config",
  name: "ade_config",
  kind: "folder",
  children: [
    { id: "ade_config/manifest.json", name: "manifest.json", kind: "file", language: "json" },
    { id: "ade_config/config.env", name: "config.env", kind: "file", language: "dotenv" },
    {
      id: "ade_config/header.py",
      name: "header.py",
      kind: "file",
      language: "python",
    },
    {
      id: "ade_config/detectors",
      name: "detectors",
      kind: "folder",
      children: [
        {
          id: "ade_config/detectors/membership.py",
          name: "membership.py",
          kind: "file",
          language: "python",
        },
        {
          id: "ade_config/detectors/duplicates.py",
          name: "duplicates.py",
          kind: "file",
          language: "python",
        },
      ],
    },
    {
      id: "ade_config/hooks",
      name: "hooks",
      kind: "folder",
      children: [
        {
          id: "ade_config/hooks/normalize.py",
          name: "normalize.py",
          kind: "file",
          language: "python",
        },
      ],
    },
    {
      id: "ade_config/tests",
      name: "tests",
      kind: "folder",
      children: [
        {
          id: "ade_config/tests/test_membership.py",
          name: "test_membership.py",
          kind: "file",
          language: "python",
        },
      ],
    },
  ],
};

export const DEFAULT_FILE_CONTENT: Record<string, string> = {
  "ade_config/manifest.json": `{
  "name": "membership-normalization",
  "version": "0.2.0",
  "description": "Normalize membership exports into ADE schema",
  "entry": {
    "module": "ade_config.detectors.membership",
    "callable": "build_pipeline"
  }
}`,
  "ade_config/config.env": `# Environment variables required to run this configuration
ADE_ENV=development
`,
  "ade_config/header.py": `"""Shared header helpers for ADE configuration."""

from ade_engine import ConfigContext

def build_header(context: ConfigContext) -> dict[str, str]:
    """Return metadata for ADE runs."""
    return {
        "workspace": context.workspace_id,
        "generated_at": context.generated_at.isoformat(),
    }
`,
  "ade_config/detectors/membership.py": `"""Membership detector."""

def build_pipeline():
    return [
        {"step": "clean"},
        {"step": "validate"},
    ]
`,
  "ade_config/detectors/duplicates.py": `"""Duplicate row detector."""

def build_pipeline():
    return [
        {"step": "detect-duplicates"},
    ]
`,
  "ade_config/hooks/normalize.py": `def normalize(record: dict[str, str]) -> dict[str, str]:
    return {
        "first_name": record.get("First Name", "").title(),
        "last_name": record.get("Last Name", "").title(),
    }
`,
  "ade_config/tests/test_membership.py": `from ade_engine.testing import ConfigTest


def test_membership_happy_path(snapshot: ConfigTest):
    result = snapshot.run_run("membership", input_path="./fixtures/membership.csv")
    assert result.errors == []
`,
};

export function findFileNode(root: WorkbenchFileNode, id: string): WorkbenchFileNode | null {
  if (root.id === id) {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const match = findFileNode(child, id);
    if (match) {
      return match;
    }
  }
  return null;
}

export function findFirstFile(root: WorkbenchFileNode): WorkbenchFileNode | null {
  if (root.kind === "file") {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const file = findFirstFile(child);
    if (file) {
      return file;
    }
  }
  return null;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/seed/stubWorkbenchData.ts
```typescript
import type {
  WorkbenchConsoleLine,
  WorkbenchDataSeed,
  WorkbenchFileNode,
  WorkbenchValidationMessage,
} from "../types";

const tree: WorkbenchFileNode = {
  id: "ade_config",
  name: "ade_config",
  kind: "folder",
  children: [
    { id: "ade_config/manifest.json", name: "manifest.json", kind: "file", language: "json" },
    { id: "ade_config/config.env", name: "config.env", kind: "file", language: "dotenv" },
    {
      id: "ade_config/header.py",
      name: "header.py",
      kind: "file",
      language: "python",
    },
    {
      id: "ade_config/detectors",
      name: "detectors",
      kind: "folder",
      children: [
        {
          id: "ade_config/detectors/membership.py",
          name: "membership.py",
          kind: "file",
          language: "python",
        },
        {
          id: "ade_config/detectors/duplicates.py",
          name: "duplicates.py",
          kind: "file",
          language: "python",
        },
      ],
    },
    {
      id: "ade_config/hooks",
      name: "hooks",
      kind: "folder",
      children: [
        {
          id: "ade_config/hooks/normalize.py",
          name: "normalize.py",
          kind: "file",
          language: "python",
        },
      ],
    },
    {
      id: "ade_config/tests",
      name: "tests",
      kind: "folder",
      children: [
        {
          id: "ade_config/tests/test_membership.py",
          name: "test_membership.py",
          kind: "file",
          language: "python",
        },
      ],
    },
  ],
};

const content: Record<string, string> = {
  "ade_config/manifest.json": `{
  "name": "membership-normalization",
  "version": "0.2.0",
  "description": "Normalize membership exports into ADE schema",
  "entry": {
    "module": "ade_config.detectors.membership",
    "callable": "build_pipeline"
  }
}`,
  "ade_config/config.env": `# Environment variables required to run this configuration
ADE_ENV=development
`,
  "ade_config/header.py": `"""Shared header helpers for ADE configuration."""

from ade_engine import ConfigContext

def build_header(context: ConfigContext) -> dict[str, str]:
    """Return metadata for ADE runs."""
    return {
        "workspace": context.workspace_id,
        "generated_at": context.generated_at.isoformat(),
    }
`,
  "ade_config/detectors/membership.py": `"""Membership detector."""

def build_pipeline():
    return [
        {"step": "clean"},
        {"step": "validate"},
    ]
`,
  "ade_config/detectors/duplicates.py": `"""Duplicate row detector."""

def build_pipeline():
    return [
        {"step": "detect-duplicates"},
    ]
`,
  "ade_config/hooks/normalize.py": `def normalize(record: dict[str, str]) -> dict[str, str]:
    return {
        "first_name": record.get("First Name", "").title(),
        "last_name": record.get("Last Name", "").title(),
    }
`,
  "ade_config/tests/test_membership.py": `from ade_engine.testing import ConfigTest


def test_membership_happy_path(snapshot: ConfigTest):
    result = snapshot.run_run("membership", input_path="./fixtures/membership.csv")
    assert result.errors == []
`,
};

const console: WorkbenchConsoleLine[] = [
  {
    level: "info",
    message: "Config workbench ready. Open a file to begin editing.",
    timestamp: "12:00:01",
  },
  {
    level: "success",
    message: "Loaded local ADE runtime stub.",
    timestamp: "12:00:02",
  },
];

const validation: WorkbenchValidationMessage[] = [
  {
    level: "warning",
    message: "Manifest description is short. Consider elaborating on the configuration purpose.",
  },
  {
    level: "info",
    message: "Detector membership.py compiled successfully.",
  },
];

export function createStubWorkbenchData(): WorkbenchDataSeed {
  return {
    tree,
    content,
    console,
    validation,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useEditorThemePreference.ts
```typescript
import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "@shared/storage";

export type EditorThemePreference = "system" | "light" | "dark";
export type EditorThemeId = "ade-dark" | "vs-light";

const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

function coercePreference(value: unknown): EditorThemePreference {
  if (value === "light" || value === "dark" || value === "system") {
    return value;
  }
  return "system";
}

function resolveTheme(preference: EditorThemePreference, systemPrefersDark: boolean): EditorThemeId {
  return preference === "dark" || (preference === "system" && systemPrefersDark) ? "ade-dark" : "vs-light";
}

export function useEditorThemePreference(storageKey: string) {
  const storage = useMemo(() => createScopedStorage(storageKey), [storageKey]);

  const [preference, setPreferenceState] = useState<EditorThemePreference>(() => {
    const stored = storage.get<EditorThemePreference>();
    return coercePreference(stored);
  });

  const [systemPrefersDark, setSystemPrefersDark] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.matchMedia(DARK_MODE_QUERY).matches;
  });

  useEffect(() => {
    const next = coercePreference(storage.get<EditorThemePreference>());
    setPreferenceState((current) => (current === next ? current : next));
  }, [storage]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const media = window.matchMedia(DARK_MODE_QUERY);
    const handleChange = (event: MediaQueryListEvent) => {
      setSystemPrefersDark(event.matches);
    };

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", handleChange);
    } else if (typeof media.addListener === "function") {
      media.addListener(handleChange);
    }

    setSystemPrefersDark(media.matches);

    return () => {
      if (typeof media.removeEventListener === "function") {
        media.removeEventListener("change", handleChange);
      } else if (typeof media.removeListener === "function") {
        media.removeListener(handleChange);
      }
    };
  }, []);

  useEffect(() => {
    storage.set(preference);
  }, [preference, storage]);

  const resolvedTheme = useMemo(() => resolveTheme(preference, systemPrefersDark), [preference, systemPrefersDark]);

  const setPreference = useCallback((next: EditorThemePreference) => {
    setPreferenceState(next);
  }, []);

  return {
    preference,
    resolvedTheme,
    setPreference,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useUnsavedChangesGuard.ts
```typescript
import { useCallback, useEffect } from "react";

import { useLocation, useNavigationBlocker } from "@app/nav/history";

const DEFAULT_PROMPT = "You have unsaved changes in the config editor. Are you sure you want to leave?";

type ConfirmFn = (message: string) => boolean;

interface UseUnsavedChangesGuardOptions {
  readonly isDirty: boolean;
  readonly confirm?: ConfirmFn;
  readonly message?: string;
  readonly shouldBypassNavigation?: () => boolean;
}

export function useUnsavedChangesGuard({
  isDirty,
  confirm = window.confirm,
  message = DEFAULT_PROMPT,
  shouldBypassNavigation,
}: UseUnsavedChangesGuardOptions) {
  const location = useLocation();

  const blocker = useCallback<Parameters<typeof useNavigationBlocker>[0]>(
    (intent) => {
      if (!isDirty) {
        return true;
      }

      if (shouldBypassNavigation?.()) {
        return true;
      }

      if (intent.location.pathname === location.pathname) {
        return true;
      }

      return confirm(message);
    },
    [confirm, isDirty, location.pathname, message, shouldBypassNavigation],
  );

  useNavigationBlocker(blocker, isDirty);

  useEffect(() => {
    if (!isDirty) {
      return;
    }

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
      return message;
    };

    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [isDirty, message]);
}

export { DEFAULT_PROMPT as UNSAVED_CHANGES_PROMPT };
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchFiles.ts
```typescript
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { WorkbenchFileMetadata, WorkbenchFileNode, WorkbenchFileTab } from "../types";
import { findFileNode, findFirstFile } from "../utils/tree";

interface WorkbenchFilesPersistence {
  readonly get: <T>() => T | null;
  readonly set: <T>(value: T) => void;
  readonly clear: () => void;
}

interface PersistedWorkbenchTabEntry {
  readonly id: string;
  readonly pinned?: boolean;
}

interface PersistedWorkbenchTabs {
  readonly openTabs: readonly (string | PersistedWorkbenchTabEntry)[];
  readonly activeTabId?: string | null;
  readonly mru?: readonly string[];
}

interface UseWorkbenchFilesOptions {
  readonly tree: WorkbenchFileNode | null;
  readonly initialActiveFileId?: string;
  readonly loadFile: (fileId: string) => Promise<{ content: string; etag?: string | null }>;
  readonly persistence?: WorkbenchFilesPersistence | null;
}

type WorkbenchTabZone = "pinned" | "regular";

interface MoveTabOptions {
  readonly zone?: WorkbenchTabZone;
}

interface WorkbenchFilesApi {
  readonly tree: WorkbenchFileNode | null;
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly activeTab: WorkbenchFileTab | null;
  readonly openFile: (fileId: string) => void;
  readonly selectTab: (fileId: string) => void;
  readonly closeTab: (fileId: string) => void;
  readonly closeOtherTabs: (fileId: string) => void;
  readonly closeTabsToRight: (fileId: string) => void;
  readonly closeAllTabs: () => void;
  readonly moveTab: (fileId: string, targetIndex: number, options?: MoveTabOptions) => void;
  readonly pinTab: (fileId: string) => void;
  readonly unpinTab: (fileId: string) => void;
  readonly toggleTabPin: (fileId: string, pinned: boolean) => void;
  readonly selectRecentTab: (direction: "forward" | "backward") => void;
  readonly updateContent: (fileId: string, content: string) => void;
  readonly beginSavingTab: (fileId: string) => void;
  readonly completeSavingTab: (
    fileId: string,
    options?: { metadata?: WorkbenchFileMetadata; etag?: string | null },
  ) => void;
  readonly failSavingTab: (fileId: string, message: string) => void;
  readonly replaceTabContent: (
    fileId: string,
    payload: { content: string; metadata?: WorkbenchFileMetadata; etag?: string | null },
  ) => void;
  readonly isDirty: boolean;
}

export function useWorkbenchFiles({
  tree,
  initialActiveFileId,
  loadFile,
  persistence,
}: UseWorkbenchFilesOptions): WorkbenchFilesApi {
  const [tabs, setTabs] = useState<WorkbenchFileTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string>("");
  const [recentOrder, setRecentOrder] = useState<string[]>([]);
  const [hasHydratedPersistence, setHasHydratedPersistence] = useState(() => !persistence);
  const [hasOpenedInitialTab, setHasOpenedInitialTab] = useState(false);
  const pendingLoadsRef = useRef<Set<string>>(new Set());
  const tabsRef = useRef<WorkbenchFileTab[]>([]);
  const activeTabIdRef = useRef<string>("");
  const recentOrderRef = useRef<string[]>([]);

  const setActiveTab = useCallback((nextActiveId: string) => {
    setActiveTabId((prev) => (prev === nextActiveId ? prev : nextActiveId));
    setRecentOrder((current) => {
      const sanitized = current.filter((id) => tabsRef.current.some((tab) => tab.id === id));
      if (!nextActiveId) {
        return sanitized;
      }
      const withoutNext = sanitized.filter((id) => id !== nextActiveId);
      return [nextActiveId, ...withoutNext];
    });
  }, []);

  useEffect(() => {
    activeTabIdRef.current = activeTabId;
  }, [activeTabId]);

  useEffect(() => {
    recentOrderRef.current = recentOrder;
  }, [recentOrder]);

  useEffect(() => {
    if (!tree) {
      setTabs([]);
      setActiveTabId("");
      setRecentOrder([]);
      return;
    }
    setTabs((current) =>
      current
        .filter((tab) => Boolean(findFileNode(tree, tab.id)))
        .map((tab) => {
          const node = findFileNode(tree, tab.id);
          if (!node || node.kind !== "file") {
            return tab;
          }
          return {
            ...tab,
            name: node.name,
            language: node.language,
            metadata: node.metadata,
          };
        }),
    );
    const prevActive = activeTabIdRef.current;
    if (!prevActive || !findFileNode(tree, prevActive)) {
      setActiveTab("");
    }
  }, [tree, setActiveTab]);

  const activeTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0] ?? null,
    [activeTabId, tabs],
  );

  const loadIntoTab = useCallback(
    async (fileId: string) => {
      if (!tabsRef.current.some((tab) => tab.id === fileId)) {
        return;
      }
      let alreadyReady = false;
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          if (tab.status === "ready") {
            alreadyReady = true;
            return tab;
          }
          return { ...tab, status: "loading", error: null };
        }),
      );

      if (alreadyReady) {
        return;
      }

      try {
        const payload = await loadFile(fileId);
        setTabs((current) =>
          current.map((tab) =>
            tab.id === fileId
              ? {
                  ...tab,
                  initialContent: payload.content,
                  content: payload.content,
                  status: "ready",
                  error: null,
                  etag: payload.etag ?? null,
                  saving: false,
                  saveError: null,
                }
              : tab,
          ),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to load file.";
        setTabs((current) =>
          current.map((tab) => (tab.id === fileId ? { ...tab, status: "error", error: message } : tab)),
        );
      }
    },
    [loadFile],
  );

  const ensureFileOpen = useCallback(
    (fileId: string, options?: { activate?: boolean }) => {
      if (!tree) {
        return;
      }
      const node = findFileNode(tree, fileId);
      if (!node || node.kind !== "file") {
        return;
      }
      setTabs((current) => {
        if (current.some((tab) => tab.id === fileId)) {
          return current;
        }
        const nextTab: WorkbenchFileTab = {
          id: node.id,
          name: node.name,
          language: node.language,
          initialContent: "",
          content: "",
          status: "loading",
          error: null,
          etag: null,
          metadata: node.metadata,
          pinned: false,
          saving: false,
          saveError: null,
          lastSavedAt: null,
        };
        return [...current, nextTab];
      });
      if (options?.activate ?? true) {
        setActiveTab(fileId);
      }
    },
    [tree, setActiveTab],
  );

  useEffect(() => {
    if (hasHydratedPersistence || !persistence || !tree) {
      if (!persistence) {
        setHasHydratedPersistence(true);
      }
      return;
    }

    const snapshot = persistence.get<PersistedWorkbenchTabs>();
    const candidateEntries = snapshot?.openTabs ?? [];
    const normalizedEntries = candidateEntries
      .map((entry) => (typeof entry === "string" ? { id: entry, pinned: false } : entry))
      .filter((entry): entry is PersistedWorkbenchTabEntry => Boolean(entry && entry.id));

    if (normalizedEntries.length > 0) {
      const nextTabs: WorkbenchFileTab[] = [];

      for (const entry of normalizedEntries) {
        const node = findFileNode(tree, entry.id);
        if (!node || node.kind !== "file") {
          continue;
        }
        nextTabs.push({
          id: node.id,
          name: node.name,
          language: node.language,
          initialContent: "",
          content: "",
          status: "loading",
          error: null,
          etag: null,
          metadata: node.metadata,
          pinned: Boolean(entry.pinned),
          saving: false,
          saveError: null,
          lastSavedAt: null,
        });
      }

      if (nextTabs.length > 0) {
        setTabs(nextTabs);
        const preferredActiveId =
          (snapshot?.activeTabId && nextTabs.some((tab) => tab.id === snapshot.activeTabId)
            ? snapshot.activeTabId
            : nextTabs[0]?.id) ?? "";
        setActiveTabId(preferredActiveId);
        const preferredMru =
          snapshot?.mru && snapshot.mru.length > 0 ? snapshot.mru : nextTabs.map((tab) => tab.id);
        const normalizedMru = preferredMru.filter((id) => nextTabs.some((tab) => tab.id === id));
        setRecentOrder(normalizedMru);
        setHasOpenedInitialTab(true);
      }
    }

    setHasHydratedPersistence(true);
  }, [hasHydratedPersistence, persistence, tree]);

  useEffect(() => {
    if (!tree || !hasHydratedPersistence) {
      return;
    }
    if (tabs.length > 0) {
      if (!hasOpenedInitialTab) {
        setHasOpenedInitialTab(true);
      }
      return;
    }
    if (hasOpenedInitialTab) {
      return;
    }
    const preferred = (initialActiveFileId && findFileNode(tree, initialActiveFileId)) || findFirstFile(tree);
    if (!preferred) {
      setHasOpenedInitialTab(true);
      return;
    }
    ensureFileOpen(preferred.id);
    setHasOpenedInitialTab(true);
  }, [
    tree,
    initialActiveFileId,
    ensureFileOpen,
    hasHydratedPersistence,
    tabs.length,
    hasOpenedInitialTab,
  ]);

  const openFile = useCallback(
    (fileId: string) => {
      ensureFileOpen(fileId);
    },
    [ensureFileOpen],
  );

  const selectTab = useCallback(
    (fileId: string) => {
      setActiveTab(fileId);
      setTabs((current) =>
        current.map((tab) =>
          tab.id === fileId && tab.status === "error" ? { ...tab, status: "loading", error: null } : tab,
        ),
      );
    },
    [setActiveTab],
  );

  const closeTab = useCallback(
    (fileId: string) => {
      setTabs((current) => {
        const remaining = current.filter((tab) => tab.id !== fileId);
        const prevActive = activeTabIdRef.current;
        const nextActiveId =
          prevActive === fileId
            ? remaining[remaining.length - 1]?.id ?? ""
            : remaining.some((tab) => tab.id === prevActive)
              ? prevActive
              : remaining[remaining.length - 1]?.id ?? "";
        setActiveTab(nextActiveId);
        return remaining;
      });
    },
    [setActiveTab],
  );

  const closeOtherTabs = useCallback(
    (fileId: string) => {
      setTabs((current) => {
        if (!current.some((tab) => tab.id === fileId) || current.length <= 1) {
          return current;
        }
        setActiveTab(fileId);
        return current.filter((tab) => tab.id === fileId);
      });
    },
    [setActiveTab],
  );

  const closeTabsToRight = useCallback(
    (fileId: string) => {
      setTabs((current) => {
        const targetIndex = current.findIndex((tab) => tab.id === fileId);
        if (targetIndex === -1 || targetIndex === current.length - 1) {
          return current;
        }
        const next = current.slice(0, targetIndex + 1);
        const nextActiveId = next.some((tab) => tab.id === activeTabIdRef.current)
          ? activeTabIdRef.current
          : fileId;
        setActiveTab(nextActiveId);
        return next;
      });
    },
    [setActiveTab],
  );

  const closeAllTabs = useCallback(() => {
    setTabs([]);
    setActiveTabId("");
    setRecentOrder([]);
  }, []);

  const moveTab = useCallback(
    (fileId: string, targetIndex: number, options?: MoveTabOptions) => {
      setTabs((current) => {
        if (current.length <= 1) {
          return current;
        }
        const fromIndex = current.findIndex((tab) => tab.id === fileId);
        if (fromIndex === -1) {
          return current;
        }
        const boundedTarget = Math.max(0, Math.min(targetIndex, current.length));
        let insertIndex = boundedTarget;
        if (fromIndex < boundedTarget) {
          insertIndex -= 1;
        }
        const pinned: WorkbenchFileTab[] = [];
        const regular: WorkbenchFileTab[] = [];
        let moving: WorkbenchFileTab | null = null;
        current.forEach((tab, index) => {
          if (index === fromIndex) {
            moving = tab;
            return;
          }
          if (tab.pinned) {
            pinned.push(tab);
          } else {
            regular.push(tab);
          }
        });
        if (!moving) {
          return current;
        }
        const zone: WorkbenchTabZone =
          options?.zone ?? (insertIndex <= pinned.length ? "pinned" : "regular");
        if (zone === "pinned") {
          const clampedIndex = Math.max(0, Math.min(insertIndex, pinned.length));
          pinned.splice(clampedIndex, 0, { ...moving, pinned: true });
        } else {
          const relativeIndex = Math.max(0, Math.min(insertIndex - pinned.length, regular.length));
          regular.splice(relativeIndex, 0, { ...moving, pinned: false });
        }
        return [...pinned, ...regular];
      });
    },
    [],
  );

  const pinTab = useCallback((fileId: string) => {
    setTabs((current) => {
      const pinned: WorkbenchFileTab[] = [];
      const regular: WorkbenchFileTab[] = [];
      let target: WorkbenchFileTab | null = null;
      for (const tab of current) {
        if (tab.id === fileId) {
          target = tab;
          continue;
        }
        if (tab.pinned) {
          pinned.push(tab);
        } else {
          regular.push(tab);
        }
      }
      if (!target || target.pinned) {
        return current;
      }
      const updated = { ...target, pinned: true };
      return [...pinned, updated, ...regular];
    });
  }, []);

  const unpinTab = useCallback((fileId: string) => {
    setTabs((current) => {
      const pinned: WorkbenchFileTab[] = [];
      const regular: WorkbenchFileTab[] = [];
      let target: WorkbenchFileTab | null = null;
      for (const tab of current) {
        if (tab.id === fileId) {
          target = tab;
          continue;
        }
        if (tab.pinned) {
          pinned.push(tab);
        } else {
          regular.push(tab);
        }
      }
      if (!target || !target.pinned) {
        return current;
      }
      const updated = { ...target, pinned: false };
      return [...pinned, updated, ...regular];
    });
  }, []);

  const toggleTabPin = useCallback(
    (fileId: string, pinned: boolean) => {
      if (pinned) {
        pinTab(fileId);
      } else {
        unpinTab(fileId);
      }
    },
    [pinTab, unpinTab],
  );

  const selectRecentTab = useCallback(
    (direction: "forward" | "backward") => {
      const ordered = recentOrderRef.current.filter((id) =>
        tabsRef.current.some((tab) => tab.id === id),
      );
      if (ordered.length <= 1) {
        return;
      }
      const activeId = activeTabIdRef.current || ordered[0];
      const currentIndex = ordered.indexOf(activeId);
      const safeIndex = currentIndex >= 0 ? currentIndex : 0;
      const delta = direction === "forward" ? 1 : -1;
      const nextIndex = (safeIndex + delta + ordered.length) % ordered.length;
      const nextId = ordered[nextIndex];
      if (nextId && nextId !== activeId) {
        setActiveTab(nextId);
      }
    },
    [setActiveTab],
  );

  const updateContent = useCallback((fileId: string, content: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              content,
              status: tab.status === "ready" ? tab.status : "ready",
              error: null,
              saveError: null,
            }
          : tab,
      ),
    );
  }, []);

  const beginSavingTab = useCallback((fileId: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              saving: true,
              saveError: null,
            }
          : tab,
      ),
    );
  }, []);

  const completeSavingTab = useCallback(
    (fileId: string, options?: { metadata?: WorkbenchFileMetadata; etag?: string | null }) => {
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          const resolvedMetadata = options?.metadata ?? tab.metadata ?? null;
          const resolvedEtag = options?.etag ?? tab.etag ?? null;
          return {
            ...tab,
            saving: false,
            saveError: null,
            initialContent: tab.content,
            etag: resolvedEtag,
            metadata: resolvedMetadata
              ? {
                  ...resolvedMetadata,
                  etag: resolvedMetadata.etag ?? resolvedEtag ?? null,
                }
              : resolvedMetadata,
            lastSavedAt: new Date().toISOString(),
          };
        }),
      );
    },
    [],
  );

  const failSavingTab = useCallback((fileId: string, message: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              saving: false,
              saveError: message,
            }
          : tab,
      ),
    );
  }, []);

  const replaceTabContent = useCallback(
    (fileId: string, payload: { content: string; metadata?: WorkbenchFileMetadata; etag?: string | null }) => {
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          return {
            ...tab,
            content: payload.content,
            initialContent: payload.content,
            status: "ready",
            error: null,
            saving: false,
            saveError: null,
            etag: payload.etag ?? tab.etag ?? null,
            metadata: payload.metadata ?? tab.metadata,
          };
        }),
      );
    },
    [],
  );

  const isDirty = useMemo(
    () => tabs.some((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [tabs],
  );

  useEffect(() => {
    tabsRef.current = tabs;
  }, [tabs]);

  useEffect(() => {
    setRecentOrder((current) => {
      const filtered = current.filter((id) => tabs.some((tab) => tab.id === id));
      return filtered.length === current.length ? current : filtered;
    });
  }, [tabs]);

  useEffect(() => {
    const visibleTabIds = new Set(tabs.map((tab) => tab.id));
    for (const pendingId of pendingLoadsRef.current) {
      if (!visibleTabIds.has(pendingId)) {
        pendingLoadsRef.current.delete(pendingId);
      }
    }
    for (const tab of tabs) {
      if (tab.status !== "loading" || pendingLoadsRef.current.has(tab.id)) {
        continue;
      }
      pendingLoadsRef.current.add(tab.id);
      const pending = loadIntoTab(tab.id);
      pending.finally(() => {
        pendingLoadsRef.current.delete(tab.id);
      });
    }
  }, [tabs, loadIntoTab]);

  useEffect(() => {
    if (!persistence || !hasHydratedPersistence) {
      return;
    }
    const orderedRecentTabs = [activeTabId, ...recentOrder]
      .filter((id): id is string => Boolean(id))
      .filter((id, index, array) => array.indexOf(id) === index)
      .filter((id) => tabs.some((tab) => tab.id === id));
    persistence.set<PersistedWorkbenchTabs>({
      openTabs: tabs.map((tab) => ({ id: tab.id, pinned: Boolean(tab.pinned) })),
      activeTabId: activeTabId || null,
      mru: orderedRecentTabs,
    });
  }, [persistence, tabs, activeTabId, recentOrder, hasHydratedPersistence]);

  return {
    tree,
    tabs,
    activeTabId,
    activeTab,
    openFile,
    selectTab,
    closeTab,
    closeOtherTabs,
    closeTabsToRight,
    closeAllTabs,
    moveTab,
    pinTab,
    unpinTab,
    toggleTabPin,
    selectRecentTab,
    updateContent,
    beginSavingTab,
    completeSavingTab,
    failSavingTab,
    replaceTabContent,
    isDirty,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchUrlState.ts
```typescript
import { useCallback, useMemo } from "react";

import {
  DEFAULT_CONFIG_BUILDER_SEARCH,
  mergeConfigBuilderSearch,
  readConfigBuilderSearch,
  useSearchParams,
} from "@app/nav/urlState";
import type { ConfigBuilderConsole, ConfigBuilderPane } from "@app/nav/urlState";

interface WorkbenchUrlState {
  readonly fileId?: string;
  readonly pane: ConfigBuilderPane;
  readonly console: ConfigBuilderConsole;
  readonly consoleExplicit: boolean;
  readonly setFileId: (fileId: string | undefined) => void;
  readonly setPane: (pane: ConfigBuilderPane) => void;
  readonly setConsole: (console: ConfigBuilderConsole) => void;
}

export function useWorkbenchUrlState(): WorkbenchUrlState {
  const [params, setSearchParams] = useSearchParams();
  const snapshot = useMemo(() => readConfigBuilderSearch(params), [params]);

  const setFileId = useCallback(
    (fileId: string | undefined) => {
      if (snapshot.file === fileId || (!fileId && !snapshot.present.file)) {
        return;
      }
      setSearchParams((current) => mergeConfigBuilderSearch(current, { file: fileId ?? undefined }), {
        replace: true,
      });
    },
    [setSearchParams, snapshot.file, snapshot.present.file],
  );

  const setPane = useCallback(
    (pane: ConfigBuilderPane) => {
      if (snapshot.pane === pane) {
        return;
      }
      setSearchParams((current) => mergeConfigBuilderSearch(current, { pane }), { replace: true });
    },
    [setSearchParams, snapshot.pane],
  );

  const setConsole = useCallback(
    (console: ConfigBuilderConsole) => {
      if (snapshot.console === console) {
        return;
      }
      setSearchParams((current) => mergeConfigBuilderSearch(current, { console }), { replace: true });
    },
    [setSearchParams, snapshot.console],
  );

  return {
    fileId: snapshot.file ?? DEFAULT_CONFIG_BUILDER_SEARCH.file,
    pane: snapshot.pane,
    console: snapshot.console,
    consoleExplicit: snapshot.present.console,
    setFileId,
    setPane,
    setConsole,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/workbenchWindowState.ts
```typescript
export function getWorkbenchReturnPathStorageKey(workspaceId: string) {
  return `ade.ui.workspace.${workspaceId}.workbench.returnPath`;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/types.ts
```typescript
export type WorkbenchFileKind = "file" | "folder";

export interface WorkbenchFileMetadata {
  size?: number | null;
  modifiedAt?: string | null;
  contentType?: string | null;
  etag?: string | null;
}

export interface WorkbenchFileNode {
  id: string;
  name: string;
  kind: WorkbenchFileKind;
  language?: string;
  children?: WorkbenchFileNode[];
  metadata?: WorkbenchFileMetadata | null;
}

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

export type WorkbenchConsoleLevel = "info" | "success" | "warning" | "error";

export interface WorkbenchConsoleLine {
  readonly level: WorkbenchConsoleLevel;
  readonly message: string;
  readonly timestamp?: string;
}

export interface WorkbenchValidationMessage {
  readonly level: "info" | "warning" | "error";
  readonly message: string;
  readonly path?: string;
}

export interface WorkbenchDataSeed {
  readonly tree: WorkbenchFileNode;
  readonly content: Record<string, string>;
  readonly console?: readonly WorkbenchConsoleLine[];
  readonly validation?: readonly WorkbenchValidationMessage[];
}

export interface WorkbenchValidationState {
  readonly status: "idle" | "running" | "success" | "error";
  readonly messages: readonly WorkbenchValidationMessage[];
  readonly lastRunAt?: string;
  readonly error?: string | null;
  readonly digest?: string | null;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts
```typescript
import type { BuildEvent, BuildCompletedEvent, BuildLogEvent, BuildStepEvent } from "@shared/builds/types";
import { isTelemetryEnvelope } from "@shared/runs/types";
import type { RunCompletedEvent, RunLogEvent, RunStreamEvent } from "@shared/runs/types";
import type { TelemetryEnvelope } from "@schema/adeTelemetry";

import type { WorkbenchConsoleLine } from "../types";

const TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
};

export function formatConsoleTimestamp(value: number | Date): string {
  const date = typeof value === "number" ? new Date(value * 1000) : value;
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString([], TIME_OPTIONS);
}

export function describeBuildEvent(event: BuildEvent): WorkbenchConsoleLine {
  switch (event.type) {
    case "build.created":
      return {
        level: "info",
        message: `Build ${event.build_id} created (status: ${event.status}).`,
        timestamp: formatConsoleTimestamp(event.created),
      };
    case "build.step":
      return formatBuildStep(event);
    case "build.log":
      return formatBuildLog(event);
    case "build.completed":
      return formatBuildCompletion(event);
    default:
      return {
        level: "info",
        message: JSON.stringify(event),
        timestamp: formatConsoleTimestamp(event.created),
      };
  }
}

export function describeRunEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  if (isTelemetryEnvelope(event)) {
    return formatTelemetry(event);
  }
  switch (event.type) {
    case "run.created":
      return {
        level: "info",
        message: `Run ${event.run_id} created (status: ${event.status}).`,
        timestamp: formatConsoleTimestamp(event.created),
      };
    case "run.started":
      return {
        level: "info",
        message: "Run started.",
        timestamp: formatConsoleTimestamp(event.created),
      };
    case "run.log":
      return formatRunLog(event);
    case "run.completed":
      return formatRunCompletion(event);
    default: {
      const neverEvent: never = event;
      return {
        level: "info",
        message: JSON.stringify(neverEvent),
        timestamp: "",
      };
    }
  }
}

function formatTelemetry(event: TelemetryEnvelope): WorkbenchConsoleLine {
  const { event: payload, timestamp } = event;
  const { event: name, level, ...rest } = payload;
  const normalizedLevel = telemetryToConsoleLevel(level);
  const extras = Object.keys(rest).length > 0 ? ` ${JSON.stringify(rest)}` : "";
  return {
    level: normalizedLevel,
    message: extras ? `Telemetry: ${name}${extras}` : `Telemetry: ${name}`,
    timestamp: formatConsoleTimestamp(new Date(timestamp)),
  };
}

function telemetryToConsoleLevel(level: TelemetryEnvelope["event"]["level"]): WorkbenchConsoleLine["level"] {
  switch (level) {
    case "warning":
      return "warning";
    case "error":
    case "critical":
      return "error";
    default:
      return "info";
  }
}

function formatBuildStep(event: BuildStepEvent): WorkbenchConsoleLine {
  const friendly = buildStepDescriptions[event.step] ?? event.step.replaceAll("_", " ");
  const message = event.message?.trim() ? event.message : friendly;
  return {
    level: "info",
    message,
    timestamp: formatConsoleTimestamp(event.created),
  };
}

const buildStepDescriptions: Record<BuildStepEvent["step"], string> = {
  create_venv: "Creating virtual environment…",
  upgrade_pip: "Upgrading pip inside the build environment…",
  install_engine: "Installing ade_engine package…",
  install_config: "Installing configuration package…",
  verify_imports: "Verifying ADE imports…",
  collect_metadata: "Collecting build metadata…",
};

function formatBuildLog(event: BuildLogEvent): WorkbenchConsoleLine {
  return {
    level: event.stream === "stderr" ? "warning" : "info",
    message: event.message,
    timestamp: formatConsoleTimestamp(event.created),
  };
}

function formatBuildCompletion(event: BuildCompletedEvent): WorkbenchConsoleLine {
  const timestamp = formatConsoleTimestamp(event.created);
  if (event.status === "active") {
    return {
      level: "success",
      message: event.summary?.trim() || "Build completed successfully.",
      timestamp,
    };
  }
  if (event.status === "canceled") {
    return {
      level: "warning",
      message: "Build was canceled before completion.",
      timestamp,
    };
  }
  const error = event.error_message?.trim() || "Build failed.";
  const exit = typeof event.exit_code === "number" ? ` (exit code ${event.exit_code})` : "";
  return {
    level: "error",
    message: `${error}${exit}`,
    timestamp,
  };
}

function formatRunLog(event: RunLogEvent): WorkbenchConsoleLine {
  return {
    level: event.stream === "stderr" ? "warning" : "info",
    message: event.message,
    timestamp: formatConsoleTimestamp(event.created),
  };
}

function formatRunCompletion(event: RunCompletedEvent): WorkbenchConsoleLine {
  const timestamp = formatConsoleTimestamp(event.created);
  if (event.status === "succeeded") {
    const exit = typeof event.exit_code === "number" ? ` (exit code ${event.exit_code})` : "";
    return {
      level: "success",
      message: `Run completed successfully${exit}.`,
      timestamp,
    };
  }
  if (event.status === "canceled") {
    return {
      level: "warning",
      message: "Run was canceled before completion.",
      timestamp,
    };
  }
  const error = event.error_message?.trim() || "Run failed.";
  const exit = typeof event.exit_code === "number" ? ` (exit code ${event.exit_code})` : "";
  return {
    level: "error",
    message: `${error}${exit}`,
    timestamp,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/drag.ts
```typescript
import type { PointerEvent as ReactPointerEvent } from "react";

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

interface PointerDragOptions {
  readonly onMove: (moveEvent: PointerEvent) => void;
  readonly onEnd?: (moveEvent: PointerEvent) => void;
  readonly cursor?: "col-resize" | "row-resize";
}

export function trackPointerDrag(event: ReactPointerEvent, options: PointerDragOptions) {
  const { onMove, onEnd, cursor } = options;

  if (typeof window === "undefined") {
    return;
  }

  event.preventDefault();

  const pointerId = event.pointerId;
  const target = event.currentTarget as HTMLElement;
  const previousCursor = document.body.style.cursor;
  const previousUserSelect = document.body.style.userSelect;
  let animationFrame: number | null = null;
  let lastMoveEvent: PointerEvent | null = null;
  let active = true;

  const cleanup = (finalEvent: PointerEvent) => {
    if (!active) {
      return;
    }
    active = false;
    if (animationFrame !== null) {
      cancelAnimationFrame(animationFrame);
      animationFrame = null;
    }
    document.body.style.cursor = previousCursor;
    document.body.style.userSelect = previousUserSelect;
    window.removeEventListener("pointermove", handleMove);
    window.removeEventListener("pointerup", handleUpOrCancel);
    window.removeEventListener("pointercancel", handleUpOrCancel);
    target.removeEventListener("lostpointercapture", handleLostCapture);
    if (target.hasPointerCapture?.(pointerId)) {
      try {
        target.releasePointerCapture(pointerId);
      } catch {
        // ignore release failures caused by stale handles
      }
    }
    if (onEnd) {
      onEnd(finalEvent);
    }
  };

  const handleMove = (moveEvent: PointerEvent) => {
    if (!active || moveEvent.pointerId !== pointerId) {
      return;
    }
    lastMoveEvent = moveEvent;
    if (animationFrame !== null) {
      return;
    }
    animationFrame = window.requestAnimationFrame(() => {
      animationFrame = null;
      if (lastMoveEvent) {
        onMove(lastMoveEvent);
      }
    });
  };

  const handleUpOrCancel = (pointerEvent: PointerEvent) => {
    if (pointerEvent.pointerId !== pointerId) {
      return;
    }
    cleanup(pointerEvent);
  };

  const handleLostCapture = (pointerEvent: PointerEvent) => {
    if (pointerEvent.pointerId !== pointerId) {
      return;
    }
    cleanup(pointerEvent);
  };

  if (cursor) {
    document.body.style.cursor = cursor;
  }
  document.body.style.userSelect = "none";

  try {
    target.setPointerCapture(pointerId);
  } catch {
    // Pointer capture is not critical; ignore failures (e.g., when ref is gone)
  }

  window.addEventListener("pointermove", handleMove);
  window.addEventListener("pointerup", handleUpOrCancel);
  window.addEventListener("pointercancel", handleUpOrCancel);
  target.addEventListener("lostpointercapture", handleLostCapture);
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/tree.ts
```typescript
import type { FileListing } from "@shared/configs/types";

import type { WorkbenchFileNode } from "../types";

const LANGUAGE_BY_EXTENSION: Record<string, string> = {
  json: "json",
  py: "python",
  ts: "typescript",
  tsx: "typescriptreact",
  js: "javascript",
  jsx: "javascriptreact",
  env: "dotenv",
  md: "markdown",
  yml: "yaml",
  yaml: "yaml",
  toml: "toml",
};

export function createWorkbenchTreeFromListing(listing: FileListing): WorkbenchFileNode | null {
  const rootId = listing.root || listing.prefix || listing.entries[0]?.parent || "";
  const hasEntries = listing.entries.length > 0;

  if (!rootId && !hasEntries) {
    return null;
  }

  const canonicalRootId = canonicalizePath(rootId);

  const rootNode: WorkbenchFileNode = {
    id: rootId,
    name: extractName(rootId),
    kind: "folder",
    children: [],
  };

  const nodes = new Map<string, WorkbenchFileNode>([[rootId, rootNode]]);

  const ensureFolder = (path: string): WorkbenchFileNode => {
    if (path.length === 0) {
      return rootNode;
    }
    const normalizedPath = canonicalizePath(path);
    const nodeId = normalizedPath === canonicalRootId ? rootId : normalizedPath;
    const existing = nodes.get(nodeId);
    if (existing) {
      return existing;
    }
    const folder: WorkbenchFileNode = {
      id: nodeId,
      name: extractName(nodeId),
      kind: "folder",
      children: [],
    };
    nodes.set(nodeId, folder);
    const parentPath = nodeId === rootId ? "" : deriveParent(nodeId) ?? rootId;
    const parentNode = ensureFolder(parentPath);
    addChild(parentNode, folder);
    return folder;
  };

  const sortedEntries = [...listing.entries].sort((a, b) => {
    if (a.depth !== b.depth) {
      return a.depth - b.depth;
    }
    return a.path.localeCompare(b.path);
  });

  for (const entry of sortedEntries) {
    const parentPath = entry.parent && entry.parent.length > 0 ? canonicalizePath(entry.parent) : rootId;
    const parentNode = ensureFolder(parentPath);

    if (entry.kind === "dir") {
      const folder = ensureFolder(entry.path);
      folder.name = entry.name;
      folder.metadata = {
        size: entry.size ?? null,
        modifiedAt: entry.mtime,
        contentType: entry.content_type,
        etag: entry.etag,
      };
      if (folder !== parentNode) {
        addChild(parentNode, folder);
      }
      continue;
    }

    const fileNode: WorkbenchFileNode = {
      id: entry.path,
      name: entry.name,
      kind: "file",
      language: inferLanguage(entry.path),
      metadata: {
        size: entry.size ?? null,
        modifiedAt: entry.mtime,
        contentType: entry.content_type,
        etag: entry.etag,
      },
    };
    nodes.set(entry.path, fileNode);
    addChild(parentNode, fileNode);
  }

  return rootNode;
}

function addChild(parent: WorkbenchFileNode, child: WorkbenchFileNode) {
  const existing = parent.children ?? [];
  const next = existing.some((node) => node.id === child.id)
    ? existing.map((node) => (node.id === child.id ? child : node))
    : [...existing, child];
  parent.children = next.sort(compareNodes);
}

function compareNodes(a: WorkbenchFileNode, b: WorkbenchFileNode): number {
  if (a.kind !== b.kind) {
    return a.kind === "folder" ? -1 : 1;
  }
  return a.name.localeCompare(b.name);
}

function inferLanguage(path: string): string | undefined {
  const normalized = path.toLowerCase();
  const extensionIndex = normalized.lastIndexOf(".");
  if (extensionIndex === -1) {
    return undefined;
  }
  const extension = normalized.slice(extensionIndex + 1);
  return LANGUAGE_BY_EXTENSION[extension];
}

function extractName(path: string): string {
  const normalized = canonicalizePath(path);
  if (!normalized) {
    return "";
  }
  const index = normalized.lastIndexOf("/");
  return index >= 0 ? normalized.slice(index + 1) : normalized;
}

function deriveParent(path: string): string | undefined {
  const normalized = canonicalizePath(path);
  if (!normalized) {
    return undefined;
  }
  const index = normalized.lastIndexOf("/");
  if (index === -1) {
    return "";
  }
  return normalized.slice(0, index);
}

function canonicalizePath(path: string): string {
  if (!path) {
    return "";
  }
  return path.replace(/\/+$/, "");
}

export function findFileNode(root: WorkbenchFileNode, id: string): WorkbenchFileNode | null {
  if (root.id === id) {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const match = findFileNode(child, id);
    if (match) {
      return match;
    }
  }
  return null;
}

export function findFirstFile(root: WorkbenchFileNode): WorkbenchFileNode | null {
  if (root.kind === "file") {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const file = findFirstFile(child);
    if (file) {
      return file;
    }
  }
  return null;
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
