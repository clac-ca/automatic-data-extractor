# 06 – Workspace layout and sections

This document describes how ADE Web structures the **workspace‑level UI**:

- The relationship between the **Workspace directory** and the **Workspace shell**.
- How the **global top bar**, **navigation**, and **sections** are composed.
- Where **banners** and **notifications** appear.
- What each main workspace section is responsible for, at a layout/UX level.

It is intentionally **frontend‑centric**: it describes components, layout, and responsibilities, and defers detailed behaviour to other docs.

> See also:
> - `01-domain-model-and-naming.md` – glossary and naming.
> - `03-routing-navigation-and-url-state.md` – URL/route model.
> - `07-documents-jobs-and-runs.md` – detailed operator workflows.
> - `08-configurations-and-config-builder.md` and `09-workbench-editor-and-scripting.md` – Config Builder internals.
> - `10-ui-components-a11y-and-testing.md` – UI component details and accessibility.

---

## 1. Layers: directory vs shell

ADE Web separates workspace UX into two layers:

1. **Workspace directory** – the entry point after sign‑in, showing all workspaces a user can access.
2. **Workspace shell** – the frame around a *single* workspace, containing its sections (Documents, Jobs, Config Builder, Settings, Overview).

They share common layout primitives:

- A **global top bar** rendered via `GlobalTopBar`.
- A central **content column** that adapts between desktop and mobile.
- A consistent placement for **banners** and **toast notifications**.

The rule of thumb:

- The **Workspace directory** is where you **pick a workspace**.
- The **Workspace shell** is where you **do work inside that workspace**.

---

## 2. Global top bar (`GlobalTopBar`)

The global top bar is the primary horizontal frame element and appears on *all* “app” screens (directory and shell).

### 2.1 Responsibilities

`GlobalTopBar` is responsible for:

- Showing **brand** and high‑level context.
- Providing a **search affordance** appropriate to the current view.
- Hosting **primary actions** (e.g. “Create workspace”, “Upload document”).
- Exposing the **profile menu** (avatar + user actions).
- Providing an optional **secondary row** for breadcrumbs, filters, or view pills.

The intent: users should be able to glance at the top bar and know *where* they are and what the main “next action” is.

### 2.2 Slots and composition

`GlobalTopBar` is a layout component with explicit slots:

- `brand` – leftmost brand and context:

  - Workspace directory: static label (e.g. “Workspace directory”) plus product name.
  - Workspace shell: workspace name and optional environment label (e.g. `Acme Corp · Production`).

- `leading` – contextual breadcrumbs or additional context on the left.

- `actions` – primary buttons:

  - Directory: “Create workspace” (if user has permission).
  - Shell: varies by section; e.g. “Upload document” on Documents, “New configuration” in Config Builder.

- `trailing` – profile + menus:

  - Usually the `ProfileDropdown` component.

- `secondaryContent` – optional row under the main bar:

  - Breadcrumbs, tabs, filters, or inline alerts specific to a section.

Implementations of `WorkspaceDirectoryScreen` and `WorkspaceShellScreen` are responsible for populating these slots appropriately.

### 2.3 Search behaviour

The top bar embeds an optional `GlobalSearchField`:

- **Directory**:

  - Acts as workspace search; filters workspace cards by name/slug.
  - Bound to `⌘K` / `Ctrl+K`.

- **Workspace shell**:

  - Acts as workspace‑scoped search.
  - Behaviour may be section‑aware:
    - On Documents: search documents.
    - On Jobs: search/filter by job id or initiator.
    - Elsewhere: search within the workspace (configs, sections, help links, etc.).

The search field is *always aligned visually*, even if hidden for a given screen, so the layout does not jump between sections.

---

## 3. Workspace directory (`/workspaces`)

`WorkspaceDirectoryScreen` is the main entry after login and is responsible for:

- Listing workspaces the user is a member of.
- Providing a way to **create** a workspace (if allowed).
- Helping users understand how to **organise** workspaces.

### 3.1 Layout

The layout is intentionally simple:

- **Top bar**:

  - `brand`: “Workspace directory”.
  - `actions`: “Create workspace” button (permission‑gated).
  - `trailing`: `ProfileDropdown`.

- **Main content**:

  - A **header section** with:
    - Title (e.g. “Workspaces”).
    - Short explanatory copy.
  - A **search box** tied to `GlobalSearchField`.
  - A **list of workspace cards**.
  - Optionally, a **right‑hand panel** with guidance/checklists.

On narrow screens, the right‑hand panel collapses below the list or is hidden entirely.

### 3.2 Search behaviour

The directory search:

- Filters workspace cards by **name** and **slug**.
- Supports keyboard focus via `⌘K` / `Ctrl+K`.
- May support “type to filter” plus Enter to jump to the best match.

The implementation should be stateless and deterministic: given the current set of workspaces and a query, the result set and “best match” behaviour is fully predictable.

### 3.3 Workspace cards

Each card represents a workspace summary:

- Visible fields:

  - Name and slug.
  - Optional environment label (e.g. Production).
  - Whether it is the user’s **default workspace**.
  - A compact summary of the user’s roles/permissions in that workspace.

- Actions:

  - Click anywhere on the card to open the workspace shell at the default section (Documents).
  - Secondary affordances (if present) such as “Open settings” should be visually subordinate.

### 3.4 Empty states

The directory has two structurally different empty states:

1. **User can create workspaces, but has none**:

   - Show a prominent CTA to “Create your first workspace”.
   - Provide a short explanation of what workspaces are used for.

2. **User cannot create workspaces and has none**:

   - Explain that they must be invited to a workspace.
   - Offer contact guidance (e.g. “Ask your admin to add you”).

---

## 4. Workspace shell (`/workspaces/:workspaceId/...`)

`WorkspaceShellScreen` is the frame around everything that happens *inside* a workspace. It owns:

- The **shell layout** (top bar, left nav, main content).
- Section selection and routing.
- Shell‑level banners and notifications.

### 4.1 Shell layout (desktop)

On desktop‑sized viewports, the shell layout is:

```tsx
<AppShell>
  <GlobalTopBar ... />

  <ShellBody>
    <WorkspaceNav />      {/* left column */}
    <WorkspaceContent>    {/* right column */}
      <ShellBanners />    {/* safe mode, cross-cutting alerts */}
      <SectionScreen />   {/* Documents / Jobs / Config Builder / Settings / Overview */}
    </WorkspaceContent>
  </ShellBody>

  <ToastsContainer />     {/* global toasts, usually bottom-right */}
</AppShell>
````

Key points:

* **WorkspaceNav** is vertically anchored and scrolls independently from the main content where possible.
* **ShellBanners** render above section content, below the top bar.
* Section screens do **not** re‑render the top bar or the left nav; they only fill `WorkspaceContent`.

### 4.2 Workspace nav

The left navigation shows:

* Workspace avatar/initials and name.
* A “Switch workspace” affordance.
* Primary navigation items:

  * Documents.
  * Jobs.
  * Config Builder.
  * Settings.
  * Overview (optional section).

The nav uses `NavLink` so active styling is driven by the **path**. The rule:

* Clicking a nav item updates the route to `/workspaces/:workspaceId/<section>`.
* The shell decides which `SectionScreen` to render from the path segment.

#### Per‑workspace collapsed state

The nav can be collapsed/expanded. This state is:

* **Stored per workspace** using the shared storage naming pattern.
* Read when the shell loads, not every time a section renders.

Collapsing only changes layout (icon‑only nav vs icon+label), not which sections are available.

### 4.3 Shell layout (mobile)

On mobile‑sized viewports:

* The left nav becomes a **slide‑in drawer**:

  * Opened by a menu button in the `GlobalTopBar`.
  * Closed by:

    * Selecting a nav item.
    * Tapping outside the drawer.
    * Pressing Escape.

* Body scroll is **locked** while the nav is open to prevent scrolling the background content.

The top bar and section content remain the same; only nav presentation changes.

### 4.4 Section resolution

`WorkspaceShellScreen` is responsible for mapping the first path segment after `:workspaceId` into a section:

* `/workspaces/:workspaceId/documents` → `DocumentsScreen`.
* `/workspaces/:workspaceId/jobs` → `JobsScreen`.
* `/workspaces/:workspaceId/config-builder` → `ConfigBuilderScreen`.
* `/workspaces/:workspaceId/settings` → `WorkspaceSettingsScreen`.
* `/workspaces/:workspaceId/overview` → `WorkspaceOverviewScreen`.

Unknown sections should produce a **workspace‑local “Section not found”** state rendered inside the shell. The page must **not** fall back to the global 404 to avoid implying the entire app is broken.

---

## 5. Workspace sections (overview)

This section defines each main workspace section at a **layout and responsibility** level. Detailed behaviour lives in other docs.

### 5.1 Documents section

**Route:** `/workspaces/:workspaceId/documents`
**Screen:** `DocumentsScreen`
**Details:** see `07-documents-jobs-and-runs.md`.

Responsibilities:

* List documents owned by the workspace with filters and sorting.
* Provide an upload flow (`Upload document` button + keyboard shortcut).
* Surface per‑document status and last job summary.
* Provide an entry point to **run extraction** against a selected configuration.

Layout considerations:

* On desktop, primary content is a table/list of documents; filters sit above or to the side.
* The top bar’s `actions` slot typically includes:

  * “Upload document”.
  * Optional view toggle (list vs cards, if implemented).

### 5.2 Jobs section

**Route:** `/workspaces/:workspaceId/jobs`
**Screen:** `JobsScreen`
**Details:** see `07-documents-jobs-and-runs.md`.

Responsibilities:

* Show the workspace‑wide ledger of jobs.
* Allow filtering by status, configuration, date range, and initiator.
* Provide links to job detail views (logs, telemetry, outputs).

Layout considerations:

* Primary layout is a table with filter controls.
* Job details may be:

  * A separate screen, or
  * A side panel anchored to the list.

In either case, the Jobs section is the **canonical place** where a user looks for “what is running / what just ran”.

### 5.3 Config Builder section

**Route:** `/workspaces/:workspaceId/config-builder`
**Screen:** `ConfigBuilderScreen`
**Details:** see `08-configurations-and-config-builder.md` and `09-workbench-editor-and-scripting.md`.

Responsibilities:

* List configurations for the workspace.
* Expose configuration‑level actions (clone, export, activate/deactivate).
* Host the **Config Builder workbench** for editing a configuration’s files and manifest.
* Keep a consistent “return path” when exiting the workbench.

Layout considerations:

* In its simplest state, the section shows a list/table of configurations.
* When a configuration is being edited:

  * The workbench appears as an **overlay** (maximised) or **embedded** (restored) inside the section’s content area.
  * The shell (top bar + nav) remains visible even when the workbench is maximised.

### 5.4 Settings section

**Route:** `/workspaces/:workspaceId/settings`
**Screen:** `WorkspaceSettingsScreen`
**Details:** RBAC aspects in `05-auth-session-rbac-and-safe-mode.md`.

Responsibilities:

* Hold settings that are **scoped to a single workspace**:

  * Name, slug, environment label.
  * Membership management (members, invites).
  * Workspace roles and permissions.
  * Safe mode toggle and message (if permission allows).

Layout considerations:

* Tabbed layout driven by `view` query param (e.g. `view=general|members|roles`).
* Subsections mount lazily to avoid unnecessary data fetching.
* The top bar’s `leading` slot may show “Settings” + workspace name; `actions` may be empty or show context‑specific actions (e.g. “Invite member”).

### 5.5 Overview section (optional)

**Route:** `/workspaces/:workspaceId/overview`
**Screen:** `WorkspaceOverviewScreen` (optional)

Responsibilities:

* Provide a high‑level dashboard view for the workspace:

  * Recent jobs.
  * Documents that need attention.
  * Config versions and safe mode status.

Layout considerations:

* Overview is intentionally **aggregated** and **read‑only**; primary actions belong in the individual sections.
* If implemented, Overview should be the **first nav item** or clearly positioned as a “home” within the workspace.

---

## 6. Banners and notifications

The shell defines **where** cross‑cutting messages appear so individual sections don’t invent their own placements.

### 6.1 Banners

Banners are full‑width messages that sit **inside `WorkspaceContent`, above the section screen**:

* **Safe mode banner**:

  * Shown whenever the safe mode status endpoint reports `enabled`.
  * Contains the human‑readable detail message.
  * Appears on all workspace sections.

* **Connectivity / system banners**:

  * For significant issues (e.g. lost connection to backend).
  * May appear alongside or below the safe mode banner.

Sections may add **section‑local banners** below the shell banners, typically for:

* “Console was automatically collapsed due to limited vertical space.”
* “Some filters could not be applied; showing partial results.”

### 6.2 Toast notifications

Toasts are ephemeral messages rendered via a `ToastsContainer`, typically:

* Anchored to the bottom‑right of the viewport.
* Triggered by:

  * Success/failure of mutations (upload, save, run, activate, etc.).
  * Non‑blocking issues that don’t merit a full banner.

Toasts are **global** to the app; sections dispatch them but do not manage their layout.

---

## 7. Design guidelines for new sections

When introducing a new workspace section, follow these rules:

1. **Live inside the shell**

   * New sections must be mounted under `WorkspaceShellScreen`, with:

     * A left‑nav item.
     * A dedicated route segment (`/workspaces/:workspaceId/<section>`).
     * A `<SectionName>Screen` component in `features/workspace-shell/<section>/`.

2. **Use the top bar slots**

   * Populate `GlobalTopBar` slots (`brand`, `leading`, `actions`) instead of creating ad‑hoc headers.
   * If the section has its own tab strip, consider `secondaryContent` for it.

3. **Respect banners**

   * Do not render full‑width messages above `ShellBanners`.
   * Section‑local banners should appear immediately below shell banners.

4. **Re‑use common patterns**

   * Lists + filter bar for “collections”.
   * Detail panels or sub‑screens for “single item” views.
   * Use `GlobalSearchField` when appropriate instead of custom search controls.

5. **Keep shell consistent**

   * New sections must not alter the shell chrome (top bar, nav) beyond slot content.
   * Shell layout should feel identical when switching sections.

By following this structure, the workspace experience remains predictable and easy to navigate, and new sections can be added without surprising users or future developers.