# ADE Web

ADE Web is the browser-based front‑end for the Automatic Data Extractor (ADE) platform.

It gives two main personas a single place to work:

- **Workspace owners / engineers** – define and evolve config packages (Python packages) that describe how documents are processed; manage safe mode; and administer workspaces, SSO, and roles.
- **End users / analysts** – upload documents; run extractions; monitor progress; inspect logs and telemetry; and download structured outputs.

This document describes **what** ADE Web does and how it should behave in an ideal implementation. It is intentionally backend‑agnostic and should be treated as the product‑level specification for the ADE Web UI and its contracts with the backend.

---

## Core concepts

### Workspaces

A **workspace** is the primary unit of organisation in ADE:

- Isolates **documents**, **runs**, **config packages**, and **access control**.
- Has a human‑readable **name** and stable **slug/ID** that appear in the UI and URLs.
- Has **one active config package version** at any point in time; this defines the default behaviour for new runs in that workspace.
- Is governed by **workspace‑level safe mode** and **role‑based access control (RBAC)**.

Users sign in, land on the **Workspaces** screen, and select (or create) a workspace before they can work with documents or configs.

---

### Documents

A **document** is any input you feed into ADE—typically exports such as:

- Spreadsheets (e.g., XLSX),
- CSV/TSV files,
- Other supported tabular or semi‑structured formats.

Per workspace:

- Documents are **uploaded into** and **owned by** that workspace.
- Each document has:
  - A **name** (usually the filename),
  - A **type** (e.g., XLSX, CSV),
  - Optional **tags** (e.g., client name, reporting period),
  - A history of **runs** associated with it.
- Documents are **immutable inputs**. If you upload a revised file, it is treated as a **new** document; runs always refer back to the original upload.

---

### Runs (jobs)

A **run** is a single execution of ADE against a specific input using a specific config version.

Conceptually:

- Runs are always **scoped to a workspace** and usually to a **document**.
- Each run tracks:
  - **Status**: `queued → running → succeeded / failed / canceled`,
  - **Timestamps**: created / started / completed,
  - **Who** triggered it,
  - The **config version** used,
  - Links to **structured output artifacts** (CSV/JSON/other),
  - **Logs and telemetry**, streamed as NDJSON events from the backend.

Runs surface in two main places:

- In the **Documents** section (per‑document view),
- In the **Jobs** section (workspace‑wide view and auditing).

The backend exposes runs via a **streaming API** (NDJSON). ADE Web consumes that stream so that **status, logs, and telemetry update in real time** while a job is running.

Advanced options commonly supported by the run API include:

- **Dry runs** – execute validation and transformation logic without emitting final outputs.
- **Validate‑only** runs – check configuration and data validity without full processing.
- Optional parameters like **input sheet names** for multi‑sheet workbooks.

These options are surfaced in the UI where they’re meaningful (e.g., advanced run dialogs and Config Builder test runs).

---

### Config packages & config versions

A **config package** is a Python package that defines how ADE should interpret, validate, and extract data for one or more document types within a workspace.

Key ideas:

- A workspace can hold **one or more config packages** (for example, different pipelines or client‑specific variants).
- Each config package is versioned into **config versions**.
- At any time, the workspace has **one active config version** that serves as the default for new runs.
- A config version consists of:
  - The Python package code,
  - Configuration and schema files,
  - A **manifest** describing the extracted columns and optional table‑level behaviour.

#### Version status and lifecycle

Each config version has a **status** and participates in a lifecycle:

- **Draft**
  - Initial state when a version is created or cloned.
  - Fully editable in the Config Builder:
    - Files and folders can be created, renamed, and removed.
    - Scripts and config files can be edited.
    - Manifests can be adjusted.
  - Can be **validated**, **built**, and used for **test runs**.
  - Not used for standard end‑user runs until activated.

- **Active**
  - Exactly **one active config version per workspace**.
  - Treated as **read‑only** in the UI to guarantee reproducibility.
  - Used for all newly started document runs unless an explicit override is provided.

- **Inactive**
  - Previously active (or otherwise retired) versions.
  - Not used for new runs.
  - Remain visible for **history, auditing, and rollback**.

