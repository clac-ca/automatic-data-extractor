# Logical module layout (source -> sections below):
# - apps/ade-web/README.md - ADE Web
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

# apps/ade-web/src/screens/Workspace/components/WorkspaceNav.tsx
```tsx
import { NavLink } from "@app/nav/Link";
import clsx from "clsx";

import { getWorkspacePrimaryNavigation, type WorkspaceNavigationItem } from "@screens/Workspace/components/workspace-navigation";
import type { WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";

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

import type { WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";

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

const JobsIcon = createIcon(
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

type WorkspaceSectionId = "documents" | "jobs" | "config-builder" | "settings";

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
    id: "jobs",
    path: "jobs",
    label: "Jobs",
    icon: JobsIcon,
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
import { useWorkspacesQuery, workspacesKeys, WORKSPACE_LIST_DEFAULT_PARAMS, type WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";
import { WorkspaceProvider } from "@screens/Workspace/context/WorkspaceContext";
import { WorkbenchWindowProvider, useWorkbenchWindow } from "@screens/Workspace/context/WorkbenchWindowContext";
import { createScopedStorage } from "@shared/storage";
import { writePreferredWorkspace } from "@screens/Workspace/state/workspace-preferences";
import { GlobalTopBar } from "@app/shell/GlobalTopBar";
import { ProfileDropdown } from "@app/shell/ProfileDropdown";
import { WorkspaceNav, WorkspaceNavList } from "@screens/Workspace/components/WorkspaceNav";
import { defaultWorkspaceSection, getWorkspacePrimaryNavigation } from "@screens/Workspace/components/workspace-navigation";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@shared/system";
import { Alert } from "@ui/Alert";
import { PageState } from "@ui/PageState";
import { useShortcutHint } from "@shared/hooks/useShortcutHint";
import type { GlobalSearchSuggestion } from "@app/shell/GlobalTopBar";
import { NotificationsProvider } from "@shared/notifications";

import WorkspaceOverviewRoute from "@screens/Workspace/sections/Overview";
import WorkspaceDocumentsRoute from "@screens/Workspace/sections/Documents";
import DocumentDetailRoute from "@screens/Workspace/sections/Documents/components/DocumentDetail";
import WorkspaceJobsRoute from "@screens/Workspace/sections/Jobs";
import WorkspaceConfigsIndexRoute from "@screens/Workspace/sections/ConfigBuilder";
import WorkspaceConfigRoute from "@screens/Workspace/sections/ConfigBuilder/detail";
import ConfigEditorWorkbenchRoute from "@screens/Workspace/sections/ConfigBuilder/workbench";
import WorkspaceSettingsRoute from "@screens/Workspace/sections/Settings";

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
    case "jobs":
      return { kind: "content", key: "jobs", element: <WorkspaceJobsRoute /> };
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
} from "@screens/Workspace/api/workspaces-api";

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
import { useWorkspacesQuery, type WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";
import { useUsersQuery } from "@shared/users/hooks/useUsersQuery";
import { WorkspaceDirectoryLayout } from "@screens/Workspaces/components/WorkspaceDirectoryLayout";
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
import { DirectoryIcon } from "@screens/Workspace/components/workspace-navigation";

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
import { useWorkspacesQuery, type WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";
import { Button } from "@ui/Button";
import { PageState } from "@ui/PageState";
import { defaultWorkspaceSection } from "@screens/Workspace/components/workspace-navigation";
import { WorkspaceDirectoryLayout } from "@screens/Workspaces/components/WorkspaceDirectoryLayout";
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
