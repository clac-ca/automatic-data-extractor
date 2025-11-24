# ADE Web — Conceptual Overview

ADE Web is the **control surface** for ADE (Automatic Data Extractor).

The backend + engine do the hard work of reading spreadsheets, applying your `ade_config` rules, and producing a normalized workbook plus an audit trail.  

The Web app exists to let humans:

1. **Model the rules** (author config packages),
2. **Freeze them** (build reproducible runtimes),
3. **Apply them** (run jobs on real documents),
4. **Understand the outcome** (inspect artifacts, telemetry, and outputs),
5. **Control access** (workspaces, roles, and safe-mode).

Everything else in the frontend is there to support those steps.

---

## 1. How ADE Web fits into the system

At a system level there are four layers:

- **Frontend (ADE Web, this repo)**  
  SPA that handles login, workspaces, config authoring, builds, runs, and inspection.

- **Backend (FastAPI)**  
  Owns users, workspaces, configs, builds, jobs, documents. Provides REST + NDJSON streaming APIs.

- **Engine (`ade_engine`)**  
  Pure runtime that turns *source files* + *config package* into *normalized workbook + artifact + telemetry*.

- **Config packages (`ade_config`)**  
  Python packages that define business rules: row detectors, column detectors, transforms, validators, hooks, manifest.

The frontend **never runs the engine directly**. It only:

- Calls HTTP APIs,
- Streams NDJSON logs/events,
- Shows state and results,
- Stores a few UX preferences in `localStorage`.

Backend + engine are the source of truth; ADE Web is just a thin, stateful client.

---

## 2. The end-to-end user journey

From a user’s perspective, ADE Web is about moving through a repeatable **Config → Build → Run** loop inside a workspace.

### Step 0 — Sign-in and first setup

- **Auth screens** (`/login`, `/auth/callback`, `/logout`) talk to `/api/v1/auth/*`.
- **Setup screen** (`/setup`) calls `/api/v1/setup` to create the first admin and initial workspace if the system is not yet configured.
- Public vs private routes are enforced via `authNavigation.ts` (e.g. `/` and `/login` are always public; `/workspaces` is gated by a session).

Once authenticated, users land on the **Workspaces** view.

---

### Step 1 — Choose a workspace (multi-tenant boundary)

A **workspace** is the isolation boundary for:

- Config packages,
- Builds & versions,
- Jobs and documents,
- Roles & permissions.

In ADE Web:

- `Workspaces` list (`/workspaces`) shows the workspaces you can access.
- Creating a workspace hits `/api/v1/workspaces`.
- Membership, roles, and permissions for a workspace live under:
  - `/api/v1/workspaces/{workspace_id}/members`
  - `/api/v1/workspaces/{workspace_id}/roles`
  - `/api/v1/permissions`

The app caches your last active workspace ID in local storage (`workspace-preferences.ts`) so it can send you back to the right one on next visit.

**Mental model:** Once you’ve picked a workspace, every main screen (Configs, Jobs, Documents, Settings) is scoped to that workspace.

---

### Step 2 — Create a configuration (what should ADE do?)

Within a workspace, the next thing you care about is **configurations** (also called “config packages”):

- A configuration represents an **installable `ade_config` project** for that workspace.
- The backend exposes them via `/api/v1/workspaces/{workspace_id}/configurations`.

From the UI perspective, a configuration has:

- **Metadata**: name, status (draft / active / inactive), created/updated timestamps.
- **Files**: a “virtual file system” view of the `ade_config` project (Python modules, manifest, hooks, etc.).
- **Versions**: immutable snapshots you can activate or archive.
- **Builds / runs**: build logs, run/test results, and validation status.

Creating a configuration is a single call where you choose the **source**:

- **Template** (seed from bundled templates shipped with the backend), or
- **Clone** (copy an existing config’s contents).

ADE Web simply surfaces this via a form and then shows you the new config in the **Config Builder**.

---

### Step 3 — Authoring rules in the Config Builder

The **Config Builder** is the heart of ADE Web.

Conceptually, it does three things:

1. **Presents the config package as a project tree**

   - Uses `/files` APIs to list and navigate the `ade_config` project:
     - Python modules (row/column detectors, transforms, validators, hooks),
     - `manifest` describing canonical fields and table-level settings,
     - Tests and helper files.
   - The tree is built from a backend `FileListing` and rendered as a nested `WorkbenchFileNode` graph.

2. **Lets you edit code & manifest safely**

   - **Code editor** (Monaco) with:
     - ADE-aware completions and snippets for detectors, transforms, validators, and hooks (`adeScriptApi.ts` + `registerAdeScriptHelpers.ts`),
     - Theme preference (light/dark/system) stored per-workspace in local storage,
     - Standard save shortcuts (`Ctrl/Cmd + S`).
   - The editor state per file is managed by `useWorkbenchFiles`:
     - Open tabs, pinned tabs, MRU order,
     - Loading/saving/error states,
     - Dirty tracking and unsaved-changes guard (navigation is blocked until you confirm).
   - File contents are loaded and saved through config file APIs:
     - `GET /configurations/{config_id}/files/{path}` (read),
     - `PUT /configurations/{config_id}/files/{path}` (create/update),
     - Rename/delete via dedicated endpoints.

3. **Keeps the builder state shareable via the URL**

   - The builder encodes **view state** (open file, console pane, layout) in query params:
     - `file`, `pane`, `console`, `view`, `tab`, etc.
   - `urlState.ts` parses/merges those params so:
     - You can deep-link into “open `column_detectors/membership.py`, console open”, and
     - The URL is the single source of truth for builder layout.

**Important constraint:** The config builder never assumes engine internals. It only knows:

- “These are files & scripts that the engine will later import.”
- “This is a manifest shape that the backend validates.”

All semantic meaning (“this detector runs in mapping phase”, etc.) comes from the engine + docs, not from the frontend.

---

### Step 4 — Validate and **Build** the configuration (freeze it)

A **build** turns the editable `ade_config` project into a sealed runtime:

> “Create a venv, install `ade_engine` + `ade_config`, verify imports, and record metadata.”

The frontend’s job during a build is to:

1. **Start the build**

   - Call the build endpoint for a workspace/config with optional `force`/`wait` flags.
   - The backend responds with a streaming NDJSON response (`application/x-ndjson`).

2. **Stream build events into the workbench console**

   - Each line is parsed as a `BuildEvent` (created, step, log, completed).
   - `workbench/utils/console.ts` converts events into high-level messages such as:
     - “Creating virtual environment…”
     - “Installing `ade_engine` package…”
     - “Build completed successfully (exit code 0).”
   - These messages show up in the **Config Builder console pane** with timestamps and levels (info/success/warning/error).

3. **Reflect build status back into the UI**

   - The config’s build state (active, failed, canceled) is stored backend-side.
   - UI components simply query the latest configuration/build metadata and adjust:
     - “Build” button enabled/disabled,
     - Most recent build summary,
     - Any error banner or hint for the user.

**Fundamental idea:** Build is the point where ADE Web **hands the config off to the runtime**. After a successful build, runs for that config become reproducible because they use that frozen venv.

---

### Step 5 — Run the engine on real documents

Once a configuration is built, you want to **try it on a spreadsheet**.

There are two related concepts surfaced in the UI:

- **Runs** – often config-centric (e.g., “run this config now and stream its logs”).
- **Jobs** – workspace-level records that tie together:
  - A config version,
  - One or more documents,
  - A full run history, outputs, and logs.

#### 5.1 Upload & inspect documents

Within a workspace:

- Documents (source spreadsheets) are uploaded and stored under `ADE_DOCUMENTS_DIR` on the backend.
- ADE Web calls APIs like `/documents/{document_id}/sheets` to show:
  - Available sheets,
  - Basic workbook shape (useful when picking a sheet subset for a run).

#### 5.2 Start a run and watch it stream

When you trigger a run from the UI:

1. The frontend calls a **run endpoint** with:

   - Which config/version/build to use,
