# Logical module layout (source -> sections below):
# - apps/ade-web/README.md
# - apps/ade-web/src/app/App.tsx
# - apps/ade-web/src/app/AppProviders.tsx
# - apps/ade-web/src/app/nav/Link.tsx
# - apps/ade-web/src/app/nav/history.tsx
# - apps/ade-web/src/app/nav/urlState.ts
# - apps/ade-web/src/app/shell/GlobalSearchField.tsx
# - apps/ade-web/src/app/shell/GlobalTopBar.tsx
# - apps/ade-web/src/app/shell/ProfileDropdown.tsx
# - apps/ade-web/src/main.tsx
# - apps/ade-web/src/ui/Alert/Alert.tsx
# - apps/ade-web/src/ui/Alert/index.ts
# - apps/ade-web/src/ui/Avatar/Avatar.tsx
# - apps/ade-web/src/ui/Avatar/index.ts
# - apps/ade-web/src/ui/Button/Button.tsx
# - apps/ade-web/src/ui/Button/index.ts
# - apps/ade-web/src/ui/CodeEditor/CodeEditor.tsx
# - apps/ade-web/src/ui/CodeEditor/CodeEditor.types.ts
# - apps/ade-web/src/ui/CodeEditor/MonacoCodeEditor.tsx - /apps/ade-web/src/ui/CodeEditor/MonacoCodeEditor.tsx
# - apps/ade-web/src/ui/CodeEditor/adeScriptApi.ts
# - apps/ade-web/src/ui/CodeEditor/index.ts
# - apps/ade-web/src/ui/CodeEditor/registerAdeScriptHelpers.ts - /apps/ade-web/src/ui/CodeEditor/registerAdeScriptHelpers.ts
# - apps/ade-web/src/ui/ContextMenu/ContextMenu.tsx
# - apps/ade-web/src/ui/ContextMenu/index.ts
# - apps/ade-web/src/ui/FormField/FormField.tsx
# - apps/ade-web/src/ui/FormField/index.ts
# - apps/ade-web/src/ui/Input/Input.tsx
# - apps/ade-web/src/ui/Input/index.ts
# - apps/ade-web/src/ui/Select/Select.tsx
# - apps/ade-web/src/ui/Select/index.ts
# - apps/ade-web/src/ui/SplitButton/SplitButton.tsx
# - apps/ade-web/src/ui/SplitButton/index.ts
# - apps/ade-web/src/ui/Tabs/Tabs.tsx
# - apps/ade-web/src/ui/Tabs/index.ts
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

# apps/ade-web/src/app/shell/GlobalSearchField.tsx
```tsx
import {
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import clsx from "clsx";

export interface GlobalSearchSuggestion {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly icon?: ReactNode;
  readonly action?: () => void;
  readonly shortcutHint?: string;
}

export interface GlobalSearchFilter {
  readonly id: string;
  readonly label: string;
  readonly active?: boolean;
}

export type GlobalSearchFieldVariant = "default" | "minimal";

export interface GlobalSearchFieldProps {
  readonly id?: string;
  readonly value?: string;
  readonly defaultValue?: string;
  readonly placeholder?: string;
  readonly ariaLabel?: string;
  readonly shortcutHint?: string;
  readonly shortcutKey?: string;
  readonly enableShortcut?: boolean;
  readonly scopeLabel?: string;
  readonly leadingIcon?: ReactNode;
  readonly trailingIcon?: ReactNode;
  readonly className?: string;
  readonly variant?: GlobalSearchFieldVariant;
  readonly isLoading?: boolean;
  readonly loadingLabel?: string;
  readonly filters?: readonly GlobalSearchFilter[];
  readonly onSelectFilter?: (filter: GlobalSearchFilter) => void;
  readonly emptyState?: ReactNode;
  readonly onChange?: (value: string) => void;
  readonly onSubmit?: (value: string) => void;
  readonly onClear?: () => void;
  readonly onFocus?: () => void;
  readonly onBlur?: () => void;
  readonly suggestions?: readonly GlobalSearchSuggestion[];
  readonly onSelectSuggestion?: (suggestion: GlobalSearchSuggestion) => void;
  readonly renderSuggestion?: (args: { suggestion: GlobalSearchSuggestion; active: boolean }) => ReactNode;
}

export function GlobalSearchField({
  id,
  value,
  defaultValue = "",
  placeholder = "Search…",
  ariaLabel,
  shortcutHint = "⌘K",
  shortcutKey = "k",
  enableShortcut = true,
  scopeLabel,
  leadingIcon,
  trailingIcon,
  className,
  variant = "default",
  isLoading = false,
  loadingLabel = "Loading suggestions",
  filters,
  onSelectFilter,
  emptyState,
  onChange,
  onSubmit,
  onClear,
  onFocus,
  onBlur,
  suggestions = [],
  onSelectSuggestion,
  renderSuggestion,
}: GlobalSearchFieldProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const suggestionsListId = `${generatedId}-suggestions`;
  const searchInputRef = useRef<HTMLInputElement>(null);
  const isControlled = value !== undefined;
  const [uncontrolledQuery, setUncontrolledQuery] = useState(defaultValue);
  const [isFocused, setIsFocused] = useState(false);
  const [highlightedSuggestion, setHighlightedSuggestion] = useState(0);
  const query = isControlled ? value ?? "" : uncontrolledQuery;
  const hasSuggestions = suggestions.length > 0;
  const hasFilters = Boolean(filters?.length);
  const showDropdown = isFocused && (hasSuggestions || isLoading || Boolean(emptyState) || hasFilters);
  const showEmptyState = isFocused && !hasSuggestions && !isLoading && Boolean(emptyState);
  const canClear = Boolean(onClear || !isControlled);
  const shortcutLabel = shortcutHint || "⌘K";
  const searchAriaLabel = ariaLabel ?? placeholder;

  useEffect(() => {
    if (!isControlled) {
      setUncontrolledQuery(defaultValue);
    }
  }, [defaultValue, isControlled]);

  useEffect(() => {
    setHighlightedSuggestion(0);
  }, [suggestions.length, query]);

  useEffect(() => {
    if (!enableShortcut) {
      return;
    }
    if (typeof window === "undefined") {
      return;
    }
    const handleKeydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === shortcutKey.toLowerCase()) {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [enableShortcut, shortcutKey]);

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed && !onSubmit) {
      return;
    }
    onSubmit?.(trimmed);
  };

  const handleSearchChange = (next: string) => {
    if (!isControlled) {
      setUncontrolledQuery(next);
    }
    onChange?.(next);
  };

  const handleClear = () => {
    if (!query) {
      return;
    }
    if (!isControlled) {
      setUncontrolledQuery("");
    }
    onChange?.("");
    onClear?.();
    searchInputRef.current?.focus();
  };

  const handleSuggestionSelection = (suggestion?: GlobalSearchSuggestion) => {
    if (!suggestion) {
      return;
    }
    onSelectSuggestion?.(suggestion);
    suggestion.action?.();
    setIsFocused(false);
    searchInputRef.current?.blur();
  };

  const handleSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (!showDropdown || !hasSuggestions) {
      if (event.key === "Escape") {
        setIsFocused(false);
        event.currentTarget.blur();
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedSuggestion((current) => (current + 1) % suggestions.length);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedSuggestion((current) => (current - 1 + suggestions.length) % suggestions.length);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      handleSuggestionSelection(suggestions[highlightedSuggestion]);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setIsFocused(false);
      event.currentTarget.blur();
    }
  };

  const variantClasses =
    variant === "minimal"
      ? "rounded-lg border border-slate-200 bg-white shadow-sm focus-within:border-brand-200"
      : "rounded-xl border border-slate-200/70 bg-gradient-to-r from-white/95 via-slate-50/80 to-white/95 shadow-[0_20px_45px_-30px_rgba(15,23,42,0.65)] ring-1 ring-inset ring-white/80 transition focus-within:border-brand-200 focus-within:shadow-[0_25px_55px_-35px_rgba(79,70,229,0.55)] sm:rounded-2xl";

  return (
    <div className={clsx("relative", className)}>
      <div className={clsx("group/search overflow-hidden", variantClasses, showDropdown && variant === "default" && "focus-within:shadow-[0_35px_80px_-40px_rgba(79,70,229,0.55)]")}>
        <form className="flex w-full items-center gap-3 px-4 py-2 text-sm text-slate-600 sm:px-5 sm:py-2.5" role="search" aria-label={searchAriaLabel} onSubmit={handleSearchSubmit}>
          <label htmlFor={inputId} className="sr-only">
            {searchAriaLabel}
          </label>
          {leadingIcon ?? (
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-white/90 text-brand-600 shadow-inner shadow-white/60 ring-1 ring-inset ring-white/70 sm:h-10 sm:w-10 sm:rounded-xl">
              <SearchIcon className="h-4 w-4 flex-shrink-0 text-brand-600" />
            </span>
          )}
          <div className="flex min-w-0 flex-1 flex-col">
            {scopeLabel ? (
              <span className="text-[0.6rem] font-semibold uppercase tracking-wide text-slate-400 sm:text-[0.65rem]">
                {scopeLabel}
              </span>
            ) : null}
            <input
              ref={searchInputRef}
              id={inputId}
              type="search"
              value={query}
              onChange={(event) => handleSearchChange(event.target.value)}
            onFocus={() => {
              setIsFocused(true);
              onFocus?.();
              // keep highlight stable if no suggestions
              if (!hasSuggestions) {
                setHighlightedSuggestion(0);
                }
              }}
            onBlur={() => {
              setIsFocused(false);
              onBlur?.();
            }}
              onKeyDown={handleSearchKeyDown}
              placeholder={placeholder}
              className="w-full border-0 bg-transparent text-base font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none"
              aria-expanded={showDropdown}
              aria-controls={showDropdown ? suggestionsListId : undefined}
            />
          </div>
          <div className="flex items-center gap-1">
            {canClear && query ? (
              <button
                type="button"
                onClick={handleClear}
                aria-label="Clear search"
                className="focus-ring inline-flex h-7 w-7 items-center justify-center rounded-full border border-transparent text-slate-400 hover:border-slate-200 hover:bg-white"
              >
                <CloseIcon className="h-3.5 w-3.5" />
              </button>
            ) : null}
            {isLoading ? (
              <span className="inline-flex h-7 w-7 items-center justify-center" aria-live="polite" aria-label={loadingLabel}>
                <SpinnerIcon className="h-4 w-4 text-brand-600" />
              </span>
            ) : null}
            {trailingIcon}
            {shortcutLabel ? (
              <span className="hidden items-center gap-1 rounded-full border border-slate-200/80 bg-white/80 px-2 py-1 text-xs font-semibold text-slate-500 shadow-inner shadow-white/60 md:inline-flex">
                {shortcutLabel}
              </span>
            ) : null}
          </div>
        </form>
      </div>
      {showDropdown ? (
        <div className="absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/95 shadow-[0_35px_80px_-40px_rgba(79,70,229,0.55)] ring-1 ring-inset ring-white/80">
          {hasSuggestions ? (
            <ul id={suggestionsListId} role="listbox" aria-label="Search suggestions" className="divide-y divide-slate-100/80">
              {suggestions.map((suggestion, index) => {
                const active = index === highlightedSuggestion;
                const content =
                  renderSuggestion?.({ suggestion, active }) ?? (
                    <DefaultSuggestion suggestion={suggestion} active={active} />
                  );
                return (
                  <li key={suggestion.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={active}
                      onMouseEnter={() => setHighlightedSuggestion(index)}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => handleSuggestionSelection(suggestion)}
                      className={clsx("flex w-full px-5 py-3 text-left transition", active ? "bg-brand-50/60" : "hover:bg-slate-50/80")}
                    >
                      {content}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}
          {showEmptyState ? (
            <div className="px-5 py-4 text-sm text-slate-500" role="status">
              {emptyState}
            </div>
          ) : null}
          {hasFilters ? (
            <div className="border-t border-slate-100/80 bg-slate-50/60 px-4 py-2.5">
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500">
                <span className="uppercase tracking-wide text-[0.6rem] text-slate-400">Filters:</span>
                {filters?.map((filter) => (
                  <button
                    key={filter.id}
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => onSelectFilter?.(filter)}
                    className={clsx(
                      "focus-ring inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold transition",
                      filter.active ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 bg-white text-slate-500 hover:border-slate-300",
                    )}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function DefaultSuggestion({ suggestion, active }: { suggestion: GlobalSearchSuggestion; active: boolean }) {
  return (
    <div className="flex w-full items-start gap-3">
      {suggestion.icon ? (
        <span className="mt-0.5 text-slate-400">{suggestion.icon}</span>
      ) : (
        <span className="mt-1 h-2.5 w-2.5 rounded-full bg-slate-200" aria-hidden />
      )}
      <span className="flex min-w-0 flex-col">
        <span className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-900">{suggestion.label}</span>
          {suggestion.shortcutHint ? (
            <span className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-slate-400">
              {suggestion.shortcutHint}
            </span>
          ) : null}
        </span>
        {suggestion.description ? (
          <span className={clsx("text-xs", active ? "text-brand-700" : "text-slate-500")}>{suggestion.description}</span>
        ) : null}
      </span>
    </div>
  );
}

function SearchIcon({ className = "h-4 w-4 flex-shrink-0 text-slate-400" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <circle cx="9" cy="9" r="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m13.5 13.5 3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CloseIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M6 6l8 8" strokeLinecap="round" />
      <path d="M14 6l-8 8" strokeLinecap="round" />
    </svg>
  );
}

function SpinnerIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={clsx("animate-spin", className)} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-70" d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
```

