# ADE frontend master blueprint

Great products feel inevitable. This blueprint narrows ADE's frontend down to the essential surfaces we must ship for a credible
v1. Nice-to-haves (onboarding tours, advanced analytics, bespoke visualizations) live in the backlog. The focus here is
structuring the core UI, clarifying dependencies, and ensuring engineering can move without second-guessing intent.

---

## 1. Purpose & scope

- **Source of truth** – When questions arise about how ADE's frontend should look, feel, or behave, this file provides the answer.
- **Scope** – Web frontend only: information architecture, interaction patterns, component strategy, and integration touchpoints
  with backend services.
- **Change hygiene** – Treat edits like code. Capture the reason for each change so future contributors understand the context and
  can revisit assumptions.

---

## 2. Product truths & guardrails

### 2.1 Why ADE exists
- Convert messy spreadsheets/PDFs into trustworthy tables without opaque automation.
- Give operations teams confidence to iterate, compare, and promote extraction logic safely.

### 2.2 First principles
1. **Clarity first** – Every surface should answer “What am I looking at?” before exposing controls.
2. **Progress with reassurance** – Users always know what changed, what is running, and how to undo it.
3. **Iteration is the happy path** – Testing, comparing, and promoting configurations should feel routine, not advanced.

### 2.3 Experience anti-goals
- Avoid dense data dumps without framing copy or clear next steps.
- Never hide destructive actions behind ambiguous icons; clarity beats minimalism when stakes are high.
- Resist modal overload—prefer inline rails/drawers so users maintain spatial orientation.

### 2.4 Personas anchoring decisions
| Persona | Core needs | Success signal |
| --- | --- | --- |
| **Operations Lead** | Governance, approvals, adoption metrics. | Can review readiness and approve promotions without digging into code. |
| **Configuration Engineer** | Scripting, debugging, rapid iteration. | Can author, test, and publish callables without context switching. |
| **Reviewer / Analyst** | Uploading docs, validating, comparing results. | Can spot regressions and confirm fixes quickly. |

---

## 3. System mental model

```
Workspace (tenant)
└── Document Type (stable container for configurations)
    └── Configuration (versioned; one active at a time)
        └── Column (metadata + callable scripts)
            ├── Detection callable (required)
            ├── Validation callable (optional)
            └── Transformation callable (optional)
└── Run (executes one or more configurations on uploaded docs)
```

### 3.1 State vocabulary
| Entity | States | Notes |
| --- | --- | --- |
| Configuration | Draft → Published → Active → Retired | Only one Active per Document Type. Promotions always flow through Published. |
| Column | Ready ↔ Needs Attention | Needs Attention surfaces missing callables, failing tests, or deprecated APIs. |
| Run | Queued → Running → Validating → Complete / Failed | Metadata flags (e.g., `needsApproval`) accompany states but never mutate them. |

Document types do **not** have a lifecycle—they are logical containers. Governance metadata lives on configurations and columns.

---

## 4. Foundational layout decisions

### 4.1 Application shell
- **Structure** – Persistent left navigation paired with a top utility bar keeps primary routes visible without crowding content.
  On tablet widths (≤1024 px) the nav collapses into a slide-in drawer; phone support is out of scope for v1.
- **Navigation** – Sections: *Document Types*, *Runs*, *Settings*. Badge counts highlight drafts needing attention and failed
  runs. Search is deferred until we validate navigation pain points.
- **Top bar** – Shows workspace selector, current user menu, and system notices. Keep it shallow (no command palette) so we ship
  faster and avoid premature keyboard choreography.
- **Content area** – Each route renders a page header (title, status chip, key actions) followed by tabs or split panes depending
  on the surface. Use CSS grid with an 8 px spacing scale so components align predictably.
- **Feedback** – Toasts appear above the content area near the top-right. Long-running processes expose inline progress indicators
  rather than blocking modals.

### 4.2 Design tokens & theming
- Global tokens (`color`, `spacing`, `radius`, `typography`) live in `frontend/src/styles/tokens.ts` and power both component
  styling and Monaco's theme.
- Dark mode is not required for v1; choose colors that degrade gracefully if we add it later.
- Layout primitives (stack, cluster, sidebar) should be defined as lightweight components instead of ad-hoc flexbox in every
  screen.

---

## 5. Primary flows & surfaces

The tables below describe the minimum viable experience for launch. Anything beyond these bullets belongs in the backlog.

### 5.1 Document type library
- **Purpose** – Understand which document types exist, their health, and entry points into configuration work.
- **Layout** – Page header with “Create document type” button and filters (status, owner). Below, a responsive table listing type
  name, active configuration, draft count, last run summary, and attention badge.
- **Key interactions** – Row click opens the detail view. Inline actions limited to “Open active configuration” and “Create new
  draft” so we do not overcomplicate v1.
- **Data needs** – `GET /document-types` returns array with counts, most recent run status, and last updated timestamp.
- **Deferred** – Duplicating/archiving document types, bulk actions, and heavy virtualization come later once list size demands it.

### 5.2 Document type detail
- **Purpose** – Inspect a document type, switch between configurations, and launch new iterations.
- **Layout** – Two-pane arrangement: left rail lists configurations (status chip, updated timestamp, owner), right pane shows the
  selected configuration summary.
- **Key interactions** – Create configuration (modal form with name + optional copy-from), promote published configuration to
  active, open configuration workspace.
- **Data needs** – `GET /document-types/:id` returns metadata plus list of configurations with status, version tag, last run stats,
  and promotion eligibility.
- **Deferred** – Rich diff summaries and downloadable specs ship after the baseline experience is stable.

### 5.3 Configuration workspace
- **Purpose** – Author and validate extraction logic for each column with minimal context switching.
- **Layout** – Three-column grid on desktop, collapsing to stacked panes on smaller screens:
  1. **Column list** – Compact table with column name, type, readiness badge, and filter chips (ready, needs attention, hidden).
  2. **Editor canvas** – Tabbed Monaco editor for detection/validation/transformation callables. Inline test results appear beneath
     the editor with expandable log output.
  3. **Inspector rail** – Metadata (description, sample values, validation checks) and controls (mark optional/required, view
     column history).
- **Key interactions** – Autosave edits (React Query mutation with debounce), run column test, publish configuration, view change
  history (read-only list for v1).
- **Data needs** – Endpoints for columns (`GET/PUT /configurations/:id/columns/:columnId`), test execution (`POST
  /configurations/:id/columns/:columnId/test`), and configuration status transitions.
- **Deferred** – Live collaborative editing, inline diffing between draft versions, and comment threads.

### 5.4 Upload & run console
- **Purpose** – Manage uploads, select configurations, and monitor run progress without leaving the page.
- **Layout** – Split view with left pane for file queue (drag-and-drop area plus status list) and right pane for run setup
  (configuration multi-select, run name/notes) followed by a timeline of progress events.
- **Key interactions** – Add/remove files, start run, watch progress updates, retry failed documents.
- **Data needs** – Chunked upload API (`POST /runs/uploads`), run creation (`POST /runs`), progress feed (Server-Sent Events or
  WebSocket, whichever backend supports first), and log retrieval.
- **Deferred** – Offline detection, resumable uploads, and bulk schedule management. Polling + SSE gets us to v1 faster than a
  fully managed resumable library.

### 5.5 Run results & comparison
- **Purpose** – Validate output accuracy and approve promotions with confidence.
- **Layout** – Page header summarizing run outcome (status, duration, triggering user) plus tabs for **Results** and **Diff**.
  - **Results** – Virtualized data grid showing extracted rows, column-level validation messages, and inline filters.
  - **Diff** – Side-by-side comparison between the current run and baseline (active configuration). Differences use color-coded
    highlights; validation issues list links back to the configuration workspace.
- **Key interactions** – Toggle between tabs, export CSV, mark run as reviewed, jump to related configuration.
- **Data needs** – `GET /runs/:id/results` (paged data + validation metadata) and `GET /runs/:id/diff` (structured diff summary).
- **Deferred** – Document previews, custom charting, and shareable annotations.

---

## 6. Interaction patterns & component layering

- **Forms** – React Hook Form backed by Zod schemas for type-safe validation. Inline validation messages appear on blur. Submit
  buttons disable while pending to prevent duplicate mutations.
- **Tables & lists** – TanStack Table handles sorting/filtering. Start without virtualization; add `@tanstack/react-virtual` once
  performance requires it.
- **Script editing** – `@monaco-editor/react` wrapped in a `ScriptEditor` component controlling language, theme, validation
  overlays, and `onRunTest` hooks.
- **File input** – Native drag-and-drop (`DataTransfer`) with progressive enhancement. Wrap uploads in a `FileQueue` service that
  exposes derived status for React Query.
- **Feedback** – Global toast system for success/error, lightweight confirmation dialog for destructive actions, and inline alerts
  near the impacted component.
- **Keyboard support** – Provide shortcuts for switching editor tabs, triggering tests, and navigating tables. Always preserve
  visible focus outlines.

---

## 7. Technology & dependency plan

| Dependency | Decision | Rationale |
| --- | --- | --- |
| Vite, React, TypeScript | ✅ Adopt | Proven trio for fast feedback and a TypeScript-first workflow. |
| React Router v6 data APIs | ✅ Adopt | Nested layouts and loader/action model align with our route structure and error handling needs. |
| @tanstack/react-query | ✅ Adopt | Centralizes server state, caching, and request lifecycle handling. |
| React Hook Form + Zod | ✅ Adopt | Lightweight, type-safe form management mirroring backend validation rules. |
| @tanstack/react-table | ✅ Adopt | Composable tables with headless primitives that match our data needs. |
| @tanstack/react-virtual | ⏸️ Defer | Only introduce once result sets are large enough to require virtualization. |
| @monaco-editor/react | ✅ Adopt | IDE-grade script editing with minimal integration code. |
| Radix UI primitives | ✅ Adopt | Accessible building blocks we can skin to ADE’s design language. |
| Storybook | ✅ Adopt | Local component workbench and spec documentation for shared components. |
| Playwright | ✅ Adopt | Deterministic end-to-end and visual regression coverage without SaaS lock-in. |
| File upload helpers (Uppy / tus-js-client) | ⏸️ Defer | Start with native fetch + chunking; revisit if resumable uploads prove complex. |

We deliberately avoid Redux-like global state, heavyweight charting libraries, or bespoke design systems until the core surfaces
ship and justify them.

---

## 8. Data & state management

- **HTTP client** – Typed wrapper around `fetch` with abort controller support lives in `frontend/src/lib/apiClient.ts`.
- **Query structure** – React Query keys follow `['workspace', workspaceId, 'documentTypes']` patterns. Mutations invalidate the
  narrowest scope necessary (e.g., column update invalidates the configuration detail and column list only).
- **Normalisation** – Mutations return normalized objects so UI components render deterministically without manual refetches.
- **Optimistic updates** – Reserve for safe fields (names, descriptions). Risky actions (publish, promote) wait for server
  confirmation.
- **Error handling** – Route-level error boundaries surface friendly copy and retry controls; global errors route to a support
  panel with context.
- **Local persistence** – Typed helpers gate access to `localStorage`/`sessionStorage` for ephemeral settings (theme preference,
  table column visibility). Avoid storing business data client-side.

---

## 9. Pre-build requirements & assumptions

1. **Data contracts** – Backend must confirm payloads for document types, configurations, columns, runs, and diff responses before
   we wire any API calls.
2. **Sample data** – Provide anonymized fixtures for each primary surface so we can stub UI states (empty, success, error) without
   guessing field names.
3. **Design tokens** – Agree on the initial color/typography scale with design so component styling does not churn mid-sprint.
4. **Testing hooks** – Backend exposes predictable IDs or attributes where end-to-end tests need to anchor (e.g., upload job IDs).
5. **Environment parity** – Local `.env` mirrors staging domains to keep React Query cache keys and CORS expectations consistent.

---

## 10. Implementation roadmap (v1 focus)

1. **Foundation sprint**
   - Scaffold Vite + React + TypeScript with Router, React Query, Vitest, Playwright, and Storybook wired into CI.
   - Build application shell (navigation, header, toast system) with placeholder routes and design tokens.
2. **Document type surfaces**
   - Implement library table with filtering and creation modal.
   - Deliver document type detail view with configuration rail and summary panel.
3. **Configuration workspace**
   - Ship column list + inspector layout, Monaco-based editor tabs, autosave, and inline testing workflow.
   - Wire publish/promote flows with confirmation dialogs.
4. **Run management & results**
   - Build upload console with queue, run setup form, and SSE-driven progress timeline.
   - Implement results/diff view with table, validation issue stack, and deep links back to the workspace.

Each milestone includes UX review, accessibility checks, and regression tests before handoff.

---

## 11. Explicitly out of scope for v1

- Onboarding tours, contextual walkthroughs, or marketing pages.
- Global command palette or fuzzy entity search.
- Real-time collaboration, presence indicators, or comments.
- Mobile portrait layouts.
- Advanced analytics dashboards or custom visualization suites.

This document evolves with user insights. Keep revisions versioned so designers, engineers, and AI agents stay aligned while
bringing ADE’s core UI to life.