The typical lifecycle:

1. **Create a draft**
   - From scratch (template),
   - By **cloning** the current active version,
   - Or by cloning an older inactive version (for rollback or regression fixes).

2. **Edit & iterate**
   - Make code and config changes in the Config Builder.
   - Update the manifest (columns, labels, required flags, etc.).
   - Run **builds/validations** and **test runs** against sample documents.
   - Inspect logs and telemetry in the integrated console.

3. **Activate**
   - Promote the draft to **Active**.
   - Automatically move the previously active version to **Inactive**.
   - All new runs use this newly active version.

4. **Evolve or rollback**
   - To evolve: clone the active version, modify, validate, and re‑activate.
   - To roll back: identify a previously working inactive version, clone it into a new draft, optionally tweak, and activate that new draft.

This workflow gives you a clear, audit‑friendly history while enforcing a **single source of truth** per workspace at any given time.

#### Manifests

Each config version has a **manifest** that describes its expected outputs and core table logic:

- **Columns**
  - Each column has:
    - `key` – a stable identifier,
    - `label` – user‑facing name,
    - `path` – where the value comes from in the extracted data,
    - `ordinal` – sort order,
    - Optional `required` flag,
    - Optional `enabled` flag,
    - Optional `depends_on` list for dependency relationships.
- **Table section**
  - Optional `transform` script path,
  - Optional `validators` script path.

The Config Builder exposes these manifest elements through UI controls so workspace owners can:

- Reorder columns,
- Toggle columns on/off,
- Mark columns as required,
- Assign or inspect transform/validator scripts.

---

### Safe mode

ADE includes a **safe mode** mechanism that acts as a kill switch for engine execution:

- When **safe mode is enabled**, new runs and build/test executions are blocked.
- Read‑only operations still work:
  - Viewing documents,
  - Inspecting runs and logs,
  - Downloading existing artifacts.

Safe mode is treated as system‑level state, with optional workspace‑level behaviour:

- A global **system safe mode flag** is exposed by the backend.
- The UI periodically refreshes this status so it remains accurate while users are active.
- Where allowed, workspace owners may see additional controls for workspace‑specific overrides.

In the UI:

- A persistent **banner** or status strip indicates that safe mode is on and explains why.
- Primary actions (Run, Build, Test Run, Activate, etc.) are disabled with contextual tooltips.
- Workspace settings provide safe mode controls to authorised roles.

---

### Roles & permissions

ADE Web is designed around **workspace‑scoped RBAC**:

- Users have roles per workspace (e.g., Owner, Maintainer, Member, Viewer).
- Roles determine which actions are available:

  - Toggling **safe mode**,
  - Editing and activating **config versions**,
  - Inviting and managing **members**,
  - Triggering **builds, test runs, and document runs**,
  - Access to **logs and telemetry**,
  - Administering SSO and workspace settings.

The backend is the source of truth for permissions. ADE Web:

- Reads the user’s session and workspace membership,
- Enables/disables UI controls accordingly,
- Avoids showing controls that the user cannot possibly use.

---

### Authentication, SSO & setup

Authentication is handled centrally by ADE’s backend.

Supported flows include:

- **Password or local account login** for simpler deployments or development.
- **Single Sign‑On (SSO)** via one or more identity providers (e.g., Azure AD, Okta), described as **auth providers** in the API.
- A first‑run **Setup** flow for bootstrapping a fresh ADE installation.

Key behaviours:

- Unauthenticated users are routed to:
  - `/login` for standard login,
  - or directly into SSO if `force_sso` is enabled by the backend.
- The login screen can show:
  - A list of configured **SSO providers** (with labels and optional icons),
  - A local login form (when permitted).
- The **Setup** screen (`/setup`) is presented when the backend indicates that ADE requires initial configuration (e.g., no admin user yet). Completing setup creates an initial session.

Session handling:

- The frontend reads the current session envelope (user, expiry, and optional `return_to` URL).
- After login or setup, ADE Web redirects to:
  1. A safe `return_to` value from the session, or
  2. A safe `redirectTo` query parameter from the URL, or
  3. The default app home (`/workspaces`).

Only **relative, same‑origin paths** are accepted as redirect targets; the app sanitises anything else to avoid open‑redirect issues.

For local development, ADE can be configured to **bypass full authentication**, allowing the frontend to be exercised without SSO wiring.

---

## Application structure & navigation

ADE Web is a **single‑page application** (SPA) that uses a custom navigation layer on top of the browser’s history API.

Primary routes:

- `/` – Home / landing.
- `/login` – Sign‑in.
- `/auth/callback` – Auth provider callback.
- `/setup` – First‑run setup flow.
- `/logout` – Logout screen.
- `/workspaces` – Workspace listing.
- `/workspaces/new` – Create workspace.
- `/workspaces/:workspaceId` – Workspace shell (Documents, Jobs, Config Builder, Settings).

Characteristics:

- Navigations update the URL via the history API without full page reloads.
- **Link** and **NavLink** components handle SPA navigation while still supporting normal browser behaviour (open in new tab, etc.).
- A **navigation blocker** mechanism allows screens (for example, the Config Builder) to prevent leaving the page when there are unsaved changes.

### URL state & deep links

Certain parts of the UI encode state into the URL so users can:

- Bookmark their current view,
- Share a link to a precise context,
- Refresh without losing place.

This is especially important in the **Config Builder**, where URL query parameters capture:

- The current **file**,
- The visible **tab** (e.g., editor),
- The active **pane** (console vs validation),
- The **console** visibility (open vs closed),
- The **layout view** (editor‑only, split, or zen/immersive mode).

The app provides helpers to read and merge this URL state in a stable way, ensuring:

- Reasonable defaults when parameters are missing,
- Clean URLs (only non‑default state is persisted),
- Back/forward navigation behaves intuitively.

---

## Documents section

The **Documents** section is where end users and analysts spend most of their time running extractions.

### Document list

The Documents screen shows a **paginated, filterable table** of all documents in the selected workspace. Typical columns:

- Document name / filename,
- Type (e.g., XLSX, CSV),
- Tags or categories,
- Last run status,
- Last run timestamp,
- Who last ran it.

Filtering & search (ideal behaviour):

- Text search by name,
- Filters by type, tags, and last run status,
- Optional date range filtering (e.g., “documents run in the last 7 days”).

### Uploading documents

Users can upload new documents via:

- An **Upload** button,
- And/or a **drag‑and‑drop** area.

The UI shows:

- Upload progress,
- Validation errors (unsupported type, size limits, etc.).

Once a file is uploaded:

- A new document record is created in that workspace,
- It appears in the table,
- It is immediately eligible to be used as input to runs.

### Document details & actions

Selecting a document opens a **details panel** or dedicated view that shows:

- Metadata:
  - Name,
  - Type,
  - Size,
  - Uploaded by,
  - Uploaded at.
- Tags and editable metadata (where permitted).
- Summary of the **most recent run**:
  - Status and duration,
  - Config version used,
  - Links to outputs.

Primary actions include:

- **Run** – start a new extraction run for that document,
- **View runs** – open a full run history drawer for the document.

When **safe mode** is enabled:

- The **Run** button is disabled,
- A tooltip or inline message explains why.

### Running a document

When starting a run from a document:

1. The user is prompted for any required parameters:
   - Which **config version** to use (defaults to the workspace’s active version),
   - Optional options such as sheet selection or scenario switches, depending on backend capabilities.
2. The run is created and moves through statuses:
   - `queued` → `running` → final state.
3. ADE Web subscribes to the **run’s NDJSON event stream**:
   - Status updates,
   - Log lines (stdout/stderr),
   - Structured telemetry events.

Document list rows and the details panel update live as the run progresses.

### Document Runs Drawer

The **Document Runs Drawer** gives a per‑document run history:

- Opens from the document details (“View runs”).
- Shows recent runs for the document (newest first), each with:
  - Status,
  - Timestamps,
  - Triggering user,
  - Config version used.

Selecting a run shows:

- Streaming or previously recorded **logs**,
- **Telemetry** (row counts, warnings, error counts, etc.),
- Links to **artifacts and output files** for download.

This drawer turns ADE Web into an end‑to‑end console for that document: you can start a job, watch it complete, inspect issues, and fetch outputs without leaving the screen.

---

## Jobs section

The **Jobs** section is a **workspace‑wide** view over all runs, regardless of which documents they came from.

### Jobs list

The Jobs screen presents a chronological table of runs with:

- Run ID,
- Document,
- Status,
- Start and completion timestamps,
- Duration,
- Triggering user,
- Config version used.

Filtering & search (ideal behaviour):

- By status (running, succeeded, failed, canceled),
- By date/time window,
- By document,
- By config version,
- By user.

This view is designed for operators and advanced users who need to monitor the overall system rather than a single document.

### Job details & logs

Selecting a job opens a detailed view or drawer that shows:

- The same **logs** that were streamed live during execution,
- **Telemetry** records (e.g., counters, timings, warnings),
- Output artifacts and download links.

This supports:

- Debugging and incident response,
- Auditing (who ran what, and when),
- Exporting run metadata via CSV or similar (ideal behaviour).

---

## Config Builder

The **Config Builder** is a first‑class part of ADE Web. It is intentionally designed to feel like a streamlined, browser‑based **VS Code‑style** environment focused on ADE config packages.

### Goals

- Make it obvious that a **config package is just a Python package**:
  - Directory tree of modules and configs,
  - Scripts for transforms/validators,
  - A manifest describing outputs.
- Minimise context switching for engineers:
  - Familiar VS Code‑like layout,
  - Keyboard shortcuts,
  - Integrated console.
- Provide an integrated loop:
  - Edit → Build/Validate → Test run → Inspect → Iterate → Activate.

### Layout: IDE‑style workbench

The Config Builder uses a multi‑panel layout:

1. **Explorer (left)**
   - Shows the **config package tree**:
     - Python modules (`__init__.py`, `models.py`, etc.),
     - Configuration files (YAML/JSON),
     - Scripts referenced by the manifest,
     - Supporting assets.
   - Features:
     - Expand/collapse folders,
     - Create, rename, and delete files and directories (for draft versions),
     - Switch between config packages and versions.

2. **Editor (centre)**
   - A code editor that behaves like a modern IDE:
     - Multiple open tabs,
     - Syntax highlighting for Python and common config formats,
     - Standard keyboard shortcuts (e.g., save, file navigation) where possible.
   - Editing is allowed only for **draft** versions; active and inactive versions are shown as read‑only.
   - The currently open files and caret position are preserved across navigations or refreshes as much as possible.

3. **Inspector / Metadata panel (right)**
   - Shows metadata for the selected config and version:
     - Display name,
     - Version identifier (often semantic version),
     - Status (draft / active / inactive),
     - Created / updated / activated timestamps,
     - Who created and activated it.
   - Provides version‑level actions such as:
     - **Activate** (for drafts),
     - **Clone** (for active/inactive versions),
     - Optional archive/restore actions where supported.

   - Also surfaces **manifest information**, including:
     - Column list (keys, labels, required flags, enabled flags, order),
     - Table transform/validator references.

4. **Console / Terminal (bottom)**
   - A terminal‑style panel that receives **streamed events** from the backend, including:
     - Build status updates,
     - Validation results,
     - Test run logs,
     - Engine errors and tracebacks.
   - Behaves like a VS Code integrated terminal:
     - Separate tabs (e.g., “Build”, “Test run”, “Validation”),
     - Lines appear incrementally as ADE streams NDJSON events,
     - Persisted per‑version so users can revisit a recent build’s output.

### View modes & URL‑encoded state

The Config Builder supports a set of **view modes** and options, persisted in the URL so they can be bookmarked or shared:

- **Tab** – primary focus (currently editor‑centric, future tabs possible).
- **Pane** – whether the bottom panel is showing:
  - `console` output, or
  - `validation` / problems.
- **Console** – whether the bottom panel is `open` or `closed`.
- **View** – overall layout:
  - `editor` – standard view,
  - `split` – editor + console visible together,
  - `zen` – minimal distractions, editor‑only focus.

