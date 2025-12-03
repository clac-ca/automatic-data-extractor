# 090-FUTURE-WORKSPACES.md  
**ADE Web – Future Workspace UX & Architecture (Phase 2)**

---

## 1. Status & Purpose

This document captures our **decision to defer workspace UX** (selector, creation, switching, settings) to a **separate phase** and outlines how we intend to build it later, once the new ade-web core is stable.

It exists so that:

- The current refactor (010-WORK-PACKAGE) can stay focused and ship.  
- We don’t forget the constraints and design goals for multi-workspace support.  
- Future work can plug into the existing architecture cleanly, without redesigning Documents/Configs/Runs.

> **Current status:**  
> - The new ade-web architecture is **workspace-aware** (all major routes take a `workspaceId`).  
> - There is **no user-facing workspace selector/creation UI** yet.  
> - Workspace UX is intentionally **out of scope** for the current workpackage and will be handled here.

---

## 2. Decision Summary

### 2.1 What we decided

For the initial ade-web rebuild:

- **We will not implement:**
  - Workspace selection screen.
  - Workspace creation flow.
  - Workspace switching UI (e.g., header dropdown).
  - Workspace settings or membership management.

- **We will implement:**
  - Screens and navigation that assume a **single, known `workspaceId`**.
  - Route shapes and APIs that are **workspace-scoped**.
  - Clean layering so workspace UX can be added without rewiring streaming, Documents, or Config Builder.

### 2.2 Why we decided this

- The rebuild is already large: new architecture, design system, streaming, Documents, Config Builder, Run Detail.
- Workspace UX is strategically important but **orthogonal**:
  - It doesn’t affect how runs stream.
  - It doesn’t affect Documents/Run Detail mechanics.
  - It’s mostly about **entry, switching, and onboarding**.
- We want to design workspace UX once we:
  - Understand how teams actually use ade (1 vs many workspaces).
  - Clarify permissions and ownership semantics.
- The current architecture already passes `workspaceId` through routes, so workspace UI can be layered on top later without breaking changes.

---

## 3. Assumptions & Context

### 3.1 Architectural assumptions

- All core routes in `060-NAVIGATION.md` include `workspaceId`:
  - `documents`, `document`, `runDetail`, `configBuilder`, etc.
- Data fetching is workspace-scoped:
  - `listDocuments(workspaceId)`, `listConfigs(workspaceId)`, etc.
- The app can be run in a **“single workspace mode”** (environment or bootstrapping picks one workspace).

### 3.2 Product assumptions (for now)

- Many users will effectively work in a **single workspace** initially.
- Advanced multi-workspace scenarios (projects/clients/orgs) are important, but not required to unlock the main value of:
  - Uploading documents.
  - Running configs.
  - Reviewing outputs/logs.

If these assumptions change (e.g., users have dozens of workspaces and switch constantly), this doc should be revisited.

---

## 4. Goals for Future Workspace UX

When we do build first-class workspace support, we want:

1. **Clear workspace context**  
   - Users always know which workspace they’re in.
   - The workspace context is visible in AppShell, not buried.

2. **Simple creation & onboarding**  
   - First-time users can create a workspace easily (“Create your first workspace”).
   - Existing users can add new workspaces from a clear entry point.

3. **Easy switching (when needed)**  
   - Users with multiple workspaces can switch from a header-level control.
   - Switching feels like a “root context” change, not a random navigation.

4. **Graceful error handling**  
   - Invalid or unauthorized workspace IDs show friendly error states.
   - Users are guided back to a list of their accessible workspaces.

5. **Minimal coupling**  
   - Workspace UX is layered on top of the existing routing and feature modules.
   - Documents/Configs/Runs stay focused on their domain, not on workspace logic.

---

## 5. Non‑Goals (for Phase 2)

To keep the future workspace work contained:

- No advanced **permissions UI** (role management, invites, etc.) unless backend and product are ready.
- No complex **organization hierarchy** (orgs > projects > workspaces) – treat “workspace” as the top unit.
- No cross-workspace analytics or dashboards in v1 of this feature.

Those can be separate future workpackages.

---

## 6. How the Current Design Supports Future Workspaces

The current ade-web refactor (010-WORK-PACKAGE.md + supporting docs):

- Uses a **typed route model** where `workspaceId` is explicit.
- Scopes feature APIs by `workspaceId` (documents, configs, runs).
- Keeps navigation logic in one place (`NavigationProvider` + route registry).
- Treats Workspace Home as a **per-workspace landing page**.

This means when we add:

- `/workspaces` (list)
- `/workspaces/new` (creation)
- A `WorkspaceSwitcher` in the header

