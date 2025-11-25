# 06 – Workspace layout and sections

This document describes the **workspace‑level UI layout** in ADE Web:

- The **Workspace directory** (`/workspaces`) – where users discover and select workspaces.
- The **Workspace shell** (`/workspaces/:workspaceId/...`) – the frame around a single workspace.
- The **sections inside a workspace** (Documents, Runs, Config Builder, Settings, Overview) and how they plug into the shell.
- Where **banners**, **safe mode messaging**, and **notifications** appear.

It focuses on **layout and responsibilities**, not API details or low‑level component props.

> Related docs:
> - [`01-domain-model-and-naming.md`](./01-domain-model-and-naming.md) – definitions of Workspace, Document, Run, Config, etc.
> - [`03-routing-navigation-and-url-state.md`](./03-routing-navigation-and-url-state.md) – route structure and navigation helpers.
> - [`07-documents-and-runs.md`](./07-documents-and-runs.md) – detailed behaviour of the Documents and Runs sections.
> - [`08-configurations-and-config-builder.md`](./08-configurations-and-config-builder.md) and [`09-workbench-editor-and-scripting.md`](./09-workbench-editor-and-scripting.md) – Config Builder internals.
> - [`10-ui-components-a11y-and-testing.md`](./10-ui-components-a11y-and-testing.md) – UI primitives, accessibility, and keyboard patterns.

---

## 1. UX layers: directory vs shell

ADE Web has two distinct workspace layers:

1. **Workspace directory**  
   - Route: `/workspaces` (+ `/workspaces/new`).  
   - Shows all workspaces the user can access.  
   - Lets users **select** or **create** workspaces.  
   - Does *not* render the workspace shell.

2. **Workspace shell**  
   - Routes: `/workspaces/:workspaceId/...`.  
   - Wraps all activity **inside a single workspace**.  
   - Provides a stable frame: top bar, left nav, banners.  
   - Hosts section screens: Documents, Runs, Config Builder, Settings, Overview.

The rule:

- `/workspaces` → **directory only**.  
- `/workspaces/:workspaceId/...` → **shell + section**.

---

## 2. Global top bar (`GlobalTopBar`)

The **global top bar** is shared between the directory and the shell. It is the horizontal frame that indicates *where you are* and exposes *what you can do next*.

### 2.1 Responsibilities

- Show **context** (directory vs specific workspace).
- Host **primary actions** for the current surface.
- Provide a **search** field (scope depends on view).
- Expose the **profile menu**.
- Provide an anchor for **global banners** directly beneath it.

### 2.2 Layout slots

`GlobalTopBar` is a layout component with named slots:

- `brand` – left‑aligned:
  - Directory: “Workspace directory” + ADE product label.
  - Shell: workspace name + optional environment label.
- `leading` – breadcrumbs or lightweight context.
- `actions` – main buttons (e.g. “Create workspace”, “Upload document”, “Run extraction”).
- `trailing` – profile / user menu (`ProfileDropdown`).
- `secondaryContent` – optional row underneath for filters, breadcrumbs, tabs.

The top bar may contain a `GlobalSearchField` in its main row.

### 2.3 Behaviour per layer

- **Directory (`/workspaces`)**
  - `brand`: static label + product name.
  - `actions`: “Create workspace” if user has permission.
  - `secondaryContent`: may hold workspace search and guidance text.
  - Search: filters workspace cards (name/slug); bound to `⌘K` / `Ctrl+K`.

- **Workspace shell (`/workspaces/:workspaceId/...`)**
  - `brand`: workspace name + environment label (e.g. `Acme · Production`).
  - `leading`: optional section name or breadcrumbs.
  - `actions`: section‑specific actions (e.g. “Upload document”, “Run extraction”, “New configuration”).
  - `trailing`: `ProfileDropdown`.
  - `secondaryContent`: often used for section filters or tabs.
  - Search: workspace‑scoped, usually **section‑aware**:
    - Documents: filters documents.
    - Runs: filters runs.
    - Other sections: workspace‑wide search surface.

From a layout standpoint, the top bar’s **height and structure** are stable; only the slot content changes between screens.

---

## 3. Workspace directory (`/workspaces`)

The Workspace directory is the first stop after sign‑in for most users.

### 3.1 Responsibilities

- List workspaces the user has access to.
- Provide search / quick jump to a workspace.
- Allow workspace creation (if the user has permission).
- Offer light guidance on how to structure workspaces.

### 3.2 Layout & structure

The directory screen is typically structured as:

