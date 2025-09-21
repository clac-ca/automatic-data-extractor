# ADE frontend master blueprint

Great products feel inevitable. This blueprint distils ADE's core product truths, clarifies the first-release user journey, and
translates that intent into UI structure the team can implement without guesswork. Experiments and "nice to haves" live in the
backlog. The blueprint below focuses on the surfaces and dependencies required to ship a confident, maintainable v1.

---

## 1. Purpose & scope

- **Source of truth** – When questions arise about how ADE's frontend should look, feel, or behave, this file provides the answer.
- **Scope** – Web frontend only: information architecture, interaction patterns, component strategy, and integration touchpoints
  with backend services.
- **Change hygiene** – Treat edits like code. Capture the reason for each change so future contributors understand the context and
  can revisit assumptions.

---

## 2. Product truths & design posture

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

### 3.2 Global UI cues
- Breadcrumbs mirror the hierarchy (`Workspace / Invoice / Config v3 / Column: Due Date`).
- Status chips reuse the same colors across lists, detail views, and comparison matrices.
- Metadata rails surface lineage (who activated, when, diff summary) to maintain auditability.

---

## 4. Application shell & navigation

- **Frame** – Persistent left navigation paired with a top utility bar keeps primary routes visible without crowding content. The
  shell adapts between three breakpoints (desktop ≥1280 px, laptop ≥1024 px, tablet ≥768 px) with drawers replacing the nav on
  smaller widths.
- **Left navigation** – Sections: *Document Types*, *Runs*, *Settings*. Nav items expose badge counts for drafts needing
  attention and recently failed runs.
- **Top utility bar** – Shows workspace selector, search (global entity lookup), user menu, and system notices. The search opens a
  command palette style overlay for quick navigation.
- **Primary content area** – Uses a page header (title, status, key actions) followed by contextual tabs or split panes depending
  on the surface.
- **Feedback** – Toasts appear above the content area, anchored near the top-right. Long-running processes expose inline progress
  indicators rather than blocking modals.

---

## 5. Primary surfaces & layouts

### 5.1 Document type library
- **Goal** – Quickly understand which document types exist, their health, and entry points into configuration work.
- **Layout** – Page header with “Create document type” button and filters (status, owner). Below, a full-width table (TanStack
  Table + virtualization) listing type name, active configuration, draft count, and last run summary.
- **Row interaction** – Row click opens the detail view; inline actions include duplicate, archive (if unused), and view active
  configuration. Needs Attention rows surface a left border accent and tooltip summarizing issues.
- **Empty state** – Illustrative zero state with a single CTA to create the first document type.

### 5.2 Document type detail & configuration list
- **Goal** – Inspect a document type, switch between configurations, and launch new iterations.
- **Layout** – Two-pane arrangement: a left rail lists configurations (status chip, updated timestamp, owner), while the right
  pane shows the selected configuration summary.
- **Summary pane** – Displays activation metadata, diff summary versus previous active version, and quick metrics (last run pass
  rate). Primary actions: *Open workspace*, *Promote to active* (for published drafts), and *Download spec*.
- **Creation flow** – A simple modal form collects name and description, with optional copy-from dropdown. Avoid multi-step
  wizards until column counts justify them.

### 5.3 Configuration workspace
- **Goal** – Author and validate extraction logic for each column with minimal context switching.
- **Layout** – Three-column responsive grid:
  1. **Column list** – Compact table with column name, type, readiness badge, and quick filters (ready, needs attention, hidden).
  2. **Editor canvas** – Tabbed interface hosting Monaco for detection/validation/transformation callables. Tabs share layout so
     keyboard shortcuts remain consistent. Inline test results appear beneath the editor with expandable log output.
  3. **Inspector rail** – Shows metadata (description, sample values, validation checks). Actions include mark optional/required
     and view column-level history.
- **Header** – Sticky bar with configuration name, status chip, autosave indicator, publish button, and link to comparison preview.
- **Testing** – “Run test” button triggers backend validation for the focused column. Results stream into the inline panel and
  update the column readiness badge.

### 5.4 Upload & run console
- **Goal** – Manage uploads, select configurations, and monitor run progress without leaving the page.
- **Layout** – Split view:
  - **Left pane** – Drop zone for files, queue list with status icons (Queued, Uploading, Processing, Failed). Each item exposes
    a context menu to retry, remove, or view logs.
  - **Right pane** – Run setup form (configuration multi-select, run name/notes) followed by a timeline showing progress events.
    WebSocket updates append to the timeline; failures pin an alert at the top with remediation guidance.
- **Edge handling** – Offline detection pauses uploads and surfaces a banner. Resume occurs automatically when connectivity
  returns.

### 5.5 Run results & comparison view
- **Goal** – Validate output accuracy and approve promotions with confidence.
- **Layout** – Page header summarizing run outcome (status, duration, triggering user) plus buttons for rerun, share link, and
  promote/revert actions (if applicable).
- **Primary content** – Tab set with two modes:
  1. **Results table** – Virtualized grid showing extracted rows. Columns support pinning, column-level validation messages, and
     inline filters. Hover reveals source document preview thumbnails when available.
  2. **Diff & validation** – Side-by-side comparison between the current run and baseline (active configuration). Differences use
     color-coded highlights; validation issues stack in a collapsible list with deep links back to the configuration workspace.
- **Audit trail** – Right rail surfaces run metadata (configuration version, dataset used) and activity log entries.

---

## 6. Interaction patterns & component strategy

- **Forms** – React Hook Form backed by Zod schemas for type-safe validation. Use inline validation messages and disable
  submission until required fields pass.
- **Tables & lists** – TanStack Table provides sorting, filtering, and virtualization. Keep column renderers pure; expensive
  formatting (dates, numbers) should leverage native `Intl` APIs.
- **Editors** – `@monaco-editor/react` powers script editing with shared configuration per callable. We wrap it in a `ScriptEditor`
  component that syncs theme tokens and exposes `onRunTest`/`onFormat` hooks.
- **Panels & drawers** – Radix UI primitives (Dialog, Drawer, Popover) ensure accessibility without heavy styling overhead.
- **Global feedback** – Reuse a toast system for success/error notifications and a lightweight confirmation dialog for destructive
  actions. Long-running actions display inline progress components instead of blocking modals.
- **Keyboard support** – Provide shortcuts for switching editor tabs, triggering tests, and navigating tables. Focus outlines must
  remain visible at all times.

---

## 7. Technology & dependency plan

| Dependency | Decision | Rationale |
| --- | --- | --- |
| Vite, React, TypeScript | ✅ Adopt | Proven trio for fast feedback and a TypeScript-first workflow. |
| React Router v6 data APIs | ✅ Adopt | Nested layouts and loader/action model align with our route structure and error handling needs. |
| @tanstack/react-query | ✅ Adopt | Centralizes server state, caching, and request lifecycle handling. |
| React Hook Form + Zod | ✅ Adopt | Lightweight, type-safe form management mirroring backend validation rules. |
| @tanstack/react-table + @tanstack/react-virtual | ✅ Adopt | Composable tables with virtualization for large results sets. |
| @monaco-editor/react | ✅ Adopt | IDE-grade script editing with minimal integration code. |
| Radix UI primitives | ✅ Adopt | Accessible building blocks we can skin to ADE’s design language. |
| Storybook | ✅ Adopt | Local component workbench and spec documentation for shared components. |
| Playwright | ✅ Adopt | Deterministic end-to-end and visual regression coverage without SaaS lock-in. |
| File upload helpers (Uppy / tus-js-client) | 🔍 Investigate later | Start with native `fetch` + chunking; introduce a helper only if resumable uploads prove complex. |

We deliberately avoid Redux-like global state, heavyweight charting libraries, or bespoke design systems until the core surfaces
ship and justify them.

---

## 8. Data & state management

- **HTTP client** – Typed wrapper around `fetch` with abort controller support lives in `frontend/src/lib/apiClient.ts`.
- **Query structure** – React Query keys follow `['workspace', workspaceId, 'documentTypes']` patterns. Mutations invalidate the
  narrowest scope necessary (e.g., column update invalidates the configuration detail and column list only).
- **Normalisation** – Mutations return normalized objects so UI components render deterministically without manual refetches.
- **Optimistic updates** – Reserved for safe fields (names, descriptions). Risky actions (publish, promote) wait for server
  confirmation.
- **Error handling** – Route-level error boundaries surface friendly copy and retry controls; global errors route to a support
  panel with context.
- **Local persistence** – Typed helpers gate access to `localStorage`/`sessionStorage` for ephemeral settings (theme preference,
  table column visibility). Avoid storing business data client-side.

---

## 9. Implementation roadmap (v1 focus)

1. **Foundation sprint**
   - Scaffold Vite + React + TypeScript with Router, React Query, Vitest, Playwright, and Storybook wired into CI.
   - Build application shell (navigation, header, toast system) with placeholder routes.
2. **Document type surfaces**
   - Implement library table with filtering, needs-attention cues, and creation modal.
   - Deliver document type detail view with configuration list rail and summary panel.
3. **Configuration workspace**
   - Ship column list + inspector layout, Monaco-based editor tabs, and inline testing workflow.
   - Wire autosave via React Query mutations and publish/promotion flows.
4. **Run management & results**
   - Build upload console with queue, run setup form, and WebSocket-driven progress timeline.
   - Implement results/diff view with virtualized tables, validation issue stack, and deep links back to the workspace.

Each milestone includes UX review, accessibility checks, and regression tests before handoff.

---

## 10. Immediate design & engineering deliverables

1. Low-fidelity wireframes for the five primary surfaces highlighting layout, hierarchy, and responsive breakpoints.
2. Component inventory covering navigation shell, tables, script editor, inspectors, and toast system with state variations.
3. Data contract outline describing required endpoints for document types, configurations, runs, column tests, and diff payloads.
4. Theme token map (`spacing`, `color`, `typography`) shared between the application shell and Monaco theme implementation.

---

This document evolves with user insights. Keep revisions versioned so designers, engineers, and AI agents stay aligned while
bringing ADE’s core UI to life.