# apps/ade-web/src/app/shell/GlobalTopBar.tsx
```tsx
import { type ReactNode } from "react";
import clsx from "clsx";

import {
  GlobalSearchField,
  type GlobalSearchFieldProps,
} from "./GlobalSearchField";

export type {
  GlobalSearchFilter,
  GlobalSearchFieldProps as GlobalTopBarSearchProps,
  GlobalSearchSuggestion,
} from "./GlobalSearchField";

interface GlobalTopBarProps {
  readonly brand?: ReactNode;
  readonly leading?: ReactNode;
  readonly actions?: ReactNode;
  readonly trailing?: ReactNode;
  readonly search?: GlobalSearchFieldProps;
  readonly secondaryContent?: ReactNode;
}

export function GlobalTopBar({
  brand,
  leading,
  actions,
  trailing,
  search,
  secondaryContent,
}: GlobalTopBarProps) {
  const showSearch = Boolean(search);
  const searchProps = search
    ? {
        ...search,
        className: clsx(
          "order-last w-full lg:order-none lg:max-w-2xl lg:justify-self-center",
          search.className,
        ),
      }
    : undefined;

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-gradient-to-b from-white/95 via-slate-50/70 to-white/90 shadow-[0_12px_40px_-30px_rgba(15,23,42,0.8)] backdrop-blur supports-[backdrop-filter]:backdrop-blur-xl">
      <div className="flex flex-col gap-3 px-4 py-3 sm:px-6 lg:px-10">
        <div
          className={clsx(
            "flex min-h-[3.5rem] w-full flex-wrap items-center gap-3 sm:gap-4",
            showSearch ? "lg:grid lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:items-center lg:gap-8" : "justify-between",
          )}
        >
          <div className="flex min-w-0 flex-1 items-center gap-3 lg:flex-none">
            {brand}
            {leading}
          </div>
          {searchProps ? <GlobalSearchField {...searchProps} /> : null}
          <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:flex-none">
            {actions}
            {trailing}
          </div>
        </div>
        {secondaryContent ? <div className="flex flex-wrap items-center gap-2">{secondaryContent}</div> : null}
      </div>
    </header>
  );
}
```

# apps/ade-web/src/app/shell/ProfileDropdown.tsx
```tsx
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useNavigate } from "@app/nav/history";
import clsx from "clsx";

interface ProfileDropdownAction {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly icon?: ReactNode;
  readonly onSelect: () => void;
}

interface ProfileDropdownProps {
  readonly displayName: string;
  readonly email: string;
  readonly actions?: readonly ProfileDropdownAction[];
}

export function ProfileDropdown({
  displayName,
  email,
  actions = [],
}: ProfileDropdownProps) {
  const [open, setOpen] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();

  const initials = useMemo(() => deriveInitials(displayName || email), [displayName, email]);

  const closeMenu = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const handlePointer = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node | null;
      if (!target) {
        return;
      }
      if (menuRef.current?.contains(target) || triggerRef.current?.contains(target)) {
        return;
      }
      closeMenu();
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeMenu();
      }
    };

    window.addEventListener("mousedown", handlePointer);
    window.addEventListener("touchstart", handlePointer, { passive: true });
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("mousedown", handlePointer);
      window.removeEventListener("touchstart", handlePointer);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [closeMenu, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const firstMenuItem = menuRef.current?.querySelector<HTMLButtonElement>("button[data-menu-item]");
    firstMenuItem?.focus({ preventScroll: true });
  }, [open]);

  const handleMenuAction = useCallback(
    (action: () => void) => {
      closeMenu();
      action();
    },
    [closeMenu],
  );

  const handleSignOut = useCallback(async () => {
    if (isSigningOut) {
      return;
    }
    closeMenu();
    setIsSigningOut(true);
    navigate("/logout", { replace: true });
  }, [closeMenu, isSigningOut, navigate]);

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        className="focus-ring inline-flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-left text-sm font-semibold text-slate-700 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-semibold text-white shadow-sm">
          {initials}
        </span>
        <span className="hidden min-w-0 flex-col sm:flex">
          <span className="truncate text-sm font-semibold text-slate-900">{displayName}</span>
          <span className="truncate text-xs text-slate-400">{email}</span>
        </span>
        <ChevronIcon className={clsx("text-slate-400 transition-transform", open && "rotate-180")} />
      </button>

      {open ? (
        <div
          ref={menuRef}
          role="menu"
          className="absolute right-0 z-50 mt-2 w-72 origin-top-right rounded-xl border border-slate-200 bg-white p-2 text-sm shadow-xl"
        >
          <div className="px-2 pb-2">
            <p className="text-sm font-semibold text-slate-900">Signed in as</p>
            <p className="truncate text-xs text-slate-500">{email}</p>
          </div>
          <ul className="space-y-1" role="none">
            {actions.map((action) => (
              <li key={action.id} role="none">
                <button
                  type="button"
                  role="menuitem"
                  data-menu-item
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-700 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                  onClick={() => handleMenuAction(action.onSelect)}
                >
                  <span className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-500">
                    {action.icon ?? action.label.charAt(0).toUpperCase()}
                  </span>
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate">{action.label}</span>
                    {action.description ? (
                      <span className="truncate text-xs font-normal text-slate-400">{action.description}</span>
                    ) : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-2 border-t border-slate-200 pt-2">
            <button
              type="button"
              role="menuitem"
              data-menu-item
              className="focus-ring flex w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-brand-200 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={handleSignOut}
              disabled={isSigningOut}
            >
              <span>Sign out</span>
              {isSigningOut ? <Spinner /> : null}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function deriveInitials(source: string) {
  const parts = source
    .split(" ")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length === 0) {
    return "•";
  }
  if (parts.length === 1) {
    return parts[0].charAt(0).toUpperCase();
  }
  return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-brand-600"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
    >
      <path d="M10 3a7 7 0 1 1-7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={clsx("h-4 w-4", className)} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
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

# apps/ade-web/src/ui/Alert/Alert.tsx
```tsx
import clsx from "clsx";
import type { HTMLAttributes, ReactNode } from "react";

export type AlertTone = "info" | "success" | "warning" | "danger";

const TONE_STYLE: Record<AlertTone, string> = {
  info: "bg-brand-50 text-brand-700 ring-brand-100",
  success: "bg-success-50 text-success-700 ring-success-100",
  warning: "bg-warning-50 text-warning-700 ring-warning-100",
  danger: "bg-danger-50 text-danger-700 ring-danger-100",
};

export interface AlertProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  readonly tone?: AlertTone;
  readonly heading?: ReactNode;
  readonly icon?: ReactNode;
}

export function Alert({ tone = "info", heading, icon, className, children, ...props }: AlertProps) {
  return (
    <div
      role="status"
      className={clsx(
        "flex w-full items-start gap-3 rounded-lg px-4 py-3 text-sm ring-1 ring-inset",
        TONE_STYLE[tone],
        className,
      )}
      {...props}
    >
      {icon ? <span aria-hidden="true">{icon}</span> : null}
      <div className="space-y-1">
        {heading ? <p className="font-semibold">{heading}</p> : null}
        {children ? <p className="leading-relaxed">{children}</p> : null}
      </div>
    </div>
  );
}
```

# apps/ade-web/src/ui/Alert/index.ts
```typescript
export { Alert } from "./Alert";
export type { AlertProps } from "./Alert";
```

# apps/ade-web/src/ui/Avatar/Avatar.tsx
```tsx
import clsx from "clsx";
import { useMemo } from "react";

const SIZE_STYLES = {
  sm: "h-8 w-8 text-sm",
  md: "h-10 w-10 text-base",
  lg: "h-12 w-12 text-lg",
} as const;

export type AvatarSize = keyof typeof SIZE_STYLES;

export interface AvatarProps {
  readonly name?: string | null;
  readonly email?: string | null;
  readonly size?: AvatarSize;
  readonly className?: string;
}

function getInitials(name?: string | null, email?: string | null) {
  if (name && name.trim().length > 0) {
    const parts = name.trim().split(/\s+/u);
    const first = parts[0]?.[0];
    const last = parts[parts.length - 1]?.[0];
    if (first) {
      return `${first}${last ?? ""}`.toUpperCase();
    }
  }
  if (email && email.trim().length > 0) {
    return email.trim()[0]?.toUpperCase();
  }
  return "?";
}

export function Avatar({ name, email, size = "md", className }: AvatarProps) {
  const initials = useMemo(() => getInitials(name, email), [name, email]);

  return (
    <span
      aria-hidden="true"
      className={clsx(
        "inline-flex select-none items-center justify-center rounded-full bg-gradient-to-br from-brand-100 via-brand-200 to-brand-300 font-semibold text-brand-900 shadow-sm",
        SIZE_STYLES[size],
        className,
      )}
    >
      {initials}
    </span>
  );
}
```

# apps/ade-web/src/ui/Avatar/index.ts
```typescript
export { Avatar } from "./Avatar";
export type { AvatarProps } from "./Avatar";
```

# apps/ade-web/src/ui/Button/Button.tsx
```tsx
import clsx from "clsx";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
  readonly isLoading?: boolean;
}

const VARIANT_STYLE: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-600 text-white hover:bg-brand-700 focus-visible:ring-brand-500 disabled:bg-brand-300",
  secondary:
    "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 focus-visible:ring-slate-400 disabled:text-slate-400",
  ghost: "bg-transparent text-slate-700 hover:bg-slate-100 focus-visible:ring-slate-300",
  danger:
    "bg-rose-600 text-white hover:bg-rose-700 focus-visible:ring-rose-500 disabled:bg-rose-300",
};

const SIZE_STYLE: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      type = "button",
      variant = "primary",
      size = "md",
      isLoading = false,
      className,
      children,
      disabled,
      ...props
    },
    ref,
  ) => {
    const isDisabled = disabled || isLoading;

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={isLoading || undefined}
        className={clsx(
          "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 disabled:cursor-not-allowed",
          VARIANT_STYLE[variant],
          SIZE_STYLE[size],
          className,
        )}
        {...props}
      >
        {isLoading ? (
          <span
            aria-hidden="true"
            className="inline-flex h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          />
        ) : null}
        <span>{children}</span>
      </button>
    );
  },
);

Button.displayName = "Button";
```

# apps/ade-web/src/ui/Button/index.ts
```typescript
export { Button } from "./Button";
export type { ButtonProps, ButtonVariant, ButtonSize } from "./Button";
```

# apps/ade-web/src/ui/CodeEditor/CodeEditor.tsx
```tsx
import { forwardRef, lazy, Suspense } from "react";
import clsx from "clsx";

import type { CodeEditorHandle, CodeEditorProps } from "./CodeEditor.types";

const LazyMonacoCodeEditor = lazy(() => import("./MonacoCodeEditor"));

export const CodeEditor = forwardRef<CodeEditorHandle, CodeEditorProps>(function CodeEditor(
  props,
  ref,
) {
  const { className, ...rest } = props;

  return (
    <Suspense
      fallback={
        <div className={clsx("relative h-full w-full", className)}>
          <div className="flex h-full items-center justify-center text-xs text-slate-400">
            Loading editor…
          </div>
        </div>
      }
    >
      <LazyMonacoCodeEditor {...rest} ref={ref} className={className} />
    </Suspense>
  );
});