- **GlobalTopBar** configured for “directory”.
- **Main content**:
  - Header section with title and brief description.
  - Workspace search field.
  - Workspace list (cards) or an empty‑state panel.
  - Optional right‑hand guidance column.

On small viewports, the right‑hand guidance collapses below or is omitted; the list remains the focus.

### 3.3 Workspace search

- Implemented via `GlobalSearchField` configured for workspaces.
- Behaviours:
  - Filters workspace cards by **name** and **slug**.
  - `⌘K` / `Ctrl+K` focuses the search when the directory is active.
  - Pressing Enter with a clearly best match may jump directly to that workspace.

Search is **purely client‑side** over the current list in typical deployments, but nothing in the layout assumes that.

### 3.4 Actions and permissions

- “Create workspace” appears only if the user has the relevant permission (e.g. `Workspaces.Create`).
- If the user lacks this permission and has no workspaces:
  - The screen explains that they must be **invited**.
  - Suggest linking to admin contact or documentation if available.

### 3.5 Empty and loading states

Common states:

- **Loading**: skeleton workspace cards and disabled actions while queries are in flight.
- **No workspaces & can create**:
  - Headline: “You don’t have any workspaces yet.”
  - Description: short explanation of what workspaces are for.
  - Primary CTA: “Create your first workspace”.
- **No workspaces & cannot create**:
  - Headline: “You’re not a member of any workspaces yet.”
  - Body: “Ask an administrator to invite you.”

### 3.6 Workspace cards

Each workspace is represented by a card that includes:

- Name.
- Slug or human‑friendly short ID.
- Optional **environment label** (e.g. Production, Staging).
- Optional indication that this is the user’s **default workspace**.
- Compact summary of the user’s roles/permissions (e.g. “Owner”, “Editor”).

Clicking a card:

- Navigates to `/workspaces/:workspaceId/documents` (or another chosen default section) inside the **Workspace shell**.

The optional right‑hand panel can include:

- Examples of workspace organisation (per client, per environment, etc.).
- A short checklist for new deployments (invite admins, configure roles, set default workspace).

---

## 4. Workspace shell (`/workspaces/:workspaceId/...`)

The Workspace shell renders everything inside a single workspace. It owns the frame; sections own their content.

### 4.1 Responsibilities

- Load and expose **workspace context**:
  - Name, slug, environment label.
  - Membership and permissions.
  - Safe mode status (via shared query).
- Render stable **shell chrome**:
  - Left navigation (section switcher).
  - Workspace‑specific top bar.
  - Banner strip (safe mode, connectivity).
- Host **section screens** inside the main content area.
- Handle shell‑level loading/error states (e.g. workspace not found).

The shell is implemented by a dedicated screen component, e.g. `WorkspaceShellScreen`.

### 4.2 Route boundary

All routes under `/workspaces/:workspaceId` are expected to be rendered inside the shell. Examples:

- `/workspaces/:workspaceId/documents`
- `/workspaces/:workspaceId/runs`
- `/workspaces/:workspaceId/config-builder`
- `/workspaces/:workspaceId/settings`
- `/workspaces/:workspaceId/overview` (optional)

The shell:

- Fetches workspace metadata once.
- Renders a **workspace‑level error state** if the workspace cannot be loaded (e.g. 404, permission denied).
- Then resolves the section based on the first path segment after `:workspaceId`.

### 4.3 Layout regions (desktop)

Conceptually, the shell layout on desktop is:

- **Top bar** – `GlobalTopBar` in “workspace” mode.
- **Banner strip** – cross‑cutting banners (safe mode, connectivity).
- **Body**:

  - Left: `WorkspaceNav` (vertical).
  - Right: `WorkspaceContent` (section content).

- **Overlay layer** – modals, maximised workbench, mobile nav, toasts.

Sections render only inside `WorkspaceContent`. They must not duplicate the top bar or left nav.

---

## 5. Left navigation (desktop)

The left nav is the primary way to navigate between sections within a workspace.

### 5.1 Contents and ordering

Typical ordering:

1. **Workspace identity**
   - Avatar/initials computed from workspace name.
   - Workspace name.
   - Environment label if present.
   - “Switch workspace” action (e.g. link back to `/workspaces` or a quick switcher dialog).

2. **Section links**
   - Documents.
   - Runs.
   - Config Builder.
   - Settings.
   - Overview (if enabled).

Section links use `NavLink` so they reflect active state based on the current path.

### 5.2 Behaviour & permissions