The current **file path** is also encoded in the query string, making deep links like:

> “Open this particular config version with `models.py` active, in split view with the console open.”

possible and stable.

### Working with config versions

From the Config Builder, workspace owners can:

- **Create drafts**
  - “New config version” (blank or from template),
  - “Clone from active” for iterative improvements,
  - “Clone from inactive” for rollback scenarios.

- **Edit drafts**
  - Modify Python modules and config files,
  - Update manifest columns and table behaviour,
  - Add or edit supporting scripts.

- **Validate & build**
  - Trigger **builds** that:
    - Set up an isolated environment,
    - Install engine/config dependencies,
    - Import modules,
    - Collect or recompute metadata.
  - View build progress and logs in the console.

- **Run tests**
  - Trigger **test runs** that use draft versions on sample documents:
    - Select a document,
    - Optionally choose specific sheets or options,
    - Stream logs and telemetry in real time,
    - Review results without affecting normal end‑user runs.

- **Activate**
  - Promote a passing draft to **Active**:
    - The newly active version becomes the single source of truth.
    - The previously active version is demoted to **Inactive**.

Unsaved‑change navigation guards:

- When a draft has unsaved edits, the Config Builder can register a **navigation blocker**:
  - Attempting to navigate away (including back/forward or switching workspaces) prompts the user to confirm, preventing accidental loss of work.

Keyboard shortcuts:

- ADE Web exposes common IDE‑style shortcuts through a central hotkey system:
  - Supports both **chords** (e.g., `Ctrl+S`) and **sequences** (e.g., `g g`).
  - Adapts labels to platform conventions (e.g., `⌘K` on macOS vs `Ctrl+K` on Windows).
- These shortcuts are used to:
  - Save files,
  - Toggle panels,
  - Navigate within the Config Builder,
  - Invoke search or command palettes (ideal behaviour).

---

## Workspace Settings

The **Settings** section is where workspace owners and admins configure workspace‑level behaviour.

Typical subsections:

### General

- Workspace display name,
- Slug/ID used in APIs and URLs,
- Environment indicators (e.g., Production, Staging, Test),
- Read‑only identifiers useful for automation and API clients.

### Authentication & SSO (workspace‑facing)

While core SSO configuration is a system responsibility, workspace settings may surface:

- Which identity provider is connected (when relevant),
- Whether SSO is enforced (e.g., `force_sso`),
- Help text for users (“Sign in with your corporate SSO”).

### Safe mode controls

For authorised roles:

- Display current **safe mode** status and message.
- Provide controls (where allowed) for:
  - Enabling/disabling safe mode,
  - Editing a user‑facing detail message.

Changes to safe mode:

- Are reflected immediately in the global status banner,
- Disable relevant actions across Documents, Jobs, and Config Builder.

### Members & roles

Settings also include **membership management**:

- View current members:
  - Name,
  - Email,
  - Role,
  - Last activity (where available).
- Actions:
  - **Invite** users by email (sending an invitation that, once accepted, grants access),
  - **Change roles** for existing members,
  - **Remove** users from the workspace.

The UI should include brief role descriptions so admins understand the impact of each role (e.g., who can edit configs, run jobs, toggle safe mode, etc.).

---

## Users & invitations

ADE Web integrates with a backend user directory:

- The **Users** API supports:
  - Paginated user listing,
  - Text search (e.g., by name/email),
  - Optional total counts for admin views.
- The **Invite user** flow:
  - Collects an email (and optional display name),
  - Sends an invitation via the backend,
  - Updates user lists once the invite is created.

This underpins workspace membership management and supports scenarios like “invite an analyst to this workspace”.

---

## Feedback & notifications

Across the app, ADE Web provides consistent user feedback for long‑running or impactful actions:

- **Toast notifications** for transient events:
  - “Run started”,
  - “Run failed – click to view logs”,
  - “Config version activated.”
- **Banner notifications** for cross‑cutting or persistent issues:
  - System‑wide safe mode,
  - Backend connectivity issues,
  - Setup required or misconfiguration.

Notifications can:

- Include optional actions (buttons),
- Be scoped so that closing a banner in one context doesn’t hide critical information elsewhere.

---

## Typical user journeys

### 1. Analyst running an extraction

1. Sign in via SSO or standard login.
2. Land on **Workspaces** and select the appropriate workspace.
3. Open the **Documents** section.
4. Upload a new spreadsheet or select an existing document.
5. Click **Run**, confirm any options, and start the run.
6. Watch progress in the **Document Runs Drawer**:
   - Status transitions,
   - Logs and telemetry.
7. When the run succeeds, download the output artifacts (e.g., CSV/JSON) from the same drawer.

### 2. Workspace owner rolling out a config change

1. Sign in and choose the workspace.
2. Go to **Config Builder**.
3. Clone the active config into a **new draft** version.
4. Edit Python modules, config files, and manifests in the editor.
5. Run **builds/validations** and **test runs** until everything passes.
6. Activate the draft:
   - It becomes the workspace’s **active** config version.
   - The former active version moves to **inactive**.
7. Inform analysts that new runs will now use the updated logic; monitor the **Jobs** section for issues.

### 3. Responding to an incident / rollback

1. Notice failures or degraded output quality in the **Jobs** view.
2. Inspect failing runs:
   - Logs,
   - Telemetry,
   - Config versions used.
3. In **Config Builder**, identify a previously working **inactive** version.
4. Clone it into a **new draft**, apply a minimal fix if needed.
5. Run validations and test runs to confirm behaviour.
6. Activate the fixed draft to restore service.
7. Optionally enable **safe mode** while investigating, then disable it once the fix is live.

---

## Backend & API expectations (high‑level)

While ADE Web is backend‑agnostic, the behaviours described above assume that the backend provides a set of stable contracts.

### HTTP APIs

The backend should expose:

- **Auth & session**
  - Create, refresh, and invalidate sessions,
  - List **auth providers** and whether SSO is forced,
  - Return the current user and accessible workspaces,
  - Provide a first‑run **setup status** and endpoint to complete setup.

- **Workspaces**
  - List and create workspaces,
  - Retrieve workspace metadata (name, slug, environment),
  - List workspace membership and roles.

- **Documents**
  - Upload, list, and retrieve documents,
  - Store document metadata (type, tags, uploader, timestamps),
  - Associate runs with documents.

- **Runs / jobs**
  - Create runs (optionally with `dry_run`, `validate_only`, `input_document_id`, sheet options),
  - Query runs and their statuses,
  - Return output listings and artifacts,
  - Return **NDJSON log and telemetry streams** and/or historical logfile endpoints.

- **Config packages & versions**
  - List configs per workspace,
  - Create configs from templates or by cloning,
  - List, create, clone, validate, activate, and read **config versions**,
  - Manage version manifests,
  - Manage config files and scripts:
    - List,
    - Read,
    - Write (with ETag support),
    - Rename/move,
    - Delete.

- **Builds**
  - Trigger config builds,
  - Provide **NDJSON build event streams** with status, steps, and log messages.

- **Safe mode**
  - Read system‑wide safe mode status and message,
  - Update safe mode (for authorised callers).

- **Users**
  - Paginated user listing with search,
  - Invitation API to create new user invitations.

### Streaming & telemetry

Both run and build endpoints should:

- Use **NDJSON** for streaming events:
  - Each line is a single JSON event,
  - Lines may be a mix of:
    - High‑level run/build events,
    - Structured telemetry envelopes (following a documented schema),
    - Log events (stdout/stderr).
- Be consumable as a regular `fetch()` response body stream.

This allows ADE Web to:

- Show progress bars and state transitions in near real time,
- Render terminal‑like consoles in the Config Builder and Jobs views,
- Maintain a clear, inspectable execution trail for users.

### Security considerations

Backends are responsible for:

- Enforcing RBAC and all permission checks (the frontend is an aid, not a gate),
- Enforcing CSRF protections for state‑changing operations (ADE Web sends a CSRF token header when configured),
- Strictly validating redirect targets and user input.

As long as these contracts are honoured, the ADE Web frontend can be re‑used with a new backend implementation while preserving the user experience described in this document.