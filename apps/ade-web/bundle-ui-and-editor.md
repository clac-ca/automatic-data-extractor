# Logical module layout (source -> sections below):
# - apps/ade-web/README.md - ADE Web
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
  | "hook_on_job_start"
  | "hook_after_mapping"
  | "hook_before_save"
  | "hook_on_job_end";

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
    "    job,",
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
    job,
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
  parameters: ["job", "state", "row_index", "row_values", "logger"],
};

const columnDetectorSpec: AdeFunctionSpec = {
  kind: "column_detector",
  name: "detect_*",
  label: "ADE: column detector (detect_*)",
  signature: [
    "def detect_*(",
    "    *,",
    "    job,",
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
    job,
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
    "job",
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
    "    job,",
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
    job,
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
  parameters: ["job", "state", "row_index", "field_name", "value", "row", "logger"],
};

const columnValidatorSpec: AdeFunctionSpec = {
  kind: "column_validator",
  name: "validate",
  label: "ADE: column validator",
  signature: [
    "def validate(",
    "    *,",
    "    job,",
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
    job,
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
    "job",
    "state",
    "row_index",
    "field_name",
    "value",
    "row",
    "field_meta",
    "logger",
  ],
};

const hookOnJobStartSpec: AdeFunctionSpec = {
  kind: "hook_on_job_start",
  name: "on_job_start",
  label: "ADE hook: on_job_start",
  signature: [
    "def on_job_start(",
    "    *,",
    "    job_id: str,",
    "    manifest: dict,",
    "    env: dict | None = None,",
    "    artifact: dict | None = None,",
    "    logger=None,",
    "    **_,",
    ") -> None:",
  ].join("\n"),
  doc: "Hook called once before detectors run. Use it for logging or lightweight setup.",
  snippet: `
def on_job_start(
    *,
    job_id: str,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    logger=None,
    **_,
) -> None:
    """\${1:Log or hydrate state before the job starts.}"""
    if logger:
        logger.info("job_start id=%s", job_id)
    return None
`.trim(),
  parameters: ["job_id", "manifest", "env", "artifact", "logger"],
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

const hookOnJobEndSpec: AdeFunctionSpec = {
  kind: "hook_on_job_end",
  name: "on_job_end",
  label: "ADE hook: on_job_end",
  signature: [
    "def on_job_end(",
    "    *,",
    "    artifact: dict | None = None,",
    "    logger=None,",
    "    **_,",
    ") -> None:",
  ].join("\n"),
  doc: "Hook called once after the job completes. Inspect the artifact for summary metrics.",
  snippet: `
def on_job_end(
    *,
    artifact: dict | None = None,
    logger=None,
    **_,
) -> None:
    """\${1:Log a completion summary.}"""
    if logger:
        total_sheets = len((artifact or {}).get("sheets", []))
        logger.info("job_end: sheets=%s", total_sheets)
    return None
`.trim(),
  parameters: ["artifact", "logger"],
};

export const ADE_FUNCTIONS: AdeFunctionSpec[] = [
  rowDetectorSpec,
  columnDetectorSpec,
  columnTransformSpec,
  columnValidatorSpec,
  hookOnJobStartSpec,
  hookAfterMappingSpec,
  hookBeforeSaveSpec,
  hookOnJobEndSpec,
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
  [hookOnJobStartSpec.name, hookOnJobStartSpec],
  [hookAfterMappingSpec.name, hookAfterMappingSpec],
  [hookBeforeSaveSpec.name, hookBeforeSaveSpec],
  [hookOnJobEndSpec.name, hookOnJobEndSpec],
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