export type { CodeEditorHandle, CodeEditorProps } from "./CodeEditor.types";
```

# apps/ade-web/src/ui/CodeEditor/CodeEditor.types.ts
```typescript
export interface CodeEditorHandle {
  focus: () => void;
  revealLine: (lineNumber: number) => void;
}

export interface CodeEditorProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly language?: string;
  readonly path?: string;
  readonly readOnly?: boolean;
  readonly onSaveShortcut?: () => void;
  readonly className?: string;
  readonly theme?: string;
}
```

# apps/ade-web/src/ui/CodeEditor/MonacoCodeEditor.tsx
```tsx
// /apps/ade-web/src/ui/CodeEditor/MonacoCodeEditor.tsx

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import Editor, { type BeforeMount, type OnMount } from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import clsx from "clsx";

import type { CodeEditorHandle, CodeEditorProps } from "./CodeEditor.types";
import { disposeAdeScriptHelpers, registerAdeScriptHelpers } from "./registerAdeScriptHelpers";

const ADE_DARK_THEME_ID = "ade-dark";
const ADE_DARK_THEME: MonacoEditor.IStandaloneThemeData = {
  base: "vs-dark",
  inherit: true,
  rules: [],
  colors: {
    "editor.background": "#1f2430",
    "editor.foreground": "#f3f6ff",
    "editorCursor.foreground": "#fbd38d",
    "editor.lineHighlightBackground": "#2a3142",
    "editorLineNumber.foreground": "#8c92a3",
    "editor.selectionBackground": "#3a4256",
    "editor.inactiveSelectionBackground": "#2d3446",
    "editorGutter.background": "#1c212b",
  },
};

const MonacoCodeEditor = forwardRef<CodeEditorHandle, CodeEditorProps>(function MonacoCodeEditor(
  {
    value,
    onChange,
    language = "plaintext",
    path,
    readOnly = false,
    onSaveShortcut,
    className,
    theme = ADE_DARK_THEME_ID,
  }: CodeEditorProps,
  ref,
) {
  const saveShortcutRef = useRef(onSaveShortcut);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const adeLanguageRef = useRef<string | null>(null);
  const editorPath = useMemo(() => toEditorPath(path), [path]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [editorReady, setEditorReady] = useState(false);

  useEffect(() => {
    saveShortcutRef.current = onSaveShortcut;
  }, [onSaveShortcut]);

  const handleChange = useCallback(
    (nextValue: string | undefined) => {
      onChange(nextValue ?? "");
    },
    [onChange],
  );

  const handleMount = useCallback<OnMount>(
    (editor, monacoInstance) => {
      const model = editor.getModel();
      const modelLanguage = model?.getLanguageId() ?? language;

      if (import.meta.env?.DEV) {
        console.debug("[ade] MonacoCodeEditor mounted", {
          language: modelLanguage,
          uri: model?.uri.toString(),
        });
      }

      if (modelLanguage === "python") {
        registerAdeScriptHelpers(monacoInstance, modelLanguage);
        adeLanguageRef.current = modelLanguage;
      }

      editor.addCommand(
        monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyS,
        () => {
          saveShortcutRef.current?.();
        },
      );

      editorRef.current = editor;
      setEditorReady(true);
    },
    [language],
  );

  useEffect(
    () => () => {
      if (adeLanguageRef.current) {
        disposeAdeScriptHelpers(adeLanguageRef.current);
        adeLanguageRef.current = null;
      }
    },
    [],
  );

  useImperativeHandle(
    ref,
    () => ({
      focus: () => {
        editorRef.current?.focus();
      },
      revealLine: (lineNumber: number) => {
        const editor = editorRef.current;
        if (!editor) return;
        const target = Math.max(1, Math.floor(lineNumber));
        editor.revealLineInCenter(target);
        editor.setPosition({ lineNumber: target, column: 1 });
        editor.focus();
      },
    }),
    [],
  );

  // Manual layout so the editor responds to surrounding layout changes
  useEffect(() => {
    if (!editorReady) return;

    const target = containerRef.current;

    if (target && typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => {
        editorRef.current?.layout();
      });
      observer.observe(target);
      editorRef.current?.layout();
      return () => observer.disconnect();
    }

    const handleResize = () => editorRef.current?.layout();
    window.addEventListener("resize", handleResize);
    handleResize();
    return () => window.removeEventListener("resize", handleResize);
  }, [editorReady]);

  useEffect(() => {
    const handleWorkbenchLayout = () => editorRef.current?.layout();
    window.addEventListener("ade:workbench-layout", handleWorkbenchLayout);
    return () => window.removeEventListener("ade:workbench-layout", handleWorkbenchLayout);
  }, []);

  const handleBeforeMount = useCallback<BeforeMount>((monacoInstance) => {
    monacoInstance.editor.defineTheme(ADE_DARK_THEME_ID, ADE_DARK_THEME);
  }, []);

  return (
    <div ref={containerRef} className={clsx("relative h-full w-full min-w-0 overflow-hidden", className)}>
      <Editor
        value={value}
        onChange={handleChange}
        language={language}
        path={editorPath}
        theme={theme}
        beforeMount={handleBeforeMount}
        height="100%"
        width="100%"
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Menlo', 'Monaco', monospace",
          scrollBeyondLastLine: false,
          smoothScrolling: true,
          automaticLayout: true,
          lineNumbersMinChars: 3,
          hover: { enabled: true },
          wordBasedSuggestions: "currentDocument",
          quickSuggestions: { other: true, comments: false, strings: true },
          suggestOnTriggerCharacters: true,
          snippetSuggestions: "inline",
        }}
        loading={
          <div className="flex h-full items-center justify-center text-xs text-slate-400">
            Loading editor…
          </div>
        }
        onMount={handleMount}
      />
    </div>
  );
});

export default MonacoCodeEditor;

function toEditorPath(rawPath: string | undefined): string | undefined {
  if (!rawPath) return undefined;
  if (rawPath.includes("://")) return rawPath;
  const normalized = rawPath.startsWith("/") ? rawPath.slice(1) : rawPath;
  return `inmemory://ade/${normalized}`;
}

export type MonacoModel = ReturnType<Parameters<OnMount>[0]["getModel"]>;
export type MonacoPosition = ReturnType<Parameters<OnMount>[0]["getPosition"]>;
```

# apps/ade-web/src/ui/CodeEditor/adeScriptApi.ts
```typescript
export type AdeFunctionKind =
  | "row_detector"
  | "column_detector"
  | "column_transform"
  | "column_validator"
  | "hook_on_run_start"
  | "hook_after_mapping"
  | "hook_before_save"
  | "hook_on_run_end";

export interface AdeFunctionSpec {
  kind: AdeFunctionKind;
  name: string;
  label: string;
  signature: string;
  doc: string;
  snippet: string;
  parameters: string[];
}

const rowDetectorSpec: AdeFunctionSpec = {
  kind: "row_detector",
  name: "detect_*",
  label: "ADE: row detector (detect_*)",
  signature: [
    "def detect_*(",
    "    *,",
    "    run,",
    "    state,",
    "    row_index: int,",
    "    row_values: list,",
    "    logger,",
    "    **_,",
    ") -> dict:",
  ].join("\n"),
  doc: "Row detector entrypoint: return tiny score deltas to help the engine classify streamed rows as header/data.",
  snippet: `
def detect_\${1:name}(
    *,
    run,
    state,
    row_index: int,
    row_values: list,
    logger,
    **_,
) -> dict:
    """\${2:Explain what this detector scores.}"""
    score = 0.0
    return {"scores": {"\${3:label}": score}}
`.trim(),
  parameters: ["run", "state", "row_index", "row_values", "logger"],
};

const columnDetectorSpec: AdeFunctionSpec = {
  kind: "column_detector",
  name: "detect_*",
  label: "ADE: column detector (detect_*)",
  signature: [
    "def detect_*(",
    "    *,",
    "    run,",
    "    state,",
    "    field_name: str,",
    "    field_meta: dict,",
    "    header: str | None,",
    "    column_values_sample: list,",
    "    column_values: tuple,",
    "    table: dict,",
    "    column_index: int,",
    "    logger,",
    "    **_,",
    ") -> dict:",
  ].join("\n"),
  doc: "Column detector entrypoint: score how likely the current raw column maps to this canonical field.",
  snippet: `
def detect_\${1:value_shape}(
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
    """\${2:Describe your heuristic for this field.}"""
    score = 0.0
    # TODO: inspect header, column_values_sample, etc.
    return {"scores": {field_name: score}}
`.trim(),
  parameters: [
    "run",
    "state",
    "field_name",
    "field_meta",
    "header",
    "column_values_sample",
    "column_values",
    "table",
    "column_index",
    "logger",
  ],
};

const columnTransformSpec: AdeFunctionSpec = {
  kind: "column_transform",
  name: "transform",
  label: "ADE: column transform",
  signature: [
    "def transform(",
    "    *,",
    "    run,",
    "    state,",
    "    row_index: int,",
    "    field_name: str,",
    "    value,",
    "    row: dict,",
    "    logger,",
    "    **_,",
    ") -> dict | None:",
  ].join("\n"),
  doc: "Column transform: normalize the mapped value or populate additional canonical fields for this row.",
  snippet: `
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
    """\${1:Normalize or expand the value for this row.}"""
    if value in (None, ""):
        return None
    normalized = value
    return {field_name: normalized}
`.trim(),
  parameters: ["run", "state", "row_index", "field_name", "value", "row", "logger"],
};

const columnValidatorSpec: AdeFunctionSpec = {
  kind: "column_validator",
  name: "validate",
  label: "ADE: column validator",
  signature: [
    "def validate(",
    "    *,",
    "    run,",
    "    state,",
    "    row_index: int,",
    "    field_name: str,",
    "    value,",
    "    row: dict,",
    "    field_meta: dict | None,",
    "    logger,",
    "    **_,",
    ") -> list[dict]:",
  ].join("\n"),
  doc: "Column validator: emit structured issues for the current row after transforms run.",
  snippet: `
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
    """\${1:Return validation issues for this field/row.}"""
    issues: list[dict] = []
    if field_meta and field_meta.get("required") and value in (None, ""):
        issues.append({
            "row_index": row_index,
            "code": "required_missing",
            "severity": "error",
            "message": f"{field_name} is required.",
        })
    return issues
`.trim(),
  parameters: [
    "run",
    "state",
    "row_index",
    "field_name",
    "value",
    "row",
    "field_meta",
    "logger",
  ],
};

const hookOnRunStartSpec: AdeFunctionSpec = {
  kind: "hook_on_run_start",
  name: "on_run_start",
  label: "ADE hook: on_run_start",
  signature: [
    "def on_run_start(",
    "    *,",
    "    run_id: str,",
    "    manifest: dict,",
    "    env: dict | None = None,",
    "    artifact: dict | None = None,",
    "    logger=None,",
    "    **_,",
    ") -> None:",
  ].join("\n"),
  doc: "Hook called once before detectors run. Use it for logging or lightweight setup.",
  snippet: `
def on_run_start(
    *,
    run_id: str,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    logger=None,
    **_,
) -> None:
    """\${1:Log or hydrate state before the run starts.}"""
    if logger:
        logger.info("run_start id=%s", run_id)
    return None
`.trim(),
  parameters: ["run_id", "manifest", "env", "artifact", "logger"],
};

const hookAfterMappingSpec: AdeFunctionSpec = {
  kind: "hook_after_mapping",
  name: "after_mapping",
  label: "ADE hook: after_mapping",
  signature: [
    "def after_mapping(",
    "    *,",
    "    table: dict,",
    "    manifest: dict,",
    "    env: dict | None = None,",
    "    logger=None,",
    "    **_,",
    ") -> dict:",
  ].join("\n"),
  doc: "Hook to tweak the materialized table after column mapping but before transforms/validators.",
  snippet: `
def after_mapping(
    *,
    table: dict,
    manifest: dict,
    env: dict | None = None,
    logger=None,
    **_,
) -> dict:
    """\${1:Adjust headers/rows before transforms run.}"""
    # Example: rename a header
    table["headers"] = [h if h != "Work Email" else "Email" for h in table["headers"]]
    return table
`.trim(),
  parameters: ["table", "manifest", "env", "logger"],
};

const hookBeforeSaveSpec: AdeFunctionSpec = {
  kind: "hook_before_save",
  name: "before_save",
  label: "ADE hook: before_save",
  signature: [
    "def before_save(",
    "    *,",
    "    workbook,",
    "    artifact: dict | None = None,",
    "    logger=None,",
    "    **_,",
    ") -> object:",
  ].join("\n"),
  doc: "Hook to polish the OpenPyXL workbook before it is written to disk.",
  snippet: `
def before_save(
    *,
    workbook,
    artifact: dict | None = None,
    logger=None,
    **_,
):
    """\${1:Style or summarize the workbook before it is saved.}"""
    ws = workbook.active
    ws.title = "Normalized"
    if logger:
        logger.info("before_save: rows=%s", ws.max_row)
    return workbook
`.trim(),
  parameters: ["workbook", "artifact", "logger"],
};

const hookOnRunEndSpec: AdeFunctionSpec = {
  kind: "hook_on_run_end",
  name: "on_run_end",
  label: "ADE hook: on_run_end",
  signature: [
    "def on_run_end(",
    "    *,",
    "    artifact: dict | None = None,",
    "    logger=None,",
    "    **_,",
    ") -> None:",
  ].join("\n"),
  doc: "Hook called once after the run completes. Inspect the artifact for summary metrics.",
  snippet: `
def on_run_end(
    *,
    artifact: dict | None = None,
    logger=None,
    **_,
) -> None:
    """\${1:Log a completion summary.}"""
    if logger:
        total_sheets = len((artifact or {}).get("sheets", []))
        logger.info("run_end: sheets=%s", total_sheets)
    return None
`.trim(),
  parameters: ["artifact", "logger"],
};

export const ADE_FUNCTIONS: AdeFunctionSpec[] = [
  rowDetectorSpec,
  columnDetectorSpec,
  columnTransformSpec,
  columnValidatorSpec,
  hookOnRunStartSpec,
  hookAfterMappingSpec,
  hookBeforeSaveSpec,
  hookOnRunEndSpec,
];

export type AdeFileScope = "row_detectors" | "column_detectors" | "hooks" | "other";

function normalizePath(filePath: string | undefined): string {
  if (!filePath) {
    return "";
  }
  return filePath.replace(/\\/g, "/").toLowerCase();
}

export function getFileScope(filePath: string | undefined): AdeFileScope {
  const normalized = normalizePath(filePath);
  if (normalized.includes("/row_detectors/")) {
    return "row_detectors";
  }
  if (normalized.includes("/column_detectors/")) {
    return "column_detectors";
  }
  if (normalized.includes("/hooks/")) {
    return "hooks";
  }
  return "other";
}

export function isAdeConfigFile(filePath: string | undefined): boolean {
  return getFileScope(filePath) !== "other";
}

const hookSpecsByName = new Map<string, AdeFunctionSpec>([
  [hookOnRunStartSpec.name, hookOnRunStartSpec],
  [hookAfterMappingSpec.name, hookAfterMappingSpec],
  [hookBeforeSaveSpec.name, hookBeforeSaveSpec],
  [hookOnRunEndSpec.name, hookOnRunEndSpec],
]);

export function getHoverSpec(word: string, filePath: string | undefined): AdeFunctionSpec | undefined {
  const scope = getFileScope(filePath);
  if (!word) {
    return undefined;
  }
  if (scope === "row_detectors" && word.startsWith("detect_")) {
    return rowDetectorSpec;
  }
  if (scope === "column_detectors") {
    if (word.startsWith("detect_")) {
      return columnDetectorSpec;
    }
    if (word === columnTransformSpec.name) {
      return columnTransformSpec;
    }
    if (word === columnValidatorSpec.name) {
      return columnValidatorSpec;
    }
  }
  if (scope === "hooks") {
    return hookSpecsByName.get(word);
  }
  return undefined;
}

export function getSnippetSpecs(filePath: string | undefined): AdeFunctionSpec[] {
  const scope = getFileScope(filePath);
  if (scope === "row_detectors") {
    return [rowDetectorSpec];
  }
  if (scope === "column_detectors") {
    return [columnDetectorSpec, columnTransformSpec, columnValidatorSpec];
  }
  if (scope === "hooks") {
    return Array.from(hookSpecsByName.values());
  }
  return [];
}
```

# apps/ade-web/src/ui/CodeEditor/index.ts
```typescript
export { CodeEditor } from "./CodeEditor";
export type { CodeEditorHandle, CodeEditorProps } from "./CodeEditor";
```

# apps/ade-web/src/ui/CodeEditor/registerAdeScriptHelpers.ts
```typescript
// /apps/ade-web/src/ui/CodeEditor/registerAdeScriptHelpers.ts

import type * as Monaco from "monaco-editor";

import type { AdeFunctionSpec } from "./adeScriptApi";
import { getHoverSpec, getSnippetSpecs, isAdeConfigFile } from "./adeScriptApi";

type Registration = {
  disposables: Monaco.IDisposable[];
  refCount: number;
};

const registrations = new Map<string, Registration>();

export function registerAdeScriptHelpers(
  monaco: typeof import("monaco-editor"),
  languageId = "python",
): void {
  const lang = languageId || "python";
  const existing = registrations.get(lang);
  if (existing) {
    existing.refCount += 1;
    return;
  }

  const disposables: Monaco.IDisposable[] = [
    registerHoverProvider(monaco, lang),
    registerCompletionProvider(monaco, lang),
    registerSignatureProvider(monaco, lang),
  ];

  registrations.set(lang, { disposables, refCount: 1 });
}

export function disposeAdeScriptHelpers(languageId = "python"): void {
  const lang = languageId || "python";
  const registration = registrations.get(lang);
  if (!registration) return;
  registration.refCount -= 1;
  if (registration.refCount <= 0) {
    registration.disposables.forEach((disposable) => disposable.dispose());
    registrations.delete(lang);
  }
}

/* ---------- Hover ---------- */

function registerHoverProvider(
  monaco: typeof import("monaco-editor"),
  languageId: string,
): Monaco.IDisposable {
  return monaco.languages.registerHoverProvider(languageId, {
    provideHover(model, position) {
      const filePath = getModelPath(model);
      if (!isAdeConfigFile(filePath)) return null;

      const word = model.getWordAtPosition(position);
      if (!word) return null;

      const spec = getHoverSpec(word.word, filePath);
      if (!spec) return null;

      const range = new monaco.Range(
        position.lineNumber,
        word.startColumn,
        position.lineNumber,
        word.endColumn,
      );

      return {
        range,
        contents: [
          { value: ["```python", spec.signature, "```"].join("\n") },
          { value: spec.doc },
        ],
      };
    },
  });
}

/* ---------- Completion: minimal, file-scoped, always on in ADE files ---------- */

function registerCompletionProvider(
  monaco: typeof import("monaco-editor"),
  languageId: string,
): Monaco.IDisposable {
  const EMPTY_COMPLETIONS = { suggestions: [] as Monaco.languages.CompletionItem[] };

  return monaco.languages.registerCompletionItemProvider(languageId, {
    // Helpful but not critical; Ctrl+Space always works
    triggerCharacters: [" ", "d", "t", "_"],

    provideCompletionItems(model, position) {
      const filePath = getModelPath(model);
      if (!isAdeConfigFile(filePath)) {
        return EMPTY_COMPLETIONS;
      }

      const specs = getSnippetSpecs(filePath);
      if (!specs || specs.length === 0) {
        return EMPTY_COMPLETIONS;
      }

      const lineNumber = position.lineNumber;
      const word = model.getWordUntilPosition(position);

      // If there's a current word, replace just that; otherwise replace from the caret.
      const range =
        word && word.word
          ? new monaco.Range(lineNumber, word.startColumn, lineNumber, word.endColumn)
          : new monaco.Range(lineNumber, position.column, lineNumber, position.column);

      const suggestions = specs.map((spec, index) =>
        createSnippetSuggestion(monaco, spec, range, index),
      );

      if (import.meta.env?.DEV) {
        console.debug("[ade-completions] ADE specs for file", {
          filePath,
          specs: specs.map((s) => s.name),
        });
        console.debug(
          "[ade-completions] ADE suggestions",
          suggestions.map((s) => s.label),
        );
      }

      return { suggestions };
    },
  });
}

/* ---------- Signature help ---------- */

function registerSignatureProvider(
  monaco: typeof import("monaco-editor"),
  languageId: string,
): Monaco.IDisposable {
  return monaco.languages.registerSignatureHelpProvider(languageId, {
    signatureHelpTriggerCharacters: ["(", ","],
    signatureHelpRetriggerCharacters: [","],
    provideSignatureHelp(model, position) {
      const filePath = getModelPath(model);
      if (!isAdeConfigFile(filePath)) {
        return null;
      }

      const lineContent = model.getLineContent(position.lineNumber);
      const prefix = lineContent.slice(0, position.column);
      const match = /([A-Za-z_][\w]*)\s*\($/.exec(prefix);
      if (!match) {
        return null;
      }

      const spec = getHoverSpec(match[1], filePath);
      if (!spec) {
        return null;
      }

      const activeParameter = computeActiveParameter(prefix);
      const parameters = spec.parameters.map((param) => ({ label: param }));

      return {
        value: {
          signatures: [
            {
              label: spec.signature,
              documentation: spec.doc,
              parameters,
            },
          ],
          activeSignature: 0,
          activeParameter: Math.min(
            Math.max(activeParameter, 0),
            Math.max(parameters.length - 1, 0),
          ),
        },
        dispose: () => {
          // nothing to clean up for one-off signature hints
        },
      };
    },
  });
}

/* ---------- Shared helpers ---------- */

function getModelPath(model: Monaco.editor.ITextModel | undefined): string | undefined {
  if (!model) return undefined;
  const uri = model.uri;
  if (!uri) return undefined;

  const rawPath = uri.path || uri.toString();
  if (!rawPath) return undefined;

  const normalized = rawPath.startsWith("/") ? rawPath.slice(1) : rawPath;

  if (import.meta.env?.DEV) {
    console.debug("[ade] getModelPath", { rawPath, normalized });
  }

  return normalized;
}

function computeActiveParameter(prefix: string): number {
  const parenIndex = prefix.lastIndexOf("(");
  if (parenIndex === -1) return 0;
  const argsSoFar = prefix.slice(parenIndex + 1);
  if (!argsSoFar.trim()) return 0;
  return argsSoFar.split(",").length - 1;
}

/* ---------- Snippet suggestion creation ---------- */

function createSnippetSuggestion(
  monaco: typeof import("monaco-editor"),
  spec: AdeFunctionSpec,
  range: Monaco.Range,
  index: number,
): Monaco.languages.CompletionItem {
  return {
    label: spec.label,
    kind: monaco.languages.CompletionItemKind.Snippet,
    insertText: spec.snippet,
    insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
    documentation: { value: spec.doc },
    detail: spec.signature,
    range,
    sortText: `0${index}`,
  };
}
```

# apps/ade-web/src/ui/ContextMenu/ContextMenu.tsx
```tsx
import { createPortal } from "react-dom";
import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";

import clsx from "clsx";

export interface ContextMenuItem {
  readonly id: string;
  readonly label: string;
  readonly onSelect: () => void;
  readonly shortcut?: string;
  readonly icon?: ReactNode;
  readonly disabled?: boolean;
  readonly danger?: boolean;
  readonly dividerAbove?: boolean;
}

export interface ContextMenuProps {
  readonly open: boolean;
  readonly position: { readonly x: number; readonly y: number } | null;
  readonly onClose: () => void;
  readonly items: readonly ContextMenuItem[];
  readonly appearance?: "light" | "dark";
}

const MENU_WIDTH = 232;
const MENU_ITEM_HEIGHT = 30;
const MENU_PADDING = 6;

export function ContextMenu({
  open,
  position,
  onClose,
  items,
  appearance = "dark",
}: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [coords, setCoords] = useState<{ x: number; y: number } | null>(null);
  const firstEnabledIndex = useMemo(
    () => items.findIndex((item) => !item.disabled),
    [items],
  );
  const [activeIndex, setActiveIndex] = useState(() =>
    firstEnabledIndex >= 0 ? firstEnabledIndex : 0,
  );

  useEffect(() => {
    if (!open || !position || typeof window === "undefined") {
      setCoords(null);
      return;
    }
    const estimatedHeight = items.length * MENU_ITEM_HEIGHT + MENU_PADDING * 2;
    const maxX = Math.max(
      MENU_PADDING,
      (window.innerWidth || 0) - MENU_WIDTH - MENU_PADDING,
    );
    const maxY = Math.max(
      MENU_PADDING,
      (window.innerHeight || 0) - estimatedHeight - MENU_PADDING,
    );
    const nextX = Math.min(Math.max(position.x, MENU_PADDING), maxX);
    const nextY = Math.min(Math.max(position.y, MENU_PADDING), maxY);
    setCoords({ x: nextX, y: nextY });
  }, [open, position, items.length]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setActiveIndex(firstEnabledIndex >= 0 ? firstEnabledIndex : 0);
  }, [open, firstEnabledIndex]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const target = itemRefs.current[activeIndex];
    target?.focus();
  }, [open, activeIndex]);

  useEffect(() => {
    if (!open || typeof window === "undefined") {
      return;
    }
    const handlePointerDown = (event: MouseEvent) => {
      if (!menuRef.current) {
        return;
      }
      if (!menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    const handleContextMenu = (event: MouseEvent) => {
      if (!menuRef.current) {
        return;
      }
      if (menuRef.current.contains(event.target as Node)) {
        event.preventDefault();
        return;
      }
      onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const direction = event.key === "ArrowDown" ? 1 : -1;
        setActiveIndex((current) => {
          if (items.length === 0) {
            return current;
          }
          let next = current;
          for (let i = 0; i < items.length; i += 1) {
            next = (next + direction + items.length) % items.length;
            if (!items[next]?.disabled) {
              return next;
            }
          }
          return current;
        });
        return;
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        const item = items[activeIndex];
        if (item && !item.disabled) {
          item.onSelect();
          onClose();
        }
      }
    };
    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("contextmenu", handleContextMenu);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("contextmenu", handleContextMenu);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose, items, activeIndex]);

  if (!open || !position || typeof window === "undefined" || !coords) {
    return null;
  }

  const palette =
    appearance === "dark"
      ? {
          bg: "bg-[#1f1f1f] text-[#f3f3f3]",
          border: "border-[#3c3c3c]",
          shadow: "shadow-[0_12px_28px_rgba(0,0,0,0.55)]",
          item: "hover:bg-[#094771] focus-visible:bg-[#094771]",
          disabled: "text-[#7a7a7a]",
          danger: "text-[#f48771] hover:text-white hover:bg-[#be1a1a] focus-visible:bg-[#be1a1a]",
          shortcut: "text-[#9f9f9f]",
          separator: "border-[#3f3f3f]",
        }
      : {
          bg: "bg-[#fdfdfd] text-[#1f1f1f]",
          border: "border-[#cfcfcf]",
          shadow: "shadow-[0_12px_28px_rgba(0,0,0,0.15)]",
          item: "hover:bg-[#dfe9f6] focus-visible:bg-[#dfe9f6]",
          disabled: "text-[#9c9c9c]",
          danger: "text-[#b02020] hover:bg-[#fde7e7] focus-visible:bg-[#fde7e7]",
          shortcut: "text-[#6d6d6d]",
          separator: "border-[#e0e0e0]",
        };

  return createPortal(
    <div
      ref={menuRef}
      role="menu"
      className={clsx(
        "z-[60] min-w-[200px] rounded-sm border backdrop-blur-sm",
        palette.bg,
        palette.border,
        palette.shadow,
      )}
      style={{ top: coords.y, left: coords.x, position: "fixed" }}
    >
      <ul className="py-1" role="none">
        {items.map((item, index) => {
          const disabled = Boolean(item.disabled);
          const danger = Boolean(item.danger);
          return (
            <Fragment key={item.id}>
              {item.dividerAbove ? (
                <li role="separator" className={clsx("mx-2 my-1 border-t", palette.separator)} />
              ) : null}
              <li role="none">
                <button
                  ref={(node) => {
                    itemRefs.current[index] = node;
                  }}
                  type="button"
                  role="menuitem"
                  className={clsx(
                    "flex w-full items-center justify-between gap-6 px-3 py-1.5 text-[13px] leading-5 outline-none transition",
                    palette.item,
                    disabled && palette.disabled,
                    danger && !disabled && palette.danger,
                    disabled && "cursor-default",
                  )}
                  onClick={(event: ReactMouseEvent<HTMLButtonElement>) => {
                    event.stopPropagation();
                    if (disabled) {
                      return;
                    }
                    item.onSelect();
                    onClose();
                  }}
                  onMouseEnter={() => {
                    if (!disabled) {
                      setActiveIndex(index);
                    }
                  }}
                  disabled={disabled}
                >
                  <span className="flex min-w-0 items-center gap-3">
                    {item.icon ? (
                      <span className="text-base opacity-80">{item.icon}</span>
                    ) : (
                      <span className="inline-block h-4 w-4" />
                    )}
                    <span className="truncate">{item.label}</span>
                  </span>
                  {item.shortcut ? (
                    <span className={clsx("text-[11px] uppercase tracking-wide", palette.shortcut)}>
                      {item.shortcut}
                    </span>
                  ) : null}
                </button>
              </li>
            </Fragment>
          );
        })}
      </ul>
    </div>,
    window.document.body,
  );
}
```

# apps/ade-web/src/ui/ContextMenu/index.ts
```typescript
export type { ContextMenuItem, ContextMenuProps } from "./ContextMenu";
export { ContextMenu } from "./ContextMenu";
```

# apps/ade-web/src/ui/FormField/FormField.tsx
```tsx
import clsx from "clsx";
import { cloneElement, isValidElement, useId } from "react";
import type { ReactElement, ReactNode } from "react";

export type ControlProps = {
  id?: string;
  required?: boolean;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean | "true" | "false";
};

export type ControlElement = ReactElement<ControlProps>;

export interface FormFieldProps {
  readonly label?: ReactNode;
  readonly hint?: ReactNode;
  readonly error?: ReactNode;
  readonly required?: boolean;
  readonly children: ControlElement | ReactNode;
  readonly className?: string;
}

export function FormField({
  label,
  hint,
  error,
  required = false,
  children,
  className,
}: FormFieldProps) {
  const generatedId = useId();
  const childProps = isValidElement(children) ? children.props ?? {} : {};
  const controlId = (childProps as ControlProps).id ?? generatedId;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [hintId, errorId, childProps["aria-describedby"]]
    .filter(Boolean)
    .join(" ") || undefined;

  return (
    <div className={clsx("space-y-2", className)}>
      {label ? (
        <label
          htmlFor={controlId}
          className="text-sm font-medium text-slate-700"
          aria-required={required || undefined}
        >
          {label}
          {required ? (
            <span className="ml-1 text-danger-600" aria-hidden="true">
              *
            </span>
          ) : null}
        </label>
      ) : null}
      {isValidElement(children)
        ? cloneElement(children as ControlElement, {
            id: controlId,
            required: required || (childProps as ControlProps).required,
            "aria-describedby": describedBy,
            "aria-invalid": error ? true : (childProps as ControlProps)["aria-invalid"],
          })
        : children}
      {hint ? (
        <p id={hintId} className="text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs font-medium text-danger-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}
```

# apps/ade-web/src/ui/FormField/index.ts
```typescript
export { FormField } from "./FormField";
export type { FormFieldProps } from "./FormField";
```

# apps/ade-web/src/ui/Input/Input.tsx
```tsx
import clsx from "clsx";
import { forwardRef } from "react";
import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

const BASE_CLASS =
  "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  readonly invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid = false, ...props }, ref) => (
    <input
      ref={ref}
      className={clsx(BASE_CLASS, invalid && "border-danger-500 focus-visible:ring-danger-500", className)}
      aria-invalid={invalid || undefined}
      {...props}
    />
  ),
);

Input.displayName = "Input";

export interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  readonly invalid?: boolean;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ className, invalid = false, rows = 4, ...props }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      className={clsx(
        BASE_CLASS,
        "resize-y",
        invalid && "border-danger-500 focus-visible:ring-danger-500",
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  ),
);

TextArea.displayName = "TextArea";
```

# apps/ade-web/src/ui/Input/index.ts
```typescript
export { Input, TextArea } from "./Input";
export type { InputProps, TextAreaProps } from "./Input";
```

# apps/ade-web/src/ui/Select/Select.tsx
```tsx
import clsx from "clsx";
import { forwardRef } from "react";
import type { SelectHTMLAttributes } from "react";

const BASE_CLASS =
  "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900 shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500";

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, ...props }, ref) => (
    <select ref={ref} className={clsx(BASE_CLASS, className)} {...props} />
  ),
);

Select.displayName = "Select";
```

# apps/ade-web/src/ui/Select/index.ts
```typescript
export { Select } from "./Select";
export type { SelectProps } from "./Select";
```

# apps/ade-web/src/ui/SplitButton/SplitButton.tsx
```tsx
import clsx from "clsx";
import { useRef } from "react";
import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";

const BASE_PRIMARY =
  "inline-flex items-center gap-2 rounded-l-md px-3 py-1.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0 disabled:cursor-not-allowed";
const BASE_MENU =
  "inline-flex items-center justify-center rounded-r-md border-l px-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0 disabled:cursor-not-allowed";

export interface SplitButtonProps {
  readonly label: ReactNode;
  readonly icon?: ReactNode;
  readonly disabled?: boolean;
  readonly isLoading?: boolean;
  readonly highlight?: boolean;
  readonly className?: string;
  readonly primaryClassName?: string;
  readonly menuClassName?: string;
  readonly title?: string;
  readonly menuAriaLabel?: string;
  readonly menuIcon?: ReactNode;
  readonly onPrimaryClick?: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  readonly onOpenMenu?: (position: { x: number; y: number }) => void;
  readonly onContextMenu?: (event: ReactMouseEvent<HTMLDivElement>) => void;
}

export function SplitButton({
  label,
  icon,
  disabled,
  isLoading,
  highlight,
  className,
  primaryClassName,
  menuClassName,
  title,
  menuAriaLabel = "Open menu",
  menuIcon = <SplitButtonChevronIcon />,
  onPrimaryClick,
  onOpenMenu,
  onContextMenu,
}: SplitButtonProps) {
  const menuButtonRef = useRef<HTMLButtonElement | null>(null);
  const isDisabled = Boolean(disabled || isLoading);

  const handleMenuClick = (event: ReactMouseEvent<HTMLButtonElement>) => {
    if (isDisabled) {
      return;
    }
    event.preventDefault();
    const rect = menuButtonRef.current?.getBoundingClientRect();
    if (rect) {
      onOpenMenu?.({ x: rect.left, y: rect.bottom });
      return;
    }
    onOpenMenu?.({ x: event.clientX, y: event.clientY });
  };

  return (
    <div
      role="group"
      className={clsx(
        "inline-flex items-stretch rounded-md shadow-sm",
        highlight && "ring-2 ring-amber-300/70 ring-offset-2 ring-offset-transparent",
        className,
      )}
      onContextMenu={onContextMenu}
    >
      <button
        type="button"
        title={title}
        disabled={isDisabled}
        className={clsx(BASE_PRIMARY, primaryClassName)}
        onClick={(event) => {
          if (isDisabled) {
            return;
          }
          onPrimaryClick?.(event);
        }}
      >
        {icon}
        <span className="whitespace-nowrap">{label}</span>
      </button>
      <button
        ref={menuButtonRef}
        type="button"
        aria-label={menuAriaLabel}
        aria-haspopup="menu"
        aria-expanded="false"
        disabled={isDisabled}
        className={clsx(BASE_MENU, menuClassName)}
        onClick={handleMenuClick}
      >
        {menuIcon}
      </button>
    </div>
  );
}

function SplitButtonChevronIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
```

# apps/ade-web/src/ui/SplitButton/index.ts
```typescript
export { SplitButton } from "./SplitButton";
export type { SplitButtonProps } from "./SplitButton";
```

# apps/ade-web/src/ui/Tabs/Tabs.tsx
```tsx
import {
  createContext,
  useCallback,
  useContext,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  type HTMLAttributes,
  type PropsWithChildren,
  type ButtonHTMLAttributes,
  type KeyboardEvent,
} from "react";

interface TabsContextValue {
  readonly value: string;
  readonly setValue: (value: string) => void;
  readonly baseId: string;
  readonly registerValue: (value: string, element: HTMLButtonElement | null) => void;
  readonly unregisterValue: (value: string) => void;
  readonly focusValue: (value: string | undefined) => void;
  readonly getValues: () => string[];
}

const TabsContext = createContext<TabsContextValue | null>(null);

export interface TabsRootProps extends PropsWithChildren {
  readonly value: string;
  readonly onValueChange: (value: string) => void;
}

export function TabsRoot({ value, onValueChange, children }: TabsRootProps) {
  const baseId = useId();
  const valuesRef = useRef<string[]>([]);
  const nodesRef = useRef(new Map<string, HTMLButtonElement | null>());

  const registerValue = useCallback((val: string, element: HTMLButtonElement | null) => {
    if (!valuesRef.current.includes(val)) {
      valuesRef.current.push(val);
    }
    nodesRef.current.set(val, element);
  }, []);

  const unregisterValue = useCallback((val: string) => {
    valuesRef.current = valuesRef.current.filter((entry) => entry !== val);
    nodesRef.current.delete(val);
  }, []);

  const focusValue = useCallback((val: string | undefined) => {
    if (!val) {
      return;
    }
    nodesRef.current.get(val)?.focus();
  }, []);

  const getValues = useCallback(() => valuesRef.current.slice(), []);

  const contextValue = useMemo(
    () => ({
      value,
      setValue: onValueChange,
      baseId,
      registerValue,
      unregisterValue,
      focusValue,
      getValues,
    }),
    [value, onValueChange, baseId, registerValue, unregisterValue, focusValue, getValues],
  );

  return <TabsContext.Provider value={contextValue}>{children}</TabsContext.Provider>;
}

export function TabsList({ children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div role="tablist" {...rest}>
      {children}
    </div>
  );
}

export interface TabsTriggerProps extends PropsWithChildren, ButtonHTMLAttributes<HTMLButtonElement> {
  readonly value: string;
}

export function TabsTrigger({ value, children, className, onClick, onKeyDown, disabled, ...rest }: TabsTriggerProps) {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error("TabsTrigger must be used within a TabsRoot");
  }

  const { registerValue, unregisterValue, focusValue, getValues } = context;
  const selected = context.value === value;
  const id = `${context.baseId}-tab-${value}`;
  const panelId = `${context.baseId}-panel-${value}`;

  const setButtonRef = useCallback(
    (node: HTMLButtonElement | null) => {
      registerValue(value, node);
    },
    [registerValue, value],
  );

  useLayoutEffect(() => () => unregisterValue(value), [unregisterValue, value]);

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    onKeyDown?.(event);
    if (event.defaultPrevented) {
      return;
    }

    const values = getValues();
    const currentIndex = values.indexOf(value);
    if (currentIndex === -1 || values.length === 0) {
      return;
    }

    let nextIndex = currentIndex;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      nextIndex = (currentIndex + 1) % values.length;
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      nextIndex = (currentIndex - 1 + values.length) % values.length;
    } else if (event.key === "Home") {
      event.preventDefault();
      nextIndex = 0;
    } else if (event.key === "End") {
      event.preventDefault();
      nextIndex = values.length - 1;
    }

    const nextValue = values[nextIndex];
    if (nextValue && nextValue !== context.value) {
      context.setValue(nextValue);
    }
    focusValue(nextValue);
  };

  return (
    <button
      {...rest}
      ref={setButtonRef}
      type="button"
      role="tab"
      id={id}
      aria-selected={selected}
      aria-controls={panelId}
      tabIndex={selected ? 0 : -1}
      className={className}
      disabled={disabled}
      onKeyDown={handleKeyDown}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented && !disabled) {
          context.setValue(value);
        }
      }}
    >
      {children}
    </button>
  );
}

export interface TabsContentProps extends PropsWithChildren, HTMLAttributes<HTMLDivElement> {
  readonly value: string;
}

export function TabsContent({ value, children, className, ...rest }: TabsContentProps) {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error("TabsContent must be used within a TabsRoot");
  }

  const selected = context.value === value;
  const id = `${context.baseId}-panel-${value}`;
  const tabId = `${context.baseId}-tab-${value}`;

  return (
    <div
      {...rest}
      role="tabpanel"
      id={id}
      aria-labelledby={tabId}
      className={className}
      hidden={!selected}
      tabIndex={0}
    >
      {children}
    </div>
  );
}
```

# apps/ade-web/src/ui/Tabs/index.ts
```typescript
export { TabsRoot, TabsList, TabsTrigger, TabsContent } from "./Tabs";
export type { TabsRootProps, TabsTriggerProps, TabsContentProps } from "./Tabs";
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
