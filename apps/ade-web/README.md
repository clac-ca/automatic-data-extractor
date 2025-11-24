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