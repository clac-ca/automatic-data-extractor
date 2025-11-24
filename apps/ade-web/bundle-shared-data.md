# Logical module layout (source -> sections below):
# - apps/ade-web/README.md - ADE Web
# - apps/ade-web/src/app/App.tsx
# - apps/ade-web/src/app/AppProviders.tsx
# - apps/ade-web/src/app/nav/Link.tsx
# - apps/ade-web/src/app/nav/history.tsx
# - apps/ade-web/src/app/nav/urlState.ts
# - apps/ade-web/src/main.tsx
# - apps/ade-web/src/shared/api/client.ts
# - apps/ade-web/src/shared/api/csrf.ts
# - apps/ade-web/src/shared/api/ndjson.ts
# - apps/ade-web/src/shared/api/pagination.ts
# - apps/ade-web/src/shared/auth/api.ts
# - apps/ade-web/src/shared/auth/api/logout.ts
# - apps/ade-web/src/shared/auth/hooks/useAuthProvidersQuery.ts
# - apps/ade-web/src/shared/auth/hooks/useSessionQuery.ts
# - apps/ade-web/src/shared/auth/hooks/useSetupStatusQuery.ts
# - apps/ade-web/src/shared/auth/utils/authNavigation.ts
# - apps/ade-web/src/shared/builds/api.ts
# - apps/ade-web/src/shared/builds/types.ts
# - apps/ade-web/src/shared/configs/api.ts
# - apps/ade-web/src/shared/configs/hooks/useConfigFiles.ts
# - apps/ade-web/src/shared/configs/hooks/useConfigLifecycle.ts
# - apps/ade-web/src/shared/configs/hooks/useConfigManifest.ts
# - apps/ade-web/src/shared/configs/hooks/useConfigScripts.ts
# - apps/ade-web/src/shared/configs/hooks/useConfigVersionsQuery.ts
# - apps/ade-web/src/shared/configs/hooks/useConfigsQuery.ts
# - apps/ade-web/src/shared/configs/hooks/useCreateConfigMutation.ts
# - apps/ade-web/src/shared/configs/hooks/useValidateConfiguration.ts
# - apps/ade-web/src/shared/configs/index.ts
# - apps/ade-web/src/shared/configs/keys.ts
# - apps/ade-web/src/shared/configs/manifest.ts
# - apps/ade-web/src/shared/configs/types.ts
# - apps/ade-web/src/shared/hooks/useHotkeys.ts
# - apps/ade-web/src/shared/hooks/useShortcutHint.ts
# - apps/ade-web/src/shared/notifications/index.ts
# - apps/ade-web/src/shared/notifications/types.ts
# - apps/ade-web/src/shared/notifications/useNotifications.ts
# - apps/ade-web/src/shared/runs/api.ts
# - apps/ade-web/src/shared/runs/types.ts
# - apps/ade-web/src/shared/setup/api.ts
# - apps/ade-web/src/shared/system/api.ts
# - apps/ade-web/src/shared/system/hooks.ts
# - apps/ade-web/src/shared/system/index.ts
# - apps/ade-web/src/shared/users/api.ts
# - apps/ade-web/src/shared/users/hooks/useInviteUserMutation.ts
# - apps/ade-web/src/shared/users/hooks/useUsersQuery.ts
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

# apps/ade-web/src/shared/api/client.ts
```typescript
import createClient, { type Middleware } from "openapi-fetch";

import { readCsrfToken } from "./csrf";
import { ApiError } from "../api";
import type { paths } from "@schema";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ?? "";
const baseUrl = rawBaseUrl.endsWith("/api/v1") ? rawBaseUrl.slice(0, -"/api/v1".length) : rawBaseUrl;

function resolveApiUrl(path: string) {
  if (!path.startsWith("/")) {
    throw new Error("API paths must begin with '/' relative to the server root");
  }
  return baseUrl.length > 0 ? `${baseUrl}${path}` : path;
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const target = resolveApiUrl(path);
  const headers = new Headers(init.headers ?? {});
  headers.set("X-Requested-With", "fetch");
  const method = init.method?.toUpperCase() ?? "GET";
  if (!SAFE_METHODS.has(method)) {
    const token = readCsrfToken();
    if (token && !headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", token);
    }
  }
  const response = await fetch(target, {
    credentials: "include",
    ...init,
    headers,
  });
  return response;
}

export const client = createClient<paths>({
  baseUrl: baseUrl.length > 0 ? baseUrl : undefined,
  credentials: "include",
  headers: {
    "X-Requested-With": "fetch",
  },
});

const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    const method = request.method?.toUpperCase() ?? "GET";
    if (!SAFE_METHODS.has(method)) {
      const token = readCsrfToken();
      if (token && !request.headers.has("X-CSRF-Token")) {
        request.headers.set("X-CSRF-Token", token);
      }
    }
    return request;
  },
};

const throwOnError: Middleware = {
  async onResponse({ response }) {
    if (response.ok) {
      return response;
    }

    const problem = await tryParseProblem(response);
    const message = problem?.title ?? `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, problem);
  },
};

client.use(csrfMiddleware);
client.use(throwOnError);

async function tryParseProblem(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined;
  }
  try {
    return await response.clone().json();
  } catch {
    return undefined;
  }
}
```

# apps/ade-web/src/shared/api/csrf.ts
```typescript
const DEFAULT_CSRF_COOKIE_NAMES = ["ade_csrf", "backend_app_csrf"];

function getConfiguredCookieNames(): readonly string[] {
  const configured =
    import.meta.env.VITE_SESSION_CSRF_COOKIE ?? import.meta.env.VITE_SESSION_CSRF_COOKIE_NAME;
  if (typeof configured === "string") {
    const trimmed = configured.trim();
    if (trimmed.length > 0) {
      return [trimmed];
    }
  }
  return DEFAULT_CSRF_COOKIE_NAMES;
}

function readCookieMap(): Map<string, string> | null {
  if (typeof document === "undefined") {
    return null;
  }
  const rawCookies = document.cookie;
  if (!rawCookies) {
    return null;
  }

  const map = new Map<string, string>();
  const entries = rawCookies.split(";");
  for (const entry of entries) {
    const [rawName, ...valueParts] = entry.trim().split("=");
    if (!rawName) {
      continue;
    }
    map.set(rawName, decodeURIComponent(valueParts.join("=")));
  }
  return map;
}

export function readCsrfToken(): string | null {
  const cookies = readCookieMap();
  if (!cookies) {
    return null;
  }

  for (const name of getConfiguredCookieNames()) {
    const token = cookies.get(name);
    if (token) {
      return token;
    }
  }

  return null;
}
```

# apps/ade-web/src/shared/api/ndjson.ts
```typescript
const NEWLINE = /\r?\n/;
const textDecoder = new TextDecoder();

export async function* parseNdjsonStream<T = unknown>(response: Response): AsyncGenerator<T> {
  const body = response.body;
  if (!body) {
    throw new Error("Response body is not a readable stream.");
  }

  const reader = body.getReader();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += textDecoder.decode(value, { stream: true });

      while (true) {
        const newlineIndex = buffer.search(NEWLINE);
        if (newlineIndex === -1) {
          break;
        }

        const line = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + (buffer[newlineIndex] === "\r" ? 2 : 1));

        const trimmed = line.trim();
        if (!trimmed) {
          continue;
        }

        yield JSON.parse(trimmed) as T;
      }
    }

    buffer += textDecoder.decode();
    const leftover = buffer.trim();
    if (leftover) {
      yield JSON.parse(leftover) as T;
    }
  } finally {
    reader.releaseLock();
  }
}
```

# apps/ade-web/src/shared/api/pagination.ts
```typescript
import { useMemo } from "react";

type PageWithItems<T> = {
  readonly items?: readonly T[] | null;
};

export function useFlattenedPages<T>(
  pages: readonly PageWithItems<T>[] | undefined,
  getKey: (item: T) => string,
) {
  return useMemo(() => {
    if (!pages || pages.length === 0) {
      return [] as T[];
    }

    const combined: T[] = [];
    const indexByKey = new Map<string, number>();

    for (const page of pages) {
      const pageItems = Array.isArray(page.items) ? (page.items as readonly T[]) : [];
      for (const item of pageItems) {
        const key = getKey(item);
        const existingIndex = indexByKey.get(key);

        if (existingIndex === undefined) {
          indexByKey.set(key, combined.length);
          combined.push(item);
          continue;
        }

        combined[existingIndex] = item;
      }
    }

    return combined;
  }, [pages, getKey]);
}
```

# apps/ade-web/src/shared/auth/api.ts
```typescript
import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import type { components } from "@schema";

export const sessionKeys = {
  root: ["auth"] as const,
  detail: () => [...sessionKeys.root, "session"] as const,
  providers: () => [...sessionKeys.root, "providers"] as const,
  setupStatus: () => [...sessionKeys.root, "setup-status"] as const,
};

export async function fetchSession(options: RequestOptions = {}): Promise<SessionEnvelope | null> {
  try {
    const { data } = await client.GET("/api/v1/auth/session", {
      signal: options.signal,
    });
    return extractSessionEnvelope(data);
  } catch (error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
}

export async function fetchAuthProviders(options: RequestOptions = {}): Promise<AuthProviderResponse> {
  try {
    const { data } = await client.GET("/api/v1/auth/providers", {
      signal: options.signal,
    });
    return normalizeAuthProviderResponse(data);
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return { providers: [], force_sso: false };
    }
    throw error;
  }
}

export async function createSession(payload: LoginPayload, options: RequestOptions = {}): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/auth/session", {
    body: payload,
    signal: options.signal,
  });
  if (!data) {
    throw new Error("Expected session payload.");
  }
  return normalizeSessionEnvelope(data);
}

export async function refreshSession(options: RequestOptions = {}): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/auth/session/refresh", {
    signal: options.signal,
  });
  if (!data) {
    throw new Error("Expected session payload.");
  }
  return normalizeSessionEnvelope(data);
}

export function normalizeSessionEnvelope(envelope: SessionEnvelopeWire): SessionEnvelope {
  return {
    ...envelope,
    expires_at: envelope.expires_at ?? null,
    refresh_expires_at: envelope.refresh_expires_at ?? null,
    return_to: envelope.return_to ?? null,
  };
}

function extractSessionEnvelope(payload: unknown): SessionEnvelope | null {
  if (!payload) {
    return null;
  }

  if (isSessionResponse(payload)) {
    return payload.session ? normalizeSessionEnvelope(payload.session) : null;
  }

  if (isSessionEnvelope(payload)) {
    return normalizeSessionEnvelope(payload);
  }

  throw new Error("Unexpected session payload shape returned by the server.");
}

function isSessionResponse(payload: unknown): payload is SessionResponse {
  if (!payload || typeof payload !== "object") {
    return false;
  }

  const candidate = payload as Partial<SessionResponse>;
  return (
    "session" in candidate &&
    "providers" in candidate &&
    Array.isArray(candidate.providers) &&
    "force_sso" in candidate
  );
}

function isSessionEnvelope(payload: unknown): payload is SessionEnvelopeWire {
  if (!payload || typeof payload !== "object") {
    return false;
  }
  const candidate = payload as Partial<SessionEnvelopeWire>;
  return Boolean(candidate.user);
}

function normalizeAuthProviderResponse(data: unknown): AuthProviderResponse {
  if (!isAuthProviderResponse(data)) {
    return { providers: [], force_sso: false };
  }

  return {
    providers: data.providers.map((provider) => ({
      ...provider,
      icon_url: provider.icon_url ?? null,
    })),
    force_sso: data.force_sso,
  };
}

function isAuthProviderResponse(value: unknown): value is AuthProviderResponse {
  if (!isRecord(value)) {
    return false;
  }
  if (!Array.isArray(value.providers) || typeof value.force_sso !== "boolean") {
    return false;
  }
  return value.providers.every(isAuthProvider);
}

function isAuthProvider(value: unknown): value is AuthProvider {
  if (!isRecord(value)) {
    return false;
  }
  if (
    typeof value.id !== "string" ||
    typeof value.label !== "string" ||
    typeof value.start_url !== "string"
  ) {
    return false;
  }
  return value.icon_url === undefined || value.icon_url === null || typeof value.icon_url === "string";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

interface RequestOptions {
  readonly signal?: AbortSignal;
}

type SessionEnvelopeWire = components["schemas"]["SessionEnvelope"];
type SessionResponse = Readonly<
  {
    session: SessionEnvelopeWire | null;
  } & AuthProviderResponse
>;
type LoginRequestSchema = components["schemas"]["LoginRequest"];

type AuthProvider = components["schemas"]["AuthProvider"];
export type AuthProviderResponse = Readonly<{
  providers: AuthProvider[];
  force_sso: boolean;
}>;
type LoginPayload = Readonly<Omit<LoginRequestSchema, "email"> & { email: string }>;
export type SessionEnvelope = Readonly<
  SessionEnvelopeWire & {
    expires_at: string | null;
    refresh_expires_at: string | null;
    return_to: string | null;
  }
>;
```

# apps/ade-web/src/shared/auth/api/logout.ts
```typescript
import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";

interface PerformLogoutOptions {
  readonly signal?: AbortSignal;
}

export async function performLogout({ signal }: PerformLogoutOptions = {}) {
  try {
    await client.DELETE("/api/v1/auth/session", { signal });
  } catch (error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return;
    }
    if (import.meta.env.DEV) {
      const reason = error instanceof Error ? error : new Error(String(error));
      console.warn("Failed to terminate session", reason);
    }
  }
}
```

# apps/ade-web/src/shared/auth/hooks/useAuthProvidersQuery.ts
```typescript
import { useQuery } from "@tanstack/react-query";

import { fetchAuthProviders, sessionKeys, type AuthProviderResponse } from "../api";

export function useAuthProvidersQuery() {
  return useQuery<AuthProviderResponse>({
    queryKey: sessionKeys.providers(),
    queryFn: ({ signal }) => fetchAuthProviders({ signal }),
    staleTime: 600_000,
    retry: false,
    refetchOnWindowFocus: false,
  });
}
```

# apps/ade-web/src/shared/auth/hooks/useSessionQuery.ts
```typescript
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchSession, sessionKeys, type SessionEnvelope } from "../api";

interface UseSessionQueryOptions {
  readonly enabled?: boolean;
}

export function useSessionQuery(options: UseSessionQueryOptions = {}) {
  const queryClient = useQueryClient();

  const query = useQuery<SessionEnvelope | null>({
    queryKey: sessionKeys.detail(),
    queryFn: ({ signal }) => fetchSession({ signal }),
    enabled: options.enabled ?? true,
    staleTime: 60_000,
    gcTime: 600_000,
    refetchOnWindowFocus: false,
    refetchOnMount: true,
  });

  const session = query.data ?? null;

  useEffect(() => {
    if (!session) {
      queryClient.removeQueries({ queryKey: sessionKeys.providers(), exact: false });
    }
  }, [queryClient, session]);

  return {
    ...query,
    session,
  };
}
```

# apps/ade-web/src/shared/auth/hooks/useSetupStatusQuery.ts
```typescript
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { fetchSetupStatus, type SetupStatus } from "@shared/setup/api";
import { sessionKeys } from "../api";

export function useSetupStatusQuery(enabled = true): UseQueryResult<SetupStatus> {
  return useQuery<SetupStatus>({
    queryKey: sessionKeys.setupStatus(),
    queryFn: ({ signal }) => fetchSetupStatus({ signal }),
    enabled,
    staleTime: 300_000,
    refetchOnWindowFocus: false,
  });
}
```

# apps/ade-web/src/shared/auth/utils/authNavigation.ts
```typescript
import type { LocationLike } from "@app/nav/history";

export const DEFAULT_APP_HOME = "/workspaces";

const PUBLIC_PATHS = new Set<string>(["/", "/login", "/setup", "/logout"]);

export function isPublicPath(path: string): boolean {
  if (!path) {
    return true;
  }

  const normalized = normalizePathname(path);

  if (PUBLIC_PATHS.has(normalized)) {
    return true;
  }

  if (normalized === "/auth" || normalized.startsWith("/auth/")) {
    return true;
  }

  return false;
}

export function joinPath(location: LocationLike): string {
  return `${location.pathname}${location.search}${location.hash}`;
}

export function normalizeNextFromLocation(location: LocationLike): string {
  const raw = joinPath(location) || "/";
  const sanitized = sanitizeNextPath(raw);
  return sanitized ?? DEFAULT_APP_HOME;
}

export function sanitizeNextPath(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed.startsWith("/")) {
    return null;
  }

  if (trimmed.startsWith("//")) {
    return null;
  }

  if (trimmed === "/") {
    return DEFAULT_APP_HOME;
  }

  if (isPublicPath(trimmed)) {
    return null;
  }

  return trimmed;
}

export function resolveRedirectParam(value: string | null | undefined): string {
  return sanitizeNextPath(value) ?? DEFAULT_APP_HOME;
}

export function buildLoginRedirect(next: string): string {
  return buildRedirectUrl("/login", next);
}

export function buildSetupRedirect(next: string): string {
  return buildRedirectUrl("/setup", next);
}

export function buildRedirectUrl(basePath: string, next: string): string {
  const safeNext = resolveRedirectParam(next);
  const params = new URLSearchParams();
  if (safeNext !== DEFAULT_APP_HOME) {
    params.set("redirectTo", safeNext);
  }
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}

export function chooseDestination(
  sessionReturnTo: string | null | undefined,
  queryNext: string | null | undefined,
): string {
  const sessionDestination = sanitizeNextPath(sessionReturnTo);
  if (sessionDestination) {
    return sessionDestination;
  }

  const queryDestination = sanitizeNextPath(queryNext);
  if (queryDestination) {
    return queryDestination;
  }

  return DEFAULT_APP_HOME;
}

function normalizePathname(path: string): string {
  let truncated = path;
  const hashIndex = truncated.indexOf("#");
  if (hashIndex >= 0) {
    truncated = truncated.slice(0, hashIndex);
  }
  const queryIndex = truncated.indexOf("?");
  if (queryIndex >= 0) {
    truncated = truncated.slice(0, queryIndex);
  }
  if (!truncated) {
    return "/";
  }
  if (!truncated.startsWith("/")) {
    return `/${truncated}`;
  }
  return truncated;
}
```

# apps/ade-web/src/shared/builds/api.ts
```typescript
import { post } from "@shared/api";
import { parseNdjsonStream } from "@shared/api/ndjson";

import type { BuildEvent } from "./types";

export interface BuildStreamOptions {
  readonly force?: boolean;
  readonly wait?: boolean;
}

export async function* streamBuild(
  workspaceId: string,
  configId: string,
  options: BuildStreamOptions = {},
  signal?: AbortSignal,
): AsyncGenerator<BuildEvent> {
  const path = `/workspaces/${encodeURIComponent(workspaceId)}/configs/${encodeURIComponent(configId)}/builds`;
  const response = await post<Response>(
    path,
    { stream: true, options },
    {
      parseJson: false,
      returnRawResponse: true,
      headers: { Accept: "application/x-ndjson" },
      signal,
    },
  );

  for await (const event of parseNdjsonStream<BuildEvent>(response)) {
    yield event;
  }
}
```

# apps/ade-web/src/shared/builds/types.ts
```typescript
export type BuildStatus = "queued" | "building" | "active" | "failed" | "canceled";

export type BuildEvent =
  | BuildCreatedEvent
  | BuildStepEvent
  | BuildLogEvent
  | BuildCompletedEvent;

export interface BuildEventBase {
  readonly object: "ade.build.event";
  readonly build_id: string;
  readonly created: number;
  readonly type: BuildEvent["type"];
}

export interface BuildCreatedEvent extends BuildEventBase {
  readonly type: "build.created";
  readonly status: BuildStatus;
  readonly config_id: string;
}

export interface BuildStepEvent extends BuildEventBase {
  readonly type: "build.step";
  readonly step:
    | "create_venv"
    | "upgrade_pip"
    | "install_engine"
    | "install_config"
    | "verify_imports"
    | "collect_metadata";
  readonly message?: string | null;
}

export interface BuildLogEvent extends BuildEventBase {
  readonly type: "build.log";
  readonly stream: "stdout" | "stderr";
  readonly message: string;
}

export interface BuildCompletedEvent extends BuildEventBase {
  readonly type: "build.completed";
  readonly status: BuildStatus;
  readonly exit_code?: number | null;
  readonly error_message?: string | null;
  readonly summary?: string | null;
}
```

# apps/ade-web/src/shared/configs/api.ts
```typescript
import { apiFetch, client } from "@shared/api/client";

import { ApiError } from "@shared/api";

import type {
  ConfigRecord,
  ConfigScriptContent,
  ConfigVersionRecord,
  ConfigVersionTestResponse,
  ConfigVersionValidateResponse,
  ConfigurationValidateResponse,
  ManifestEnvelope,
  ManifestEnvelopeWithEtag,
  ManifestPatchRequest,
  FileListing,
  FileReadJson,
  FileWriteResponse,
  FileRenameResponse,
  ConfigurationPage,
} from "./types";
import type { paths } from "@schema";

const textEncoder = new TextEncoder();

type ListConfigsQuery = paths["/api/v1/workspaces/{workspace_id}/configurations"]["get"]["parameters"]["query"];

export interface ListConfigsOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listConfigs(
  workspaceId: string,
  options: ListConfigsOptions = {},
): Promise<ConfigurationPage> {
  const { signal, page, pageSize, includeTotal } = options;
  const query: ListConfigsQuery = {};

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/configurations", {
    params: {
      path: { workspace_id: workspaceId },
      query,
    },
    signal,
  });

  if (!data) {
    throw new Error("Expected configuration page payload.");
  }

  return data;
}

export async function readConfiguration(
  workspaceId: string,
  configId: string,
  signal?: AbortSignal,
): Promise<ConfigRecord | null> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
      signal,
    },
  );
  return (data ?? null) as ConfigRecord | null;
}

export async function validateConfiguration(
  workspaceId: string,
  configId: string,
): Promise<ConfigurationValidateResponse> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/validate",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected validation payload.");
  }
  return data as ConfigurationValidateResponse;
}

export async function activateConfiguration(workspaceId: string, configId: string): Promise<ConfigRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/activate",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigRecord;
}

export async function deactivateConfiguration(workspaceId: string, configId: string): Promise<ConfigRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/deactivate",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigRecord;
}

export interface ListConfigFilesOptions {
  readonly prefix?: string;
  readonly depth?: "0" | "1" | "infinity";
  readonly include?: readonly string[];
  readonly exclude?: readonly string[];
  readonly limit?: number;
  readonly pageToken?: string | null;
  readonly sort?: "path" | "name" | "mtime" | "size";
  readonly order?: "asc" | "desc";
  readonly signal?: AbortSignal;
}

export async function listConfigFiles(
  workspaceId: string,
  configId: string,
  options: ListConfigFilesOptions = {},
): Promise<FileListing> {
  const { prefix, depth, include, exclude, limit, pageToken, sort, order, signal } = options;
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/files",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId },
        query: {
          prefix: prefix ?? "",
          depth: depth ?? "infinity",
          include: include?.length ? [...include] : undefined,
          exclude: exclude?.length ? [...exclude] : undefined,
          limit,
          page_token: pageToken ?? undefined,
          sort,
          order,
        },
      },
      signal,
      requestInitExt: { cache: "no-store" },
    },
  );
  if (!data) {
    throw new Error("Expected file listing payload.");
  }
  return data as FileListing;
}

export async function readConfigFileJson(
  workspaceId: string,
  configId: string,
  filePath: string,
  signal?: AbortSignal,
): Promise<FileReadJson> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, file_path: filePath },
      },
      headers: {
        Accept: "application/json",
      },
      signal,
      requestInitExt: { cache: "no-store" },
    },
  );
  if (!data) {
    throw new Error("Expected file payload.");
  }
  return data as FileReadJson;
}

export interface UpsertConfigFilePayload {
  readonly path: string;
  readonly content: string;
  readonly parents?: boolean;
  readonly etag?: string | null;
  readonly create?: boolean;
}

export async function upsertConfigFile(
  workspaceId: string,
  configId: string,
  payload: UpsertConfigFilePayload,
): Promise<FileWriteResponse> {
  const encodedPath = encodeFilePath(payload.path);
  const query = payload.parents ? "?parents=1" : "";
  const response = await apiFetch(
    `/api/v1/workspaces/${workspaceId}/configurations/${configId}/files/${encodedPath}${query}`,
    {
      method: "PUT",
      body: textEncoder.encode(payload.content),
      headers: {
        "Content-Type": "application/octet-stream",
        ...(payload.create ? { "If-None-Match": "*" } : payload.etag ? { "If-Match": payload.etag } : {}),
      },
    },
  );

  if (!response.ok) {
    const problem = await tryParseProblem(response);
    const message = problem?.title ?? `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, problem);
  }

  const data = (await response.json().catch(() => ({}))) as FileWriteResponse;
  if (!data || !data.path) {
    throw new Error("Expected write response payload.");
  }
  return data;
}

export interface RenameConfigFilePayload {
  readonly fromPath: string;
  readonly toPath: string;
  readonly overwrite?: boolean;
  readonly destIfMatch?: string | null;
}

export async function renameConfigFile(
  workspaceId: string,
  configId: string,
  payload: RenameConfigFilePayload,
): Promise<FileRenameResponse> {
  const { data } = await client.PATCH(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, file_path: payload.fromPath },
      },
      body: {
        op: "move",
        to: payload.toPath,
        overwrite: payload.overwrite ?? false,
        dest_if_match: payload.destIfMatch ?? undefined,
      },
    },
  );
  if (!data) {
    throw new Error("Expected rename payload.");
  }
  return data as FileRenameResponse;
}

export async function deleteConfigFile(
  workspaceId: string,
  configId: string,
  filePath: string,
  options: { etag?: string | null } = {},
): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}", {
    params: {
      path: { workspace_id: workspaceId, config_id: configId, file_path: filePath },
    },
    headers: options.etag ? { "If-Match": options.etag } : undefined,
  });
}

export type ConfigSourceInput =
  | { readonly type: "template"; readonly templateId: string }
  | { readonly type: "clone"; readonly configId: string };

export interface CreateConfigPayload {
  readonly displayName: string;
  readonly source: ConfigSourceInput;
}

function serializeConfigSource(source: ConfigSourceInput) {
  if (source.type === "template") {
    return {
      type: "template" as const,
      template_id: source.templateId.trim(),
    };
  }
  return {
    type: "clone" as const,
    config_id: source.configId.trim(),
  };
}

export async function createConfig(
  workspaceId: string,
  payload: CreateConfigPayload,
): Promise<ConfigRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations",
    {
      params: {
        path: { workspace_id: workspaceId },
      },
      body: {
        display_name: payload.displayName.trim(),
        source: serializeConfigSource(payload.source),
      },
    },
  );
  if (!data) {
    throw new Error("Expected configuration payload.");
  }
  return data as ConfigRecord;
}

export interface ListConfigVersionsOptions {
  readonly signal?: AbortSignal;
}

export async function listConfigVersions(
  workspaceId: string,
  configId: string,
  options: ListConfigVersionsOptions = {},
): Promise<ConfigVersionRecord[]> {
  const { signal } = options;
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId },
      },
      signal,
    },
  );
  return (data ?? []) as ConfigVersionRecord[];
}

export async function readConfigVersion(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  signal?: AbortSignal,
): Promise<ConfigVersionRecord | null> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      signal,
    },
  );
  return (data ?? null) as ConfigVersionRecord | null;
}

export async function createVersion(
  workspaceId: string,
  configId: string,
  payload: { semver: string; message?: string | null; sourceVersionId?: string | null; seedDefaults?: boolean },
) {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions",
    {
      params: { path: { workspace_id: workspaceId, config_id: configId } },
      body: {
        semver: payload.semver,
        message: payload.message ?? null,
        source_version_id: payload.sourceVersionId ?? null,
        seed_defaults: payload.seedDefaults ?? false,
      },
    },
  );
  if (!data) {
    throw new Error("Expected version payload.");
  }
  return data;
}

export async function activateVersion(workspaceId: string, configId: string, configVersionId: string) {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/activate",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
    },
  );
  if (!data) {
    throw new Error("Expected version payload.");
  }
  return data;
}

export async function archiveVersion(workspaceId: string, configId: string, configVersionId: string) {
  await client.DELETE(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
    },
  );
}

export async function permanentlyDeleteVersion(
  workspaceId: string,
  configId: string,
  configVersionId: string,
) {
  await client.DELETE(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
        query: { purge: true },
      },
    },
  );
}

export async function restoreVersion(workspaceId: string, configId: string, configVersionId: string) {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/restore",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
    },
  );
  if (!data) {
    throw new Error("Expected version payload.");
  }
  return data;
}

export async function validateVersion(
  workspaceId: string,
  configId: string,
  configVersionId: string,
): Promise<ConfigVersionValidateResponse> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/validate",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
    },
  );
  if (!data) {
    throw new Error("Expected validation payload.");
  }
  return data;
}

export async function testVersion(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  documentId: string,
  notes?: string | null,
): Promise<ConfigVersionTestResponse> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/test",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      body: {
        document_id: documentId,
        notes: notes ?? null,
      },
    },
  );
  if (!data) {
    throw new Error("Expected test response payload.");
  }
  return data;
}

export async function listScripts(workspaceId: string, configId: string, configVersionId: string, signal?: AbortSignal) {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      signal,
    },
  );
  return data ?? [];
}

export async function readScript(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  scriptPath: string,
  signal?: AbortSignal,
): Promise<ConfigScriptContent | null> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts/{script_path}",
    {
      params: {
        path: {
          workspace_id: workspaceId,
          config_id: configId,
          config_version_id: configVersionId,
          script_path: scriptPath,
        },
      },
      signal,
    },
  );
  return data ?? null;
}

export async function createScript(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  payload: { path: string; template?: string | null; language?: string | null },
): Promise<ConfigScriptContent> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      body: {
        path: payload.path,
        template: payload.template ?? null,
        language: payload.language ?? null,
      },
    },
  );
  if (!data) {
    throw new Error("Expected script payload.");
  }
  return data;
}

export interface UpdateScriptPayload {
  readonly code: string;
  readonly etag?: string | null;
}

export async function updateScript(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  scriptPath: string,
  payload: UpdateScriptPayload,
): Promise<ConfigScriptContent> {
  const { data } = await client.PUT(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts/{script_path}",
    {
      params: {
        path: {
          workspace_id: workspaceId,
          config_id: configId,
          config_version_id: configVersionId,
          script_path: scriptPath,
        },
      },
      body: { code: payload.code },
      headers: payload.etag ? { "If-Match": payload.etag } : undefined,
    },
  );
  if (!data) {
    throw new Error("Expected script payload.");
  }
  return data;
}

export async function deleteScript(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  scriptPath: string,
) {
  await client.DELETE(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/scripts/{script_path}",
    {
      params: {
        path: {
          workspace_id: workspaceId,
          config_id: configId,
          config_version_id: configVersionId,
          script_path: scriptPath,
        },
      },
    },
  );
}

export async function readManifest(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  signal?: AbortSignal,
): Promise<ManifestEnvelopeWithEtag> {
  const { data, response } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/manifest",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      signal,
    },
  );
  if (!data) {
    throw new Error("Expected manifest payload.");
  }
  const etag = response.headers.get("etag");
  return { ...data, etag } as ManifestEnvelopeWithEtag;
}

export async function patchManifest(
  workspaceId: string,
  configId: string,
  configVersionId: string,
  manifest: ManifestPatchRequest,
  etag?: string | null,
): Promise<ManifestEnvelope> {
  const { data } = await client.PATCH(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/manifest",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: configVersionId },
      },
      body: manifest,
      headers: etag ? { "If-Match": etag } : undefined,
    },
  );
  if (!data) {
    throw new Error("Expected manifest payload.");
  }
  return data;
}

export async function cloneVersion(
  workspaceId: string,
  configId: string,
  sourceVersionId: string,
  options: { semver: string; message?: string | null },
): Promise<ConfigVersionRecord> {
  const { data } = await client.POST(
    "/api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions/{config_version_id}/clone",
    {
      params: {
        path: { workspace_id: workspaceId, config_id: configId, config_version_id: sourceVersionId },
      },
      body: {
        semver: options.semver,
        message: options.message ?? null,
      },
    },
  );
  if (!data) {
    throw new Error("Expected version payload.");
  }
  return data;
}

export function findActiveVersion(versions: readonly ConfigVersionRecord[]) {
  return versions.find((version) => version.status === "active" || version.activated_at) ?? null;
}

export function findLatestInactiveVersion(versions: readonly ConfigVersionRecord[]) {
  const inactive = versions.filter((version) => version.status !== "active" && !version.deleted_at);
  return inactive.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] ?? null;
}

function encodeFilePath(path: string) {
  return path
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

async function tryParseProblem(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined;
  }
  try {
    return await response.clone().json();
  } catch {
    return undefined;
  }
}
```

# apps/ade-web/src/shared/configs/hooks/useConfigFiles.ts
```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listConfigFiles,
  readConfigFileJson,
  renameConfigFile,
  upsertConfigFile,
  type ListConfigFilesOptions,
  type RenameConfigFilePayload,
  type UpsertConfigFilePayload,
} from "../api";
import { configsKeys } from "../keys";
import type { FileListing, FileReadJson, FileRenameResponse, FileWriteResponse } from "../types";

interface UseConfigFilesQueryOptions extends Partial<ListConfigFilesOptions> {
  readonly workspaceId: string;
  readonly configId: string;
  readonly enabled?: boolean;
}

export function useConfigFilesQuery({ workspaceId, configId, enabled = true, ...options }: UseConfigFilesQueryOptions) {
  const {
    prefix = "",
    depth = "infinity",
    include,
    exclude,
    limit,
    pageToken,
    sort = "path",
    order = "asc",
  } = options;

  return useQuery<FileListing>({
    queryKey: [
      ...configsKeys.files(workspaceId, configId),
      prefix,
      depth,
      include?.join("|") ?? "",
      exclude?.join("|") ?? "",
      limit ?? "",
      pageToken ?? "",
      sort,
      order,
    ],
    queryFn: ({ signal }) =>
      listConfigFiles(workspaceId, configId, {
        prefix,
        depth,
        include,
        exclude,
        limit,
        pageToken,
        sort,
        order,
        signal,
      }),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    staleTime: 5_000,
  });
}

interface UseConfigFileQueryOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly path?: string | null;
  readonly enabled?: boolean;
}

export function useConfigFileQuery({ workspaceId, configId, path, enabled = true }: UseConfigFileQueryOptions) {
  return useQuery<FileReadJson | null>({
    queryKey: configsKeys.file(workspaceId, configId, path ?? ""),
    queryFn: ({ signal }) => {
      if (!path) {
        return Promise.resolve(null);
      }
      return readConfigFileJson(workspaceId, configId, path, signal);
    },
    enabled: enabled && Boolean(workspaceId) && Boolean(configId) && Boolean(path),
    staleTime: 0,
    gcTime: 60_000,
  });
}

export function useSaveConfigFileMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation<FileWriteResponse, Error, UpsertConfigFilePayload>({
    mutationFn: (payload) => upsertConfigFile(workspaceId, configId, payload),
    async onSuccess(_, variables) {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configsKeys.files(workspaceId, configId) }),
        queryClient.invalidateQueries({ queryKey: configsKeys.file(workspaceId, configId, variables.path) }),
      ]);
    },
  });
}

export function useRenameConfigFileMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation<FileRenameResponse, Error, RenameConfigFilePayload>({
    mutationFn: (payload) => renameConfigFile(workspaceId, configId, payload),
    async onSuccess(_, variables) {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configsKeys.files(workspaceId, configId) }),
        queryClient.invalidateQueries({ queryKey: configsKeys.file(workspaceId, configId, variables.fromPath) }),
        queryClient.invalidateQueries({ queryKey: configsKeys.file(workspaceId, configId, variables.toPath) }),
      ]);
    },
  });
}
```

# apps/ade-web/src/shared/configs/hooks/useConfigLifecycle.ts
```typescript
import { useMutation } from "@tanstack/react-query";

import { activateConfiguration, deactivateConfiguration } from "../api";
import type { ConfigRecord } from "../types";

export function useActivateConfigurationMutation(workspaceId: string, configId: string) {
  return useMutation<ConfigRecord, Error, void>({
    mutationFn: () => activateConfiguration(workspaceId, configId),
  });
}

export function useDeactivateConfigurationMutation(workspaceId: string, configId: string) {
  return useMutation<ConfigRecord, Error, void>({
    mutationFn: () => deactivateConfiguration(workspaceId, configId),
  });
}
```

# apps/ade-web/src/shared/configs/hooks/useConfigManifest.ts
```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { patchManifest, readManifest } from "../api";
import { configsKeys } from "../keys";
import type { ManifestEnvelope, ManifestEnvelopeWithEtag, ManifestPatchRequest } from "../types";

interface UseConfigManifestOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly versionId: string;
  readonly enabled?: boolean;
}

export function useConfigManifestQuery({ workspaceId, configId, versionId, enabled = true }: UseConfigManifestOptions) {
  return useQuery<ManifestEnvelopeWithEtag>({
    queryKey: configsKeys.manifest(workspaceId, configId, versionId),
    queryFn: ({ signal }) => readManifest(workspaceId, configId, versionId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0 && versionId.length > 0,
    staleTime: 10_000,
  });
}

export function usePatchManifestMutation(
  workspaceId: string,
  configId: string,
  versionId: string,
) {
  const queryClient = useQueryClient();
  return useMutation<ManifestEnvelope, Error, { manifest: ManifestPatchRequest; etag?: string | null }>({
    mutationFn: ({ manifest, etag }) => patchManifest(workspaceId, configId, versionId, manifest, etag),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configsKeys.manifest(workspaceId, configId, versionId) });
    },
  });
}
```

# apps/ade-web/src/shared/configs/hooks/useConfigScripts.ts
```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createScript, deleteScript, listScripts, readScript, updateScript } from "../api";
import { configsKeys } from "../keys";
import type { ConfigScriptContent, ConfigScriptSummary } from "../types";

interface UseConfigScriptsOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly versionId: string;
  readonly enabled?: boolean;
}

export function useConfigScriptsQuery({ workspaceId, configId, versionId, enabled = true }: UseConfigScriptsOptions) {
  return useQuery<ConfigScriptSummary[]>({
    queryKey: configsKeys.scripts(workspaceId, configId, versionId),
    queryFn: ({ signal }) => listScripts(workspaceId, configId, versionId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0 && versionId.length > 0,
    staleTime: 5_000,
    placeholderData: (previous) => previous ?? [],
  });
}

export function useConfigScriptQuery(
  workspaceId: string,
  configId: string,
  versionId: string,
  path: string,
  enabled = true,
) {
  return useQuery<ConfigScriptContent | null>({
    queryKey: configsKeys.script(workspaceId, configId, versionId, path),
    queryFn: ({ signal }) => readScript(workspaceId, configId, versionId, path, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0 && versionId.length > 0 && path.length > 0,
    staleTime: 2_000,
  });
}

export function useCreateScriptMutation(workspaceId: string, configId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation<ConfigScriptContent, Error, { path: string; template?: string | null; language?: string | null }>({
    mutationFn: (payload) => createScript(workspaceId, configId, versionId, payload),
    onSuccess: (script) => {
      queryClient.invalidateQueries({ queryKey: configsKeys.scripts(workspaceId, configId, versionId) });
      queryClient.setQueryData(configsKeys.script(workspaceId, configId, versionId, script.path), script);
    },
  });
}

export function useUpdateScriptMutation(workspaceId: string, configId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation<ConfigScriptContent, Error, { path: string; code: string; etag?: string | null }>({
    mutationFn: ({ path, code, etag }) => updateScript(workspaceId, configId, versionId, path, { code, etag }),
    onSuccess: (script) => {
      queryClient.invalidateQueries({ queryKey: configsKeys.script(workspaceId, configId, versionId, script.path) });
      queryClient.invalidateQueries({ queryKey: configsKeys.scripts(workspaceId, configId, versionId) });
    },
  });
}

export function useDeleteScriptMutation(workspaceId: string, configId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { path: string }>({
    mutationFn: ({ path }) => deleteScript(workspaceId, configId, versionId, path),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: configsKeys.scripts(workspaceId, configId, versionId) });
      queryClient.removeQueries({ queryKey: configsKeys.script(workspaceId, configId, versionId, variables.path) });
    },
  });
}
```

# apps/ade-web/src/shared/configs/hooks/useConfigVersionsQuery.ts
```typescript
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listConfigVersions, readConfigVersion } from "../api";
import { configsKeys } from "../keys";
import type { ConfigVersionRecord } from "../types";

interface UseConfigVersionsOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly enabled?: boolean;
}

export function useConfigVersionsQuery({
  workspaceId,
  configId,
  enabled = true,
}: UseConfigVersionsOptions) {
  return useQuery<ConfigVersionRecord[]>({
    queryKey: configsKeys.versions(workspaceId, configId),
    queryFn: ({ signal }) => listConfigVersions(workspaceId, configId, { signal }),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    placeholderData: (previous) => previous ?? [],
    staleTime: 15_000,
  });
}

export function useConfigVersionQuery(workspaceId: string, configId: string, versionId: string, enabled = true) {
  return useQuery<ConfigVersionRecord | null>({
    queryKey: configsKeys.version(workspaceId, configId, versionId),
    queryFn: ({ signal }) => readConfigVersion(workspaceId, configId, versionId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0 && versionId.length > 0,
    staleTime: 10_000,
  });
}

export function useInvalidateConfigVersions(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspaceId, configId) });
  };
}
```

# apps/ade-web/src/shared/configs/hooks/useConfigsQuery.ts
```typescript
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listConfigs, readConfiguration } from "../api";
import { configsKeys } from "../keys";
import type { ConfigRecord, ConfigurationPage } from "../types";

const CONFIGS_PAGE_SIZE = 100;

interface UseConfigsQueryOptions {
  readonly workspaceId: string;
  readonly enabled?: boolean;
  readonly page?: number;
  readonly pageSize?: number;
}

export function useConfigsQuery({
  workspaceId,
  enabled = true,
  page = 1,
  pageSize = CONFIGS_PAGE_SIZE,
}: UseConfigsQueryOptions) {
  return useQuery<ConfigurationPage>({
    queryKey: configsKeys.list(workspaceId, { page, pageSize }),
    queryFn: ({ signal }) => listConfigs(workspaceId, { page, pageSize, signal }),
    enabled: enabled && workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function useInvalidateConfigs(workspaceId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: configsKeys.root(workspaceId) });
  };
}

interface UseConfigQueryOptions {
  readonly workspaceId: string;
  readonly configId?: string;
  readonly enabled?: boolean;
}

export function useConfigQuery({ workspaceId, configId, enabled = true }: UseConfigQueryOptions) {
  return useQuery<ConfigRecord | null>({
    queryKey: configsKeys.detail(workspaceId, configId ?? ""),
    queryFn: ({ signal }) => {
      if (!configId) {
        return Promise.resolve(null);
      }
      return readConfiguration(workspaceId, configId, signal);
    },
    enabled: enabled && workspaceId.length > 0 && Boolean(configId),
    staleTime: 10_000,
  });
}
```

# apps/ade-web/src/shared/configs/hooks/useCreateConfigMutation.ts
```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { configsKeys } from "../keys";
import { createConfig, type CreateConfigPayload } from "../api";
import type { ConfigRecord } from "../types";

export function useCreateConfigMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<ConfigRecord, Error, CreateConfigPayload>({
    mutationFn: (payload) => createConfig(workspaceId, payload),
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: configsKeys.root(workspaceId) });
    },
  });
}
```

# apps/ade-web/src/shared/configs/hooks/useValidateConfiguration.ts
```typescript
import { useMutation } from "@tanstack/react-query";

import { validateConfiguration } from "../api";
import type { ConfigurationValidateResponse } from "../types";

export function useValidateConfigurationMutation(workspaceId: string, configId: string) {
  return useMutation<ConfigurationValidateResponse, Error, void>({
    mutationFn: () => validateConfiguration(workspaceId, configId),
  });
}
```

# apps/ade-web/src/shared/configs/index.ts
```typescript
export * from "./api";
export * from "./hooks/useConfigsQuery";
export * from "./hooks/useConfigVersionsQuery";
export * from "./hooks/useConfigManifest";
export * from "./hooks/useConfigScripts";
export * from "./hooks/useConfigFiles";
export * from "./hooks/useCreateConfigMutation";
export * from "./hooks/useValidateConfiguration";
export * from "./hooks/useConfigLifecycle";
export * from "./manifest";
export * from "./types";
export * from "./keys";
```

# apps/ade-web/src/shared/configs/keys.ts
```typescript
export const configsKeys = {
  root: (workspaceId: string) => ["workspaces", workspaceId, "configs"] as const,
  list: (workspaceId: string, params: { page?: number; pageSize?: number } = {}) =>
    [...configsKeys.root(workspaceId), "list", { ...params }] as const,
  detail: (workspaceId: string, configId: string) =>
    [...configsKeys.root(workspaceId), "detail", configId] as const,
  versions: (workspaceId: string, configId: string) =>
    [...configsKeys.detail(workspaceId, configId), "versions"] as const,
  version: (workspaceId: string, configId: string, versionId: string) =>
    [...configsKeys.detail(workspaceId, configId), "version", versionId] as const,
  scripts: (workspaceId: string, configId: string, versionId: string) =>
    [...configsKeys.version(workspaceId, configId, versionId), "scripts"] as const,
  script: (workspaceId: string, configId: string, versionId: string, path: string) =>
    [...configsKeys.scripts(workspaceId, configId, versionId), "script", path] as const,
  manifest: (workspaceId: string, configId: string, versionId: string) =>
    [...configsKeys.version(workspaceId, configId, versionId), "manifest"] as const,
  files: (workspaceId: string, configId: string) =>
    [...configsKeys.detail(workspaceId, configId), "files"] as const,
  file: (workspaceId: string, configId: string, path: string) =>
    [...configsKeys.files(workspaceId, configId), "file", path] as const,
};
```

# apps/ade-web/src/shared/configs/manifest.ts
```typescript
import { z } from "zod";

import type { ConfigManifest, ParsedManifest, ManifestColumn, ManifestTableSection } from "./types";

const manifestColumnSchema = z
  .object({
    key: z.string(),
    label: z.string(),
    path: z.string(),
    ordinal: z.number().int(),
    required: z.boolean().optional(),
    enabled: z.boolean().optional(),
    depends_on: z.array(z.string()).optional(),
  })
  .transform((value) => ({
    ...value,
    depends_on: value.depends_on ?? [],
  }));

const tableEntrySchema = z
  .object({
    path: z.string(),
  })
  .strict();

const manifestSchema = z
  .object({
    name: z.string(),
    files_hash: z.string().default(""),
    columns: z.array(manifestColumnSchema).default([]),
    table: z
      .object({
        transform: tableEntrySchema.nullable().optional(),
        validators: tableEntrySchema.nullable().optional(),
      })
      .partial()
      .optional(),
  })
  .passthrough();

export function parseManifest(raw: ConfigManifest | null | undefined): ParsedManifest {
  if (!raw) {
    return {
      name: "",
      filesHash: "",
      columns: [],
      table: undefined,
      raw: {},
    };
  }

  const parsed = manifestSchema.safeParse(raw);
  if (!parsed.success) {
    console.warn("Unable to parse manifest payload", parsed.error);
    return {
      name: "",
      filesHash: "",
      columns: [],
      table: undefined,
      raw,
    };
  }

  const { name, files_hash: filesHash, columns, table, ...rest } = parsed.data;

  return {
    name,
    filesHash,
    columns: columns.map<ManifestColumn>((column) => ({
      key: column.key,
      label: column.label,
      path: column.path,
      ordinal: column.ordinal,
      required: column.required ?? false,
      enabled: column.enabled ?? true,
      depends_on: column.depends_on ?? [],
    })),
    table: table
      ? ({
          transform: table.transform ?? null,
          validators: table.validators ?? null,
        } satisfies ManifestTableSection)
      : undefined,
    raw: { ...rest, name, files_hash: filesHash, columns, table },
  };
}

export function composeManifestPatch(current: ParsedManifest, nextColumns: ManifestColumn[]): ConfigManifest {
  return {
    ...current.raw,
    name: current.name,
    files_hash: current.filesHash,
    columns: nextColumns.map((column) => ({
      key: column.key,
      label: column.label,
      path: column.path,
      ordinal: column.ordinal,
      required: column.required ?? false,
      enabled: column.enabled ?? true,
      depends_on: Array.from(column.depends_on ?? []),
    })),
    table: current.table
      ? {
          transform: current.table.transform ?? null,
          validators: current.table.validators ?? null,
        }
      : undefined,
  };
}
```

# apps/ade-web/src/shared/configs/types.ts
```typescript
import type { components } from "@schema";

export type ConfigurationPage = components["schemas"]["ConfigurationPage"];
export type ConfigRecord = components["schemas"]["ConfigurationRecord"];
export interface ConfigVersionRecord {
  readonly config_version_id: string;
  readonly config_id: string;
  readonly workspace_id: string;
  readonly status: "draft" | "published" | "active" | "inactive";
  readonly semver?: string | null;
  readonly content_digest?: string | null;
  readonly created_at: string;
  readonly updated_at: string;
  readonly activated_at?: string | null;
  readonly deleted_at?: string | null;
}
export type ConfigScriptSummary = components["schemas"]["ConfigScriptSummary"];
export type ConfigScriptContent = components["schemas"]["ConfigScriptContent"];
export type ConfigVersionValidateResponse = components["schemas"]["ConfigVersionValidateResponse"];
export type ConfigVersionTestResponse = components["schemas"]["ConfigVersionTestResponse"];
export type ConfigurationValidateResponse = components["schemas"]["ConfigurationValidateResponse"];
export type ManifestResponse = components["schemas"]["ManifestResponse"];
export type ManifestPatchRequest = components["schemas"]["ManifestPatchRequest"];

export type ManifestEnvelope = ManifestResponse;
export interface ManifestEnvelopeWithEtag extends ManifestEnvelope {
  readonly etag?: string | null;
}

export type ConfigManifest = ManifestEnvelope["manifest"];

export interface ManifestColumn {
  readonly key: string;
  readonly label: string;
  readonly path: string;
  readonly ordinal: number;
  readonly required?: boolean;
  readonly enabled?: boolean;
  readonly depends_on?: readonly string[];
}

export interface ManifestTableSection {
  readonly transform?: { readonly path: string } | null;
  readonly validators?: { readonly path: string } | null;
}

export interface ParsedManifest {
  readonly name: string;
  readonly filesHash: string;
  readonly columns: ManifestColumn[];
  readonly table?: ManifestTableSection;
  readonly raw: ConfigManifest;
}

export type FileEntry = components["schemas"]["FileEntry"];
export type FileListing = components["schemas"]["FileListing"];
export type FileReadJson = components["schemas"]["FileReadJson"];
export type FileWriteResponse = components["schemas"]["FileWriteResponse"];
export type FileRenameResponse = components["schemas"]["FileRenameResponse"];
```

# apps/ade-web/src/shared/hooks/useHotkeys.ts
```typescript
import { useEffect, useRef } from "react";

interface HotkeyOptions {
  readonly enabled?: boolean;
  readonly allowInInputs?: boolean;
  readonly preventDefault?: boolean;
  readonly stopPropagation?: boolean;
  readonly sequenceTimeoutMs?: number;
}

export interface HotkeyConfig {
  readonly combo: string;
  readonly handler: (event: KeyboardEvent) => void;
  readonly options?: HotkeyOptions;
}

interface ChordSegment {
  readonly key: string;
  readonly ctrl?: boolean;
  readonly meta?: boolean;
  readonly alt?: boolean;
  readonly shift?: boolean;
}

interface ParsedChord {
  readonly type: "chord";
  readonly segment: ChordSegment;
}

interface ParsedSequence {
  readonly type: "sequence";
  readonly segments: readonly string[];
  readonly timeout: number;
}

type ParsedHotkey = (ParsedChord | ParsedSequence) & {
  readonly config: HotkeyConfig;
};

function normalizeKey(key: string): string {
  if (key.length === 1) {
    return key.toLowerCase();
  }
  switch (key) {
    case "ArrowUp":
      return "arrowup";
    case "ArrowDown":
      return "arrowdown";
    case "ArrowLeft":
      return "arrowleft";
    case "ArrowRight":
      return "arrowright";
    case "Escape":
      return "escape";
    case "Enter":
      return "enter";
    case " ":
    case "Space":
      return "space";
    default:
      return key.toLowerCase();
  }
}

function parseCombo(config: HotkeyConfig): ParsedHotkey | null {
  const { combo, options } = config;
  const parts = combo
    .trim()
    .split(" ")
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length === 0) {
    return null;
  }

  if (parts.length === 1) {
    const modifiers = new Set(
      parts[0]
        .split("+")
        .map((value) => value.trim().toLowerCase())
        .filter(Boolean),
    );
    const key = normalizeKey(parts[0].split("+").pop() ?? "");
    if (!key) {
      return null;
    }
    return {
      type: "chord",
      segment: {
        key,
        ctrl: modifiers.has("ctrl") || modifiers.has("control"),
        meta: modifiers.has("meta") || modifiers.has("cmd") || modifiers.has("command"),
        alt: modifiers.has("alt") || modifiers.has("option"),
        shift: modifiers.has("shift"),
      },
      config,
    };
  }

  const segments = parts.map((part) => normalizeKey(part));
  const timeout = options?.sequenceTimeoutMs ?? 600;
  return {
    type: "sequence",
    segments,
    timeout,
    config,
  };
}

function isEditableTarget(element: HTMLElement | null): boolean {
  if (!element) {
    return false;
  }
  const tag = element.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") {
    return true;
  }
  if (element.isContentEditable) {
    return true;
  }
  return false;
}

export function useHotkeys(configs: readonly HotkeyConfig[]) {
  const configsRef = useRef(configs);
  const sequenceRef = useRef<string[]>([]);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    configsRef.current = configs;
  }, [configs]);

  useEffect(() => {
    const parsed = configsRef.current
      .map(parseCombo)
      .filter((value): value is ParsedHotkey => value !== null);

    if (parsed.length === 0) {
      return;
    }

    const resetSequence = () => {
      sequenceRef.current = [];
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      for (const entry of parsed) {
        const { config } = entry;
        if (config.options?.enabled === false) {
          continue;
        }
        if (!config.options?.allowInInputs && isEditableTarget(event.target as HTMLElement | null)) {
          continue;
        }
        if (entry.type === "chord") {
          if (event.repeat) {
            continue;
          }
          const { segment } = entry;
          const key = normalizeKey(event.key);
          if (key !== segment.key) {
            continue;
          }
          if (Boolean(event.ctrlKey) !== Boolean(segment.ctrl)) {
            continue;
          }
          if (Boolean(event.metaKey) !== Boolean(segment.meta)) {
            continue;
          }
          if (Boolean(event.altKey) !== Boolean(segment.alt)) {
            continue;
          }
          if (Boolean(event.shiftKey) !== Boolean(segment.shift)) {
            continue;
          }
          if (config.options?.preventDefault !== false) {
            event.preventDefault();
          }
          if (config.options?.stopPropagation) {
            event.stopPropagation();
          }
          config.handler(event);
          resetSequence();
          return;
        }
      }

      const sequenceHandlers = parsed.filter((entry): entry is ParsedSequence & { config: HotkeyConfig } => entry.type === "sequence");
      if (sequenceHandlers.length === 0) {
        return;
      }

      const key = normalizeKey(event.key);

      if (event.ctrlKey || event.metaKey || event.altKey) {
        resetSequence();
        return;
      }

      sequenceRef.current = [...sequenceRef.current, key];
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }

      let matched = false;
      for (const sequence of sequenceHandlers) {
        const { config, segments, timeout } = sequence;
        if (config.options?.enabled === false) {
          continue;
        }
        const current = sequenceRef.current;
        const requiredLength = segments.length;
        if (current.length > requiredLength) {
          continue;
        }
        const isPrefix = segments.slice(0, current.length).every((segmentKey, index) => segmentKey === current[index]);
        if (!isPrefix) {
          continue;
        }
        matched = true;
        if (current.length === requiredLength) {
          if (config.options?.preventDefault !== false) {
            event.preventDefault();
          }
          if (config.options?.stopPropagation) {
            event.stopPropagation();
          }
          config.handler(event);
          resetSequence();
          return;
        }
        if (timeoutRef.current !== null) {
          window.clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = window.setTimeout(() => {
          resetSequence();
        }, timeout);
      }

      if (!matched) {
        resetSequence();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      resetSequence();
    };
  }, [configs]);
}
```

# apps/ade-web/src/shared/hooks/useShortcutHint.ts
```typescript
import { useEffect, useState } from "react";

interface ShortcutHintOptions {
  readonly macLabel?: string;
  readonly windowsLabel?: string;
}

const DEFAULT_MAC_LABEL = "⌘K";
const DEFAULT_WINDOWS_LABEL = "Ctrl+K";

export function useShortcutHint({ macLabel = DEFAULT_MAC_LABEL, windowsLabel = DEFAULT_WINDOWS_LABEL }: ShortcutHintOptions = {}) {
  const [hint, setHint] = useState(macLabel);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const platform = window.navigator.platform ?? "";
    const isApplePlatform = /Mac|iPhone|iPad|Macintosh/.test(platform);
    setHint(isApplePlatform ? macLabel : windowsLabel);
  }, [macLabel, windowsLabel]);

  return hint;
}
```

# apps/ade-web/src/shared/notifications/index.ts
```typescript
export { NotificationsProvider } from "./NotificationsProvider";
export { useNotifications } from "./useNotifications";
export type { ToastOptions, BannerOptions, NotificationAction, NotificationIntent } from "./types";
```

# apps/ade-web/src/shared/notifications/types.ts
```typescript
import type { ReactNode } from "react";

export type NotificationIntent = "info" | "success" | "warning" | "danger";

export interface NotificationAction {
  readonly label: string;
  readonly onSelect: () => void;
  readonly variant?: "primary" | "secondary" | "ghost";
}

interface NotificationBase {
  readonly id?: string;
  readonly title: string;
  readonly description?: string;
  readonly intent?: NotificationIntent;
  readonly dismissible?: boolean;
  readonly actions?: readonly NotificationAction[];
  readonly duration?: number | null;
  readonly scope?: string;
  readonly persistKey?: string;
  readonly icon?: ReactNode;
}

export interface ToastOptions extends NotificationBase {
  readonly kind?: "toast";
}

export interface BannerOptions extends NotificationBase {
  readonly kind?: "banner";
  readonly sticky?: boolean;
}
```

# apps/ade-web/src/shared/notifications/useNotifications.ts
```typescript
import { useMemo } from "react";

import type { BannerOptions, ToastOptions } from "./types";
import { useNotificationsContext } from "./NotificationsProvider";

export function useNotifications() {
  const context = useNotificationsContext();

  return useMemo(
    () => ({
      notifyToast: (options: ToastOptions) => context.pushToast(options),
      notifyBanner: (options: BannerOptions) => context.pushBanner(options),
      dismissNotification: (id: string) => context.dismiss(id),
      dismissScope: (scope: string, kind?: "toast" | "banner") => context.clearScope(scope, kind),
    }),
    [context],
  );
}
```

# apps/ade-web/src/shared/runs/api.ts
```typescript
import { post } from "@shared/api";
import { client } from "@shared/api/client";
import { parseNdjsonStream } from "@shared/api/ndjson";

import type { ArtifactV1 } from "@schema";
import type { TelemetryEnvelope } from "@schema/adeTelemetry";

import type { components } from "@schema";

import type { RunStreamEvent } from "./types";

export type RunOutputListing = components["schemas"]["RunOutputListing"];

export interface RunStreamOptions {
  readonly dry_run?: boolean;
  readonly validate_only?: boolean;
  readonly input_document_id?: string;
  readonly input_sheet_name?: string;
  readonly input_sheet_names?: readonly string[];
}

export async function* streamRun(
  configId: string,
  options: RunStreamOptions = {},
  signal?: AbortSignal,
): AsyncGenerator<RunStreamEvent> {
  const path = `/configs/${encodeURIComponent(configId)}/runs`;
  const response = await post<Response>(
    path,
    { stream: true, options },
    {
      parseJson: false,
      returnRawResponse: true,
      headers: { Accept: "application/x-ndjson" },
      signal,
    },
  );

  for await (const event of parseNdjsonStream<RunStreamEvent>(response)) {
    yield event;
  }
}

export async function fetchRunOutputs(
  runId: string,
  signal?: AbortSignal,
): Promise<RunOutputListing> {
  const { data } = await client.GET("/api/v1/runs/{run_id}/outputs", {
    params: { path: { run_id: runId } },
    signal,
  });

  if (!data) throw new Error("Run outputs unavailable");
  return data as RunOutputListing;
}

export async function fetchRunArtifact(
  runId: string,
  signal?: AbortSignal,
): Promise<ArtifactV1> {
  const response = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}/artifact`, {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error("Run artifact unavailable");
  }

  return (await response.json()) as ArtifactV1;
}

export async function fetchRunTelemetry(
  runId: string,
  signal?: AbortSignal,
): Promise<TelemetryEnvelope[]> {
  const response = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}/logfile`, {
    headers: { Accept: "application/x-ndjson" },
    signal,
  });

  if (!response.ok) {
    throw new Error("Run telemetry unavailable");
  }

  const text = await response.text();
  return text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as TelemetryEnvelope;
      } catch (error) {
        console.warn("Skipping invalid telemetry line", { error, line });
        return null;
      }
    })
    .filter((value): value is TelemetryEnvelope => Boolean(value));
}
```

# apps/ade-web/src/shared/runs/types.ts
```typescript
import { ADE_TELEMETRY_EVENT_SCHEMA } from "@schema/adeTelemetry";
import type { TelemetryEnvelope } from "@schema/adeTelemetry";

export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export type RunEvent =
  | RunCreatedEvent
  | RunStartedEvent
  | RunLogEvent
  | RunCompletedEvent;

export interface RunEventBase {
  readonly object: "ade.run.event";
  readonly run_id: string;
  readonly created: number;
  readonly type: RunEvent["type"];
}

export interface RunCreatedEvent extends RunEventBase {
  readonly type: "run.created";
  readonly status: RunStatus;
  readonly config_id: string;
}

export interface RunStartedEvent extends RunEventBase {
  readonly type: "run.started";
}

export interface RunLogEvent extends RunEventBase {
  readonly type: "run.log";
  readonly stream: "stdout" | "stderr";
  readonly message: string;
}

export interface RunCompletedEvent extends RunEventBase {
  readonly type: "run.completed";
  readonly status: RunStatus;
  readonly exit_code?: number | null;
  readonly error_message?: string | null;
  readonly artifact_path?: string | null;
  readonly events_path?: string | null;
  readonly output_paths?: string[];
  readonly processed_files?: string[];
}

export type RunStreamEvent = RunEvent | TelemetryEnvelope;

export function isTelemetryEnvelope(event: RunStreamEvent): event is TelemetryEnvelope {
  return (event as TelemetryEnvelope).schema === ADE_TELEMETRY_EVENT_SCHEMA;
}
```

# apps/ade-web/src/shared/setup/api.ts
```typescript
import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import { normalizeSessionEnvelope, type SessionEnvelope } from "@shared/auth/api";
import type { components } from "@schema";

export async function fetchSetupStatus(options: RequestOptions = {}): Promise<SetupStatus> {
  try {
    const { data } = await client.GET("/api/v1/setup/status", {
      signal: options.signal,
    });
    if (!data) {
      throw new Error("Expected setup status payload.");
    }
    return data as SetupStatus;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return { requires_setup: false, force_sso: false };
    }
    throw error;
  }
}

export async function completeSetup(payload: SetupPayload): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/setup", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected session payload.");
  }

  return normalizeSessionEnvelope(data);
}

export type SetupStatus = components["schemas"]["SetupStatus"];
type SetupPayload = components["schemas"]["SetupRequest"];

interface RequestOptions {
  readonly signal?: AbortSignal;
}
```

# apps/ade-web/src/shared/system/api.ts
```typescript
import { client } from "@shared/api/client";

export interface SafeModeStatus {
  readonly enabled: boolean;
  readonly detail: string;
}

export interface SafeModeUpdateRequest {
  readonly enabled: boolean;
  readonly detail?: string | null;
}

interface RequestOptions {
  readonly signal?: AbortSignal;
}

export async function fetchSafeModeStatus(options: RequestOptions = {}): Promise<SafeModeStatus> {
  const { data } = await client.GET("/api/v1/system/safe-mode", {
    signal: options.signal,
  });

  const payload = (data ?? {}) as Partial<SafeModeStatus>;
  const enabled = Boolean(payload.enabled);
  const detail =
    typeof payload.detail === "string" && payload.detail.trim().length > 0
      ? payload.detail.trim()
      : DEFAULT_SAFE_MODE_MESSAGE;

  return { enabled, detail };
}

export async function updateSafeModeStatus(
  payload: SafeModeUpdateRequest,
  options: RequestOptions = {},
): Promise<SafeModeStatus> {
  const { data } = await client.PUT("/api/v1/system/safe-mode", {
    body: payload,
    signal: options.signal,
  });

  const normalized = (data ?? {}) as Partial<SafeModeStatus>;
  return {
    enabled: Boolean(normalized.enabled),
    detail:
      typeof normalized.detail === "string" && normalized.detail.trim().length > 0
        ? normalized.detail.trim()
        : DEFAULT_SAFE_MODE_MESSAGE,
  };
}

export const DEFAULT_SAFE_MODE_MESSAGE =
  "ADE safe mode enabled; skipping engine execution until ADE_SAFE_MODE is disabled.";
```

# apps/ade-web/src/shared/system/hooks.ts
```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  DEFAULT_SAFE_MODE_MESSAGE,
  fetchSafeModeStatus,
  updateSafeModeStatus,
  type SafeModeStatus,
  type SafeModeUpdateRequest,
} from "./api";

const SAFE_MODE_QUERY_KEY = ["system", "safe-mode"] as const;

export function useSafeModeStatus() {
  return useQuery<SafeModeStatus>({
    queryKey: SAFE_MODE_QUERY_KEY,
    queryFn: ({ signal }) => fetchSafeModeStatus({ signal }),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useUpdateSafeModeStatus() {
  const queryClient = useQueryClient();
  return useMutation<SafeModeStatus, Error, SafeModeUpdateRequest>({
    mutationFn: (payload) => updateSafeModeStatus(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SAFE_MODE_QUERY_KEY });
    },
  });
}

export { DEFAULT_SAFE_MODE_MESSAGE, type SafeModeStatus, type SafeModeUpdateRequest };
```

# apps/ade-web/src/shared/system/index.ts
```typescript
export * from "./api";
export * from "./hooks";
```

# apps/ade-web/src/shared/users/api.ts
```typescript
import { post } from "@shared/api";
import { client } from "@shared/api/client";
import type { components, paths } from "@schema";

export interface FetchUsersOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly search?: string;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function fetchUsers(options: FetchUsersOptions = {}): Promise<UserListPage> {
  const { page, pageSize, search, includeTotal, signal } = options;
  const query: ListUsersQuery = {};

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }
  const trimmedSearch = search?.trim();
  if (trimmedSearch) {
    query.q = trimmedSearch;
  }

  const { data } = await client.GET("/api/v1/users", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected user page payload.");
  }

  return data;
}

export interface InviteUserPayload {
  readonly email: string;
  readonly display_name?: string | null;
}

export function inviteUser(payload: InviteUserPayload) {
  return post<UserProfile>("/users/invitations", payload);
}

type ListUsersQuery = paths["/api/v1/users"]["get"]["parameters"]["query"];
type UserListPage = components["schemas"]["UserPage"];
type UserSummary = UserListPage["items"][number];
type UserProfile = components["schemas"]["UserProfile"];

export type { UserListPage, UserSummary };
```

# apps/ade-web/src/shared/users/hooks/useInviteUserMutation.ts
```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { inviteUser } from "../api";

interface InviteUserInput {
  readonly email: string;
  readonly displayName?: string;
}

export function useInviteUserMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ email, displayName }: InviteUserInput) =>
      inviteUser({
        email,
        display_name: displayName?.trim() ? displayName.trim() : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users", "all"] });
    },
  });
}
```

# apps/ade-web/src/shared/users/hooks/useUsersQuery.ts
```typescript
import { useCallback } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";

import { fetchUsers, type FetchUsersOptions, type UserListPage } from "../api";
import { useFlattenedPages } from "@shared/api/pagination";

export interface UseUsersQueryOptions {
  readonly enabled?: boolean;
  readonly search?: string;
  readonly pageSize?: number;
}

export function useUsersQuery(options: UseUsersQueryOptions = {}) {
  const {
    enabled = true,
    search = "",
    pageSize,
  } = options;

  const trimmedSearch = search.trim();
  const effectiveSearch = trimmedSearch.length >= 2 ? trimmedSearch : "";

  const query = useInfiniteQuery<UserListPage, Error>({
    queryKey: ["users", "all", { search: trimmedSearch, pageSize }],
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchUsers(normalizeFetchOptions({
        page: typeof pageParam === "number" ? pageParam : 1,
        pageSize,
        search: effectiveSearch || undefined,
        signal,
      })),
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled,
    staleTime: 60_000,
  });

  const getUserKey = useCallback((user: UserListPage["items"][number]) => user.id, []);
  const users = useFlattenedPages(query.data?.pages, getUserKey);

  return {
    ...query,
    users,
  };
}

function normalizeFetchOptions(options: FetchUsersOptions): FetchUsersOptions {
  const next: FetchUsersOptions = { ...options };
  if (!next.page || next.page < 1) {
    next.page = 1;
  }
  return next;
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