- **Active styling** is derived from the current path segment; for example, `/workspaces/:workspaceId/runs/...` marks the Runs item active.
- **Permissions** determine what appears:
  - Some sections may be completely hidden if the user cannot view them.
  - Alternatively, a section can be visible but disabled with a tooltip explaining the missing permission.

The shell decides the hiding strategy; individual sections should not second‑guess it.

### 5.3 Collapse and persistence

On larger screens, the nav can be collapsed to icon‑only mode:

- When collapsed:

  - Icons remain visible.
  - Workspace name and section labels are hidden or reduced.

- Collapse state is persisted **per workspace** with a key such as:

  - `ade.ui.workspace.<workspaceId>.nav.collapsed`

Rules:

- Default = expanded.
- Manual user choice should be honoured on subsequent visits.
- Auto‑collapse on very narrow viewports is allowed but should be treated as separate from the stored preference.

---

## 6. Mobile navigation

On smaller viewports, the left nav is presented as a **slide‑in drawer**.

### 6.1 Trigger and layout

- A menu button (usually in the top bar) opens the workspace nav.
- The nav slides in from the left and covers or pushes the content.
- A semi‑transparent background overlay (scrim) appears behind the nav.

### 6.2 Behaviour and closing rules

When the nav is open:

- **Body scroll is locked** so the background content does not scroll.
- Focus is moved into the nav and should remain there until the nav closes.

The nav closes when:

- A section link is selected.
- The user taps on the scrim outside the nav.
- The user presses the Escape key.
- The user activates an explicit close button (if present).

These behaviours keep mobile navigation predictable and prevent layout jitter when switching sections.

---

## 7. Workspace sections (overview)

Each section is a dedicated screen inside the shell’s main content area. This section defines their **responsibilities and relationships** to the shell; detailed workflows live in other docs.

### 7.1 Documents

- **Route:** `/workspaces/:workspaceId/documents`  
- **Screen:** `DocumentsScreen`  
- **Persona:** analysts/operators.

Responsibilities:

- List and filter documents in the workspace.
- Provide upload capabilities.
- Show each document’s status and **last run** summary.
- Offer actions such as “Run extraction”, “Download source file”, “Delete/archive”.

Shell integration:

- Top bar `actions` typically include “Upload document”.
- `GlobalSearchField` filters visible documents by name and additional criteria.
- Section banners (e.g. validation warnings) appear below the shell’s banner strip.

Detailed behaviour is in [`07-documents-and-runs.md`](./07-documents-and-runs.md).

### 7.2 Runs

- **Route:** `/workspaces/:workspaceId/runs`  
- **Screen:** `RunsScreen`  
- **Persona:** analysts/operators/engineers.

Responsibilities:

- Show a **workspace‑wide ledger of runs**.
- Allow filtering by status, configuration, initiator, date range, and possibly document.
- Provide links to:
  - Run detail view.
  - Logs and telemetry (via NDJSON streams).
  - Output artifacts and individual output files.

Shell integration:

- Top bar `leading` may display “Runs” with time range or filter summary.
- Top bar `actions` are often empty; run creation usually starts from Documents or Config Builder.
- `GlobalSearchField` can search by run id, document name, or initiator depending on configuration.

Detailed behaviour is in [`07-documents-and-runs.md`](./07-documents-and-runs.md).

### 7.3 Config Builder

- **Route:** `/workspaces/:workspaceId/config-builder`  
- **Screen:** `ConfigBuilderScreen`  
- **Persona:** workspace owners/engineers.

Responsibilities:

- Show configurations available in the workspace.
- Provide actions: create/clone/export configurations, activate/deactivate versions.
- Host the **Config Builder workbench** for editing configuration code and manifest.
- Manage the “return path” so users can exit the workbench back to where they came from.

Shell integration:

- Top bar `actions` may include “New configuration”.
- Workbench can be **embedded** or **maximised** (immersive); see §9.

Details:

- Configuration list: [`08-configurations-and-config-builder.md`](./08-configurations-and-config-builder.md).
- Workbench/editor: [`09-workbench-editor-and-scripting.md`](./09-workbench-editor-and-scripting.md).

### 7.4 Settings

- **Route:** `/workspaces/:workspaceId/settings`  
- **Screen:** `WorkspaceSettingsScreen`  
- **Persona:** workspace admins/owners.

Responsibilities:

- Manage workspace metadata (name, slug, environment label).
- Manage members and workspace‑scoped roles.
- Expose safe mode controls and other admin settings (subject to permissions).

Shell integration:

- Often uses `secondaryContent` in the top bar to place tab controls (e.g. General, Members, Roles).
- Section content is tabbed and controlled by a `view` query parameter.

RBAC and safe mode are described in [`05-auth-session-rbac-and-safe-mode.md`](./05-auth-session-rbac-and-safe-mode.md).

### 7.5 Overview (optional)

- **Route:** `/workspaces/:workspaceId/overview`  
- **Screen:** `WorkspaceOverviewScreen` (if implemented).

Responsibilities:

- Provide a **summary** surface for the workspace:
  - Recent runs.
  - Documents that need attention.
  - Current configuration status.
  - Safe mode state.

Shell integration:

- Typically appears as the first item in the nav or clearly marked as “Home”.
- Primarily read‑only; actions are delegated to other sections.

---

## 8. Banners and notifications

The shell defines **where** banners and notifications appear so sections behave consistently.

### 8.1 Banner strip

Immediately beneath `GlobalTopBar` is a **banner strip** reserved for:

- **Safe mode banner**:
  - Always present when safe mode is enabled.
  - Contains the human‑readable message from the safe mode endpoint.
  - Appears on all workspace sections.

- **Other cross‑cutting banners**:
  - Connectivity issues (“Lost connection; retrying…”).
  - Global warnings (e.g. “Using a deprecated configuration version”).

Ordering is:

1. Safe mode (highest priority).
2. Connectivity / critical issues.
3. Informational environment messages.

Section‑local banners (e.g. “Filters could not be applied”) should be rendered **inside the section**, below this strip.

### 8.2 Toast notifications

Toast notifications are transient messages, rendered in a global container (typically top‑right or bottom‑right):

- Used for:
  - Successful actions (saved, uploaded, run started).
  - Minor failures that don’t block the flow.
- Not used for:
  - Long‑lived states or critical errors that require user decisions.

The shell ensures toasts sit **above** content and banners in the z‑order but does not itself decide when to show them; sections and shared hooks trigger them.

---

## 9. Immersive layouts and special cases

Most sections are standard list/detail pages, but some flows use **immersive** layouts that temporarily emphasise content over shell chrome.

### 9.1 Config Builder workbench (immersive mode)

The Config Builder workbench supports window states (see [`09-workbench-editor-and-scripting.md`](./09-workbench-editor-and-scripting.md)):

- **Restored**:
  - Appears embedded in the Config Builder section.
  - Shell (top bar + nav + banners) fully visible.

- **Maximised**:
  - Workbench expands to fill the viewport.
  - Nav and possibly the banner strip may be visually hidden.
  - Top bar may be reduced to a thin chrome or hidden entirely.

- **Docked/minimised**:
  - Workbench is hidden; a dock control allows restoring it.

Layout rules:

- Immersive mode must provide an obvious **“Exit”** control to return to standard layout.
- Even if banners are visually collapsed, safe mode and other important states should remain one click away.
- Window state is part of presentation; routes remain under `/workspaces/:workspaceId/config-builder`.

### 9.2 Workspace‑local “Section not found”

If the path segment after `/workspaces/:workspaceId/` does not map to a known section:

- Render a **workspace‑local “Section not found”** state *inside the shell*.
- Do **not** show the global 404 – the workspace context is valid, only the section is invalid.
- Provide a clear way back to a valid section (e.g. button: “Go to Documents”).

---

## 10. Guidelines for new sections

When adding new workspace sections, apply these rules:

1. **Section lives under the shell**  
   - Route: `/workspaces/:workspaceId/<sectionSlug>`.  
   - Nav item in `WorkspaceNav`.  
   - Screen component in `features/workspace-shell/<section>/`.

2. **Use top bar slots rather than custom headers**  
   - `brand` and `leading` communicate where you are.  
   - `actions` hosts your primary call‑to‑action.  
   - `secondaryContent` is the place for section‑level tabs or filters.

3. **Respect banner and toast conventions**  
   - Global banners always sit in the shell’s banner strip.  
   - Section‑local banners go **inside** section content.  
   - Use toasts for short‑lived feedback, not persistent states.

4. **Re‑use list/detail patterns**  
   - For collections: list/table + filter toolbar.  
   - For individual items: detail view, often linked from a list row.

5. **Keep navigation predictable**  
   - Don’t invent new global nav elements; plug into `WorkspaceNav`.  
   - Use `NavLink` so active state follows the URL.

By keeping a clear separation between **shell responsibilities** (context, navigation, banners) and **section responsibilities** (data, workflows), the workspace experience stays predictable and easy to extend, even as we add new run types or features in the future.