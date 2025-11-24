# Logical module layout (source -> sections below):
# - apps/ade-web/README.md - ADE Web
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
# ADE Web

ADE Web is the browser-based front‑end for the Automatic Data Extractor (ADE) platform.

It gives two main personas a single place to work:

- **Workspace owners / engineers** – define and evolve config packages (Python packages) that describe how documents are processed, manage safe mode, and administer workspaces, users, and SSO.
- **End users / analysts** – upload documents, run extractions, monitor progress, inspect logs and telemetry, and download structured outputs.

This document describes **what** ADE Web does and how it should behave in an ideal implementation. It is intentionally backend‑agnostic and should be treated as the product‑level specification for the ADE Web UI and its contracts with the backend.

---

## High‑level UX & layout

ADE Web has two major “layers”:

1. **Workspace directory** – finding and creating workspaces.
2. **Workspace shell** – working inside a specific workspace (Documents, Jobs, Config Builder, Settings).

Both layers share a consistent structure:

- A **global top bar** with:
  - Brand/context (e.g. “Workspace directory” or current workspace name on mobile),
  - A **search box** (scope depends on context),
  - A user avatar and menu (profile, sign‑out, etc.).
- A main content area that adapts between desktop and mobile.

### Workspace directory layout

The **Workspace directory** (`/workspaces`) is the entry point after sign‑in:

- Top bar brand:
  - “Workspace directory”
  - Subtitle “Automatic Data Extractor”.
- A **search box** for workspaces:
  - Keyboard shortcut hint (e.g. `⌘K` / `Ctrl+K`),
  - Suggestions (top matching workspaces),
  - Pressing Enter jumps to the best match.
- Optional **actions**:
  - “Create workspace” for users with `Workspaces.Create` permission.
- Main content:
  - Either:
    - An **empty state** inviting the user to create their first workspace, or
    - A **card grid** of visible workspaces, each showing:
      - Workspace name,
      - Slug,
      - A “Default” badge (for the user’s default workspace),
      - The permissions the user has in that workspace (e.g. Owner, Runner, Viewer).

A right‑hand side panel offers guidance:

- **Workspace tips** (why multiple workspaces, how to structure them).
- A **setup checklist** (invite admins, review configs before production, etc.).

### Workspace shell layout

Inside a workspace (`/workspaces/:workspaceId/...`), ADE Web presents a **workspace shell**:

- **Left navigation (desktop)**:
  - A workspace card showing initials, name, and “Switch workspace”.
  - A collapsible primary nav, with items:
    - Documents
    - Jobs
    - Config Builder
    - Workspace Settings
  - Collapse/expand state is persisted **per workspace**.

- **Top bar**:
  - On desktop:
    - A search box whose **scope** depends on the current section:
      - In **Documents**, the search box filters documents.
      - Elsewhere, it searches within the workspace and lets you jump to sections.
    - A user **Profile dropdown** (display name + email, sign‑out, etc.).
  - On mobile:
    - A **menu button** opens a slide‑in navigation panel for workspace sections.

- **Main content**:
  - The current section’s content (Documents, Jobs, Config Builder, Settings).
  - A **safe mode banner** at the top of the content area when safe mode is active.
  - A **notifications layer** (toasts) for feedback on actions.

- **Immersive mode (Config Builder)**:
  - Certain Config Builder routes use a full‑height, “workbench” layout.
  - When the workbench is **maximised**, the workspace nav and top bar disappear to give a distraction‑free editing experience.
  - An internal window state tracks when the workbench is maximised/minimised.

On mobile, opening the workspace nav:

- Shows a **slide‑in panel** with sections and workspace name.
- Locks body scroll while the panel is open.
- Lets you close with a close button, tapping outside, or navigating.

---

## Core concepts

### Workspaces

A **workspace** is the primary unit of organisation in ADE:

- Isolates **documents**, **runs**, **config packages**, and **access control**.
- Has a human‑readable **name** and stable **slug/ID** that appear in the UI and URLs.
- Has **one active config version** at any point for “normal” runs.
- Is governed by **safe mode** and **role‑based access control (RBAC)**.
- May have a **default** flag for each user, used as their preferred workspace.

Users sign in, land on the **Workspace directory**, and then select (or create) a workspace before they can work with documents or configs.

---

### Documents

A **document** is any input you feed into ADE:

- Typically:
  - Spreadsheets (e.g., XLSX),
  - CSV/TSV files,
  - Other supported tabular or semi‑structured formats.

Per workspace:

- Documents are **uploaded into** and **owned by** that workspace.
- Each document has:
  - A **name** (often the filename),
  - A **type** (e.g., XLSX, CSV),
  - Optional **tags** (e.g., client, period),
  - A history of **runs**.
- Documents are **immutable inputs**:
  - Uploading a revised file creates a **new document**.
  - Runs always refer to the original upload.

---

### Runs (jobs)

A **run** is a single execution of ADE against a specific input using a specific config version.

Conceptually:

- Runs are always **scoped to a workspace**, and generally to a **document**.
- Each run includes:
  - **Status**: `queued → running → succeeded / failed / canceled`,
  - **Timestamps**: created / started / completed,
  - **Triggering user**,
  - **Config version** used,
  - Links to **output artifacts** (CSV/JSON/other),
  - **Logs and telemetry** (via NDJSON streams).

Runs surface in:

- **Documents** (per‑document history and details),
- **Jobs** (workspace‑wide monitoring and auditing).

The backend exposes **streaming APIs** (NDJSON):

- ADE Web consumes these streams so that status, logs, and telemetry update **in real time** while a job is running.
- Completed runs can replay the same event stream for consistent run history.

---

### Config packages & versions

A **config package** is a Python package that tells ADE how to interpret, validate, and extract data for a workspace.

Key ideas:

- A workspace may hold **one or more config packages** (e.g. pipelines, client variants).
- Each config package is versioned into **config versions**.
- At any time, the workspace has **one active config version** that is used for standard runs.
- Each config version comprises:
  - Python package code,
  - Configuration and schema files,
  - A **manifest** describing output columns and table‑level behaviour,
  - Optional scripts (transforms, validators, helpers).

For simplicity, user‑facing docs emphasise three statuses:

- **Draft**
  - Editable in the Config Builder.
  - Supports:
    - File/script editing,
    - Manifest editing,
    - Builds, validations, test runs.
- **Active**
  - Exactly **one active version per workspace** for “normal” runs.
  - Treated as **read‑only** in the UI.
- **Inactive**
  - Older versions, kept for history and rollback.
  - Not used for new runs unless cloned into a new draft.

Internally, backends may support extra states (published, archived, deleted) but the primary UI contract is the `draft → active → inactive` lifecycle.

---

### Manifest & schema

Each config version has a **manifest** that describes the expected outputs and table behaviour:

- **Columns**:
  - `key` – stable identifier,
  - `label` – human‑friendly name,
  - `path` – where the value comes from in extracted data,
  - `ordinal` – ordering,
  - `required` – whether the column must be present,
  - `enabled` – whether the column is included in outputs,
  - `depends_on` – optional dependencies on other columns.
- **Table section**:
  - Optional `transform` script path,
  - Optional `validators` script path.

ADE Web:

- Parses the manifest into a structured representation,
- Surfaces it in the Config Builder for:
  - Column reordering,
  - Toggling enabled/disabled,
  - Toggling required flags,
  - Inspecting or editing transform/validator hooks.
- Sends **manifest patches** to the backend, preserving unknown fields so forward compatibility is maintained.

---

### Safe mode

ADE includes a **safe mode** mechanism as a kill switch for engine execution:

- When **safe mode is enabled**:
  - New runs, builds, and test runs are blocked.
  - Read‑only operations still work:
    - Viewing documents,
    - Inspecting runs and logs,
    - Downloading existing artifacts.
- Safe mode is **system‑scoped**, with an optional extension to workspace scope (ideal behaviour):
  - Backends expose a system‑wide `enabled` flag and human‑readable `detail` message.
  - Workspace settings may surface additional per‑workspace controls.

In the UI:

- A **global banner** shows when safe mode is active, reusing the backend’s message or a sensible default.
- Workspace‑level actions that execute the engine (Run, Build, Test, Activate) are disabled with tooltips explaining why.
- Authorised users see safe mode controls under Settings.

---

### Roles & permissions

ADE Web is designed around **workspace‑scoped RBAC**:

- Users have roles per workspace (e.g. Owner, Maintainer, Runner, Viewer).
- Roles govern capabilities such as:
  - Creating/deleting **workspaces**,
  - Managing **members** and roles,
  - Toggling **safe mode**,
  - Editing and activating **config versions**,
  - Running **builds/test runs**,
  - Triggering **document runs**,
  - Viewing **logs and telemetry**.

Permissions are enforced by the backend; ADE Web only:

- Reads the user’s roles/permissions,
- Enables/disables or hides UI controls accordingly,
- Uses feature flags like `Workspaces.Create` or `Users.Read.All` as hints for what to show.

---

### Authentication, SSO & first‑time setup

Authentication is handled centrally by ADE’s backend.

#### First‑run setup

On a fresh deployment:

- A **Setup status** endpoint indicates that setup is required.
- ADE Web routes users to `/setup` where they:
  - Configure the first admin account,
  - Optionally configure or select SSO providers,
  - Complete the initial bootstrap.
- After successful setup, ADE Web:
  - Establishes a session,
  - Redirects to `/workspaces` (or another safe default).

If setup is not required, `/setup` behaves like a protected route and redirects to the app.

#### Login & SSO

Normal sign‑in uses `/login`:

- ADE Web calls an **auth providers** API to list:
  - Local login (if enabled),
  - SSO providers (id + label + optional icon),
  - Whether `force_sso` is true.
- When `force_sso` is true:
  - The UI either hides the local form or drives directly into SSO.
- Unaudited or unsafe `redirectTo` parameters are sanitised:
  - Only internal, single‑origin paths are honoured.
  - Auth callbacks and setup flows also sanitise redirect destinations.

Redirect behaviour:

1. Use a `return_to` field from the session (if set),
2. Else, use a validated `redirectTo` query parameter from the URL,
3. Else, send the user to the default app home (`/workspaces`).

---

## Routes & navigation model

ADE Web runs as a **single‑page app** with a lightweight custom navigation layer.

### Top‑level routes

- `/` – Entry point; decides where to send the user (login, setup, or app).
- `/login` – Sign‑in and auth provider selection.
- `/auth/callback` – Auth provider callback handler.
- `/setup` – First‑time setup flow.
- `/logout` – Logout screen.
- `/workspaces` – Workspace directory.
- `/workspaces/new` – Create workspace.
- `/workspaces/:workspaceId` – Workspace shell (Documents, Jobs, Config Builder, Settings).
- Any other path – Not found.

Within `/workspaces/:workspaceId`, the first path segment after the workspace ID selects the section:

- `/documents` – Documents list and document details.
- `/jobs` – Jobs list.
- `/config-builder` – Config overview and details:
  - `/config-builder/:configId` – Config details (metadata, versions, etc.).
  - `/config-builder/:configId/editor` – Full workbench editor for that config.
- `/settings` – Workspace settings.
- `/overview` – Optional overview/summary section.
- Legacy `/configs/...` paths are redirected into `/config-builder/...`.

### Navigation behaviour

ADE Web uses a `NavProvider` based on the browser `history` API:

- `Link` intercepts clicks and performs SPA navigation unless the user explicitly opens links in a new tab/window (Ctrl/⌘/Shift/Alt clicks).
- `NavLink` knows whether it is “active” (either exact match or prefix match) and can render:
  - Different classes,
  - Different children,
  - Based on the `isActive` flag.

A **navigation blocker** mechanism allows screens to intercept transitions:

- For example, the Config Builder can register a blocker when there are unsaved edits.
- Navigation attempts (including back/forward) are turned into “intents” that blockers can veto.
- If vetoed, the app returns the user to the current URL.

---

### URL state & search parameters

ADE Web encodes important state into the URL to make views shareable and recoverable on refresh.

Generic helpers:

- Convert JS objects or tuples into `URLSearchParams`.
- Provide utilities to:
  - Read a single parameter by key,
  - Apply a patch (set/remove params) and build a new URL,
  - Override search params in nested components.

Important uses of URL state:

- **Documents list** – for example:
  - `q` – free‑text search across document names.
  - Pagination and sorting parameters (ideal behaviour).
- **Config Builder** – see below.
- **Auth flows** – `redirectTo` for post‑login routing.

#### Config Builder search state

The Config Builder persists its layout and file selection in the URL:

- `tab` – primary tab (currently `editor`).
- `pane` – bottom panel (`console` or `validation`/`problems`).
- `console` – whether the bottom panel is `open` or `closed`.
- `view` – layout mode:
  - `editor` – editor‑only,
  - `split` – editor + console,
  - `zen` – minimal, editor‑focused view.
- `file` (or legacy `path`) – currently open file or script.

Helpers:

- **Read**: parse all relevant parameters into a `ConfigBuilderSearchState`, with flags indicating which were explicitly present.
- **Merge**: apply a patch to the current state and serialise to the URL, only persisting non‑default values.

This makes it possible to:

- Bookmark a specific config version and file with the console open in validation mode.
- Share a URL that opens the Builder in exactly the layout you see.
- Refresh without losing your place.

---

## Workspace directory & creation

### Workspace directory (`/workspaces`)

The workspace directory presents:

- A **search box** for workspaces:
  - Filters workspaces by name and slug.
  - Keyboard shortcut (platform‑aware) to focus the search.
  - Suggestions for the most relevant workspaces; selecting a suggestion jumps to that workspace.
- Optional **“Create workspace”** button:
  - Shown only to users with the right permission (e.g. `Workspaces.Create`).

Main content varies depending on data:

- **No workspaces & can create**:
  - An empty‑state card encouraging workspace creation.
- **No workspaces & cannot create**:
  - An informational empty state explaining that the user needs to be added to a workspace.
- **Workspaces available**:
  - A **card grid**, each card linking to:
    - `/workspaces/:id/documents` (the default workspace section).
  - Each card shows:
    - Name,
    - Slug,
    - “Default” badge (if applicable),
    - A comma‑separated list of permissions/roles.

### Create workspace (`/workspaces/new`)

The **Create workspace** form is available to authenticated users (and only fully unlocked for users with certain permissions).

Form fields:

- **Workspace name**:
  - Required, length‑limited.
- **Workspace slug**:
  - Required, lowercase and URL‑safe.
  - Automatically **slugified from the name** until the slug field is manually edited:
    - Lowercases the name,
    - Replaces non‑alphanumeric characters with `-`,
    - Trims leading/trailing dashes,
    - Enforces a max length.
- **Workspace owner** (optional):
  - Only shown when the user has permission to read the user directory (e.g. `Users.Read.All`).
  - Defaults to the current user.
  - Dropdown of users (paged with a “Load more users…” button).
  - If the owner field is available and cleared, the form will require an owner to be selected.

Validation:

- Client‑side validation:
  - Name and slug required,
  - Slug pattern (lowercase letters, numbers, dashes).
- Server‑side validation:
  - Name and slug uniqueness errors are displayed inline,
  - Any field‑specific API errors are mapped to their respective inputs,
  - A generic root error covers non‑field issues.

On successful creation:

- The user is redirected to `/workspaces/:id` (which immediately normalises to the workspace’s default section).

---

## Workspace shell sections

Within a workspace, the shell is driven by the URL and the workspace nav.

### Documents

The **Documents** section is where analysts and operators run extractions.

#### Document list

A **paginated, filterable table** of documents:

- Columns:
  - Name,
  - Type,
  - Tags,
  - Last run status,
  - Last run time,
  - Last run triggered by.
- Filters and search:
  - Free‑text search (driven by `q` query param),
  - Type/tag filters (ideal behaviour),
  - Time‑window filter for “recently used” documents.

The top‑bar search switches to a **document‑scoped search** when you’re on the Documents section.

#### Uploading documents

From the Documents section, users can:

- Upload via an **Upload** button and/or drag‑and‑drop area.
- See:
  - Upload progress,
  - Errors for unsupported types, size limits, or server errors.

On success:

- A new document is created in the workspace.
- It appears in the table.
- It becomes immediately eligible for runs.

#### Document details & runs

Selecting a document opens a **details view** (panel or dedicated screen) showing:

- Metadata:
  - Name, type, size,
  - Uploaded by, uploaded at,
  - Tags / other editable metadata.
- Latest run status:
  - Status, duration,
  - Config version used,
  - Output links.

Actions:

- **Run** – start an extraction run for this document.
- **View runs** – open a per‑document run history view (Document Runs Drawer).

Safe mode:

- When safe mode is active, the **Run** action is disabled.
- Tooltips and inline messaging explain why.

#### Document Runs Drawer

The **Document Runs Drawer** shows recent runs for the selected document:

- Each run shows:
  - Status,
  - Start/complete times,
  - Triggering user,
  - Config version used.
- Selecting a run shows:
  - Live or replayed logs (NDJSON),
  - Telemetry (e.g. rows processed, warnings),
  - Links to output files.

This drawer is designed as a **single console** for that document: upload, run, watch, debug, and download, all in one place.

---

### Jobs

The **Jobs** section is a workspace‑wide view of recent and running jobs.

#### Jobs list

A **chronological table** of runs:

- Columns:
  - Run ID,
  - Document,
  - Status,
  - Start/completion timestamps,
  - Duration,
  - User,
  - Config version.
- Filters:
  - Status (running/succeeded/failed/canceled),
  - Time window,
  - Document,
  - Config version,
  - User.

#### Job details & logs

Selecting a job opens a detailed view:

- **Streamed logs**:
  - NDJSON events, interleaving log lines, run lifecycle events, and telemetry.
- **Telemetry**:
  - Structured counters (rows processed, warnings, etc.).
- **Artifacts**:
  - Listing and downloads for output files.

This view supports:

- Incident response and debugging,
- Auditing,
- Export of job summaries (ideal behaviour).

---

### Config Builder

The **Config Builder** is a first‑class IDE‑style environment inside ADE Web.

#### Goals

- Make it obvious that a **config is a Python package**.
- Provide a familiar IDE layout:
  - Explorer, editor, inspector, console.
- Support an integrated workflow:
  - Edit → Build/Validate → Test → Inspect → Activate.

#### Layout

The Config Builder workbench has four main areas:

1. **Explorer (left)**
   - Shows the config package file tree:
     - Python modules,
     - Config files,
     - Scripts referenced from the manifest,
     - Assets and helpers.
   - For draft versions:
     - Create, rename, and delete files and folders.
   - Switch between config packages and config versions.

2. **Editor (center)**
   - Multi‑tab code editor with:
     - Syntax highlighting,
     - Save shortcuts,
     - Keyboard navigation.
   - Only **draft** versions are editable.
   - Uses optimistic concurrency with ETags (or equivalent) to avoid overwrites.

3. **Inspector (right)**
   - Shows config and version metadata:
     - Name, ID, semantic version,
     - Status (draft/active/inactive),
     - Created/updated/activated at,
     - Who created/activated it.
   - Actions:
     - Activate draft,
     - Clone versions (from active/inactive),
     - Archive/restore (ideal behaviour).
   - Manifest view:
     - Column list with key/label/required/enabled/order,
     - Table transform/validator references.

4. **Console (bottom)**
   - Streams:
     - Build steps and results,
     - Validation errors,
     - Test‑run logs and telemetry.
   - Tabbed (e.g. “Build”, “Test run”, “Validation”).
   - Open/closed state encoded in the URL.

#### View modes & URL state

The workbench supports layout modes:

- `editor` – standard view,
- `split` – editor + console,
- `zen` – editor‑focused.

Combined with `pane` (`console`/`validation`) and `console` (`open`/`closed`), these settings are persisted in the URL via query parameters, along with the current `file`. This enables:

- Deep linking into a specific file and console state,
- Stable state across browser refreshes,
- Shareable Builder URLs.

#### Versions, builds & test runs

From the Config Builder, workspace owners can:

- **Create drafts**:
  - New blank versions from templates,
  - Clones of the current active version (for iteration),
  - Clones of inactive versions (for rollback).
- **Edit drafts**:
  - Modify files/scripts/manifest.
- **Validate & build**:
  - Trigger a build pipeline:
    - Install dependencies,
    - Import config modules,
    - Gather metadata.
  - Watch NDJSON events in the console.
- **Run tests**:
  - Run draft versions against sample documents:
    - Optional sheet selection and options (`dry_run`, `validate_only`).
  - Stream logs and telemetry into the console.
- **Activate**:
  - Promote a validated draft to **Active**.
  - Demote the previous active version to **Inactive**.

#### Navigation guards & hotkeys

- **Navigation blockers**:
  - When a draft has unsaved changes, Builder screens can register a blocker.
  - Attempts to navigate away trigger a confirmation prompt (ideal behaviour).
- **Keyboard shortcuts**:
  - Platform‑aware key hints (e.g. `⌘S` vs `Ctrl+S`).
  - Support for chords and sequences for:
    - Saving,
    - Toggling console,
    - Navigating files,
    - Opening command/search palettes (ideal behaviour).

---

### Workspace Settings

The **Workspace Settings** section holds workspace‑specific configuration.

Subsections typically include:

- **General**
  - Name and slug,
  - Environment label (Production, Staging, Test),
  - Workspace ID and other read‑only identifiers for automation.
- **Authentication & SSO (workspace‑facing)**
  - Information about which IdP(s) apply,
  - Whether SSO is required,
  - Guidance for users.
- **Safe mode**
  - Safe mode state and message,
  - Controls for authorised roles (where allowed).
  - Changes propagate to the global banner and disable engine‑invoking actions.
- **Members & roles**
  - Lists members (name, email, role, last activity),
  - Supports:
    - Inviting users by email,
    - Changing roles,
    - Removing members.
  - Uses the central user directory and invitation APIs under the hood.

---

## Notifications & keyboard shortcuts

### Notifications

ADE Web uses a shared notifications system:

- **Toasts**:
  - Short‑lived notifications (e.g. “Run started”, “Config activated”).
  - Can include intent (info, success, warning, danger) and optional actions.
- **Banners**:
  - Persistent, cross‑cutting notifications:
    - Safe mode active,
    - Backend connectivity issues,
    - Setup required.

Notifications can be scoped and de‑duplicated so users are not overwhelmed by repeated messages.

### Keyboard shortcuts

ADE Web supports keyboard shortcuts for power users:

- Platform‑aware hints:
  - `⌘K` on macOS, `Ctrl+K` on Windows/Linux.
- Chords and sequences:
  - Common actions like save, search, and navigate.
- Respect for text inputs:
  - Shortcuts are suppressed while typing in fields where appropriate.

A small “shortcut hint” component is used in search boxes and other affordances to gently teach available hotkeys.

---

## Typical user journeys

### 1. Analyst running an extraction

1. Sign in via SSO or standard login.
2. Land on **Workspaces**, pick a workspace.
3. Go to **Documents**.
4. Upload a spreadsheet or select an existing document.
5. Click **Run**, choose config/version/options as needed, and confirm.
6. Watch the run in the **Document Runs Drawer**:
   - Live logs,
   - Telemetry,
   - Status updates.
7. On success, download outputs from the same drawer.

### 2. Workspace owner rolling out a config change

1. Sign in and choose the workspace.
2. Open **Config Builder**.
3. Clone the active config into a **new Draft**.
4. Edit Python modules, config files, and manifest.
5. Run **builds/validations** and **test runs** until the draft is stable.
6. **Activate** the draft:
   - It becomes the active version,
   - The previous active version becomes inactive.
7. Monitor early runs in **Jobs**, and adjust if needed.

### 3. Responding to an incident / rollback

1. Notice failures or anomalies in **Jobs**.
2. Drill into problematic runs:
   - Logs,
   - Telemetry,
   - Config versions used.
3. In **Config Builder**, locate a previously good inactive version.
4. Clone it into a new draft, optionally apply a small fix.
5. Validate and test it against representative documents.
6. Activate the fixed draft.
7. Optionally enable **safe mode** during investigation; disable it once stable.

### 4. Admin creating a new workspace

1. Sign in as a user with `Workspaces.Create` permission.
2. Go to **Workspaces** and click **Create workspace**.
3. Fill in:
   - Name (e.g. “Finance Operations”),
   - Slug (auto‑generated from name, tweak if needed),
   - Owner (yourself, or another user if allowed).
4. Submit the form:
   - Fix any client or server‑side validation errors.
5. Land in the new workspace shell and proceed to:
   - Configure SSO hints,
   - Invite members,
   - Set up config packages and safe mode policies.

---

## Backend expectations (high‑level)

While ADE Web is backend‑agnostic, it suggests a set of contracts for any compatible backend:

- **Auth & sessions**
  - Endpoints for:
    - Listing auth providers (`force_sso`, provider metadata),
    - Reading the current session (user, roles, return_to),
    - Creating/refreshing/destroying sessions,
    - Exposing first‑run setup status and completing setup.

- **Workspaces**
  - List and create workspaces (with name, slug, owner, default flag, etc.),
  - Retrieve workspace metadata and permissions,
  - Manage membership and roles.

- **Documents**
  - Upload, list, and retrieve documents by workspace,
  - Store type, tags, uploader, timestamps,
  - Associate runs with documents.

- **Runs / jobs**
  - Create runs with options (e.g. `dry_run`, `validate_only`, input sheet selection),
  - Query runs by workspace/document/user,
  - Provide NDJSON streams for run events, logs, and telemetry,
  - Provide artifact listings and download endpoints.

- **Config packages & versions**
  - List configs per workspace,
  - Manage versions (create/clone/activate/archive),
  - Provide file and script operations (list/read/write/rename/delete) with ETag support,
  - Read and patch manifests safely,
  - Trigger builds and validations,
  - Trigger test runs against documents.

- **Safe mode**
  - System‑wide safe mode endpoint (status + detail),
  - Optional workspace‑scoped safe mode for finer control.

- **Users & invitations**
  - Paginated user directory with search,
  - Create invitations and track their state.

- **Streaming & telemetry**
  - NDJSON endpoints where each line is a standalone JSON event:
    - Run/build lifecycle events,
    - Structured telemetry envelopes,
    - Log messages.

- **Security**
  - Enforce RBAC and permissions on all operations,
  - CSRF protection for state‑changing requests (ADE Web can send CSRF tokens),
  - Strict validation of redirect targets and user input.

As long as these conceptual contracts are honoured, the ADE Web frontend can be re‑used and the backend can be reimplemented or swapped without changing the user experience.
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
  "version": "0.1.0",
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
    """Return metadata for ADE jobs."""
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
    result = snapshot.run_job("membership", input_path="./fixtures/membership.csv")
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
  "version": "0.1.0",
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
    """Return metadata for ADE jobs."""
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
    result = snapshot.run_job("membership", input_path="./fixtures/membership.csv")
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