We do **not** need to:

- Change how Documents/Config Builder/Run Detail fetch data.
- Change how Run streaming works.
- Change core architecture or streaming spec.

Workspace UX will hook into the existing navigation and contexts.

---

## 7. Future Feature Sketch – Workspace Support

This section outlines what we’re likely to build in a future workpackage. It’s not a commitment yet, but a **preferred direction**.

### 7.1 New Routes

Extend the route union (in `060-NAVIGATION.md`) to include:

```ts
type Route =
  | { name: 'workspaceList'; params: {} }
  | { name: 'workspaceCreate'; params: {} }
  | { name: 'workspaceHome'; params: { workspaceId: string } }
  | { name: 'documents'; params: { workspaceId: string } }
  | { name: 'document'; params: { workspaceId: string; documentId: string } }
  | { name: 'runDetail'; params: { workspaceId: string; runId: string; sequence?: number } }
  | { name: 'configBuilder'; params: { workspaceId: string; configId: string } };
````

Example URLs:

* List: `/workspaces`
* New: `/workspaces/new`
* Workspace Home: `/workspaces/:workspaceId`

### 7.2 Workspace Data & Context

New feature module: `features/workspaces/`:

* `workspacesApi.ts`:

  * `listWorkspaces()`
  * `createWorkspace(payload)`
  * `getWorkspace(workspaceId)` (optional)
* `useWorkspaceList()`:

  * Provides current user’s workspaces.
* `useCurrentWorkspace()`:

  * Derives workspace from route + list, or returns error/undefined.
* `WorkspaceGuard`:

  * Ensures a valid workspace exists for workspace-scoped routes.
  * Handles:

    * Unknown workspace → redirect to `/workspaces`.
    * No workspaces at all → redirect to `/workspaces/new`.

### 7.3 Workspace Switcher

Add to `AppShell` header:

* A `WorkspaceSwitcher` component that shows:

  * Current workspace name.
  * Dropdown listing other workspaces.
  * “Create workspace…” at the bottom.

On selection:

* Calls `navigate({ name: 'workspaceHome', params: { workspaceId } })`.

### 7.4 Workspace List & Creation UX

**Workspace List Screen** (`/workspaces`):

* Title: “Your Workspaces”.
* Card list:

  * Workspace name.
  * Last activity (recent run/doc change).
  * Primary action: “Open workspace”.
* Primary button: “Create workspace”.

**Workspace Creation Screen** (`/workspaces/new`) or dialog:

* Simple form:

  * Workspace name (required).
  * Optional description.
* On submit:

  * Call `createWorkspace`.
  * Navigate to new workspace’s home.

### 7.5 First-Time User Flow

When a user logs in and:

* Has **0 workspaces**:

  * Redirect to `/workspaces/new`.
  * Show “Welcome to ADE – create your first workspace” copy.
* Has **1 workspace**:

  * Redirect directly to that workspace’s home (e.g., `/workspaces/:id/documents`).
* Has **>1 workspace**:

  * Land on `/workspaces` to choose, or use last-used workspace (TBD).

---

## 8. Risks & Open Questions

* **Permissions / multi-tenant model:**

  * Who can create workspaces?
  * Are workspaces tied to orgs, users, or both?
* **Workspace naming & identifiers:**

  * Are slugs user-controlled or system-generated?
  * Are there constraints (unique names per user/org)?
* **Frequency of switching:**

  * Are users expected to switch frequently (like projects) or rarely (like orgs)?
  * This affects whether the switcher sits in the global header vs deeper in navigation.

These are product/backend questions that should be answered before workspace UX is implemented.

---

## 9. How to Use This Document

* **Now (during the refactor):**

  * Treat workspace UX as **explicitly out-of-scope**.
  * Ensure core codepaths keep `workspaceId` explicit and easy to thread through.

* **Later (when ready for workspace UX):**

  * Use this document as the starting point for a **new workpackage**, e.g.:

    * `./workpackages/ade-web-workspaces/010-WORK-PACKAGE.md`
  * Lift the relevant sections (routes, flows, components) into that new WP.
  * Update `060-NAVIGATION.md` and `030-UX-FLOWS.md` with workspace-specific details.

---

## 10. Summary

* The current refactor is **safe** to ship without workspace selector UX.
* The architecture is **workspace-ready** (routes & data are scoped).
* This doc preserves a thought-through path for:

  * Workspace list & creation.
  * Workspace switching.
  * First-time user onboarding.
  * Graceful handling of invalid/inaccessible workspaces.

When the time comes, we’ll spin up a focused “workspace UX” workpackage and implement these ideas on top of the new ade-web foundation.