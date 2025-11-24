# 06-workspace-layout-and-sections

**Purpose:** Describe the global UX frame: top bar, nav, directory, shell, and where each section fits.

### 1. Overview

* Two layers:

  * Workspace directory.
  * Workspace shell.

* How they share top bar, safe mode banner, notifications.

### 2. GlobalTopBar

* Slots:

  * `brand`, `leading`, `actions`, `trailing`, `secondaryContent`.

* Where `GlobalSearchField` appears:

  * In directory: workspace search.
  * In shell: workspace-scoped search (documents/jobs/configs).

* Responsive behaviour:

  * How it collapses on small screens.

### 3. Workspace directory (`/workspaces`)

* Layout:

  * Heading, subtitle.
  * Workspace search with ⌘K / Ctrl+K.
  * “Create workspace” button with permission gating.

* States:

  * No workspaces / can create → CTA to create workspace.
  * No workspaces / cannot create → explain they need to be invited.

* Workspace cards:

  * Name, slug, default badge, roles summary.
  * Click behaviour (enter workspace shell to default section).

* Right-hand panel content (guidance/checklist).

### 4. Workspace shell (`/workspaces/:workspaceId/...`)

* Left navigation (desktop):

  * Workspace avatar/name.
  * Switch workspace affordance.
  * Sections: Documents, Jobs, Config Builder, Settings, Overview.
  * Collapse/expand and per-workspace persistence.

* Mobile navigation:

  * Slide-in panel, open/close triggers.
  * Scroll lock and dismissal rules.

* Top bar in shell:

  * Workspace name + environment label.
  * Contextual search.
  * Profile dropdown.

### 5. Sections overview

For each section, 1–2 paragraphs and link to the detailed doc:

* **Documents** (doc 07).
* **Jobs** (doc 07).
* **Config Builder** (docs 08–09).
* **Settings** (doc 05 for RBAC + this for UX).
* **Overview** (optional).

Mention, briefly:

* Primary goals of each section.
* Typical entry points from other sections.

### 6. Global banners & notifications

* Where safe mode banners render (inside workspace shell).
* Where error/info banners appear for cross-cutting issues.
* Where toast notifications originate and what they’re used for.
