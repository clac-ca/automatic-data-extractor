# ADE frontend core blueprint

ADE's frontend must make complex extraction workflows feel approachable. This document captures the minimum structure we need to
ship a credible v1: which screens exist, how they are laid out, which dependencies unlock velocity, and what the backend must
provide. Anything outside these foundations can wait.

---

## 1. Purpose & scope

- **Source of truth** – Defines layout, interaction patterns, and supporting tooling for ADE's web client.
- **Scope** – Desktop-first React application. Mobile portrait layouts and onboarding flows are intentionally out of scope.
- **Change hygiene** – Update this file with rationale whenever we refine layout decisions or add dependencies.

---

## 2. Product truths & guardrails

### 2.1 Why ADE exists
- Turn messy spreadsheets/PDFs into trustworthy tables with auditable logic.
- Let operations teams iterate, compare, and promote extraction logic without touching backend code.

### 2.2 First principles
1. **Immediate clarity** – Each surface answers “What is this and what changed?” before exposing controls.
2. **Confidence while iterating** – Users should see progress, test outcomes, and promotion states without hunting.
3. **Deterministic actions** – Buttons and shortcuts do exactly what they say; avoid cleverness that obscures state.

### 2.3 Anti-goals
- No dense data dumps without framing copy or empty-state guidance.
- No destructive actions hidden behind icons or nested menus.
- Minimize modal usage; prefer inline rails/drawers so spatial context remains intact.

### 2.4 Personas anchoring decisions
| Persona | Core needs | Success signal |
| --- | --- | --- |
| **Operations Lead** | Governance, approvals, adoption metrics. | Can review readiness and approve promotions without code. |
| **Configuration Engineer** | Author scripts, debug failures, iterate quickly. | Can edit, test, and publish callables in one workspace. |
| **Reviewer / Analyst** | Upload docs, validate outputs, compare revisions. | Can confirm fixes and spot regressions quickly. |

---

## 3. Domain model & key states

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

| Entity | Lifecycle states | Notes |
| --- | --- | --- |
| Configuration | Draft → Published → Active → Retired | Only one Active per Document Type. Promotions flow Draft → Published → Active. |
| Column | Ready ↔ Needs Attention | Needs Attention indicates missing callables, failing tests, or deprecated APIs. |
| Run | Queued → Running → Validating → Complete / Failed | Metadata flags (e.g., `needsApproval`) augment but never override states. |

Document types are logical containers without lifecycle. Governance metadata lives on configurations and columns.

---

## 4. Application shell & layout primitives

### 4.1 Shell structure
- **Navigation** – Persistent left rail with sections: *Document Types*, *Runs*, *Settings*. Collapse to a slide-in drawer ≤1024 px.
- **Top bar** – Workspace selector, user menu, and inline system notices. No command palette in v1.
- **Content frame** – Page header (title, status chip, critical actions) followed by body area arranged with CSS grid using an 8 px spacing scale.
- **Feedback** – Toast stack in the upper-right of the content frame. Long-running actions surface inline progress rows, not blocking modals.

### 4.2 Layout primitives
- Define lightweight `Stack`, `Columns`, and `Sidebar` components backed by CSS variables from `frontend/src/styles/tokens.ts`.
- Tokens cover color, spacing, radius, typography, and elevation. Dark mode can follow later if we choose colors with accessible contrast out of the gate.

---

## 5. Core product surfaces

Each surface description includes layout, must-have interactions, and implementation notes so engineers can size work accurately.

### 5.1 Document type library
- **Purpose** – Discover document types, assess health, and jump into work.
- **Layout** – Page header with primary action “Create document type” and filters for status/owner. Below, a table listing name, active configuration, draft count, latest run summary, and attention badge.
- **Key interactions** – Row click opens detail view. Inline actions limited to “Open active configuration” and “Create new draft”.
- **Implementation notes**
  - Data from `GET /document-types` must include counts and last-run metadata; seed fixtures for empty/error states.
  - Table built with TanStack Table (no virtualization). Badges leverage Radix `Badge` primitives for consistency.

### 5.2 Document type detail
- **Purpose** – Inspect a document type, switch configurations, and launch new drafts.
- **Layout** – Two-pane view: left rail lists configurations (status chip, updated timestamp, owner); right pane shows summary of the selected configuration (description, readiness, recent run outcomes) with quick actions.
- **Key interactions** – Create configuration (modal with name + optional copy-from), promote published configuration to active, open configuration workspace.
- **Implementation notes**
  - Endpoint `GET /document-types/:id` returns metadata plus configuration list and promotion eligibility flags.
  - Promotion flow uses confirm dialog from Radix `AlertDialog`; optimistic updates avoided until backend confirms transition.

### 5.3 Configuration workspace
- **Purpose** – Author and validate column-level logic without leaving the screen.
- **Layout** – Three-column grid on desktop, collapsing to stacked panes ≤1280 px:
  1. **Column list** – Compact list with readiness filter chips (all, ready, needs attention).
  2. **Editor canvas** – Tabbed Monaco editor for detection/validation/transformation scripts; inline test results expand below the editor.
  3. **Inspector rail** – Metadata (description, type, sample values) and switches (optional/required). Read-only history list sits at the bottom.
- **Key interactions** – Autosave edits with debounce, execute column test, publish configuration, view change history.
- **Implementation notes**
  - Use React Query mutations for autosave + invalidation; persist unsaved state indicator in the header.
  - `POST /configurations/:id/columns/:columnId/test` powers inline test results; ensure backend payload includes logs and sample output.
  - Monaco editor packaged via `@monaco-editor/react` with custom theme derived from tokens.

### 5.4 Upload & run console
- **Purpose** – Queue documents, select configurations, and monitor run progress.
- **Layout** – Split view: left pane hosts drag-and-drop queue with file status list; right pane holds run setup form (configuration multi-select, run name, notes) and a progress timeline beneath.
- **Key interactions** – Add/remove files, start run, observe live progress, retry failed documents.
- **Implementation notes**
  - Uploads use native `fetch` with chunking; wrap in a `FileQueue` helper that exposes derived statuses for React Query.
  - Run creation via `POST /runs`; progress stream delivered over Server-Sent Events (`/runs/:id/stream`) with polling fallback for browsers lacking SSE.
  - Timeline entries rendered with Radix `Accordion` for expandable log details.

### 5.5 Run results & comparison
- **Purpose** – Validate output accuracy and compare against baseline runs.
- **Layout** – Header summarizing status, duration, triggering user. Tabs: **Results** (data grid) and **Diff** (side-by-side comparison against baseline configuration).
- **Key interactions** – Toggle tabs, filter results, export CSV, mark run as reviewed, deep-link to configuration workspace.
- **Implementation notes**
  - Results grid uses TanStack Table plus `@tanstack/react-virtual` for large datasets; load data in paged chunks from `GET /runs/:id/results`.
  - Diff view consumes `GET /runs/:id/diff` and renders column-level highlights; reuse tokenized colors for additions/removals to maintain accessibility.
  - “Mark as reviewed” mutation updates run metadata and invalidates relevant caches.

---

## 6. Interaction patterns & component layering

- **Forms** – React Hook Form + Zod for validation; errors show on blur or submit. Submit buttons disable while pending to prevent duplicate mutations.
- **Tables & lists** – TanStack Table for sorting/filtering; use shared table components that handle loading, empty, and error states.
- **Script editing** – Wrap Monaco in a `ScriptEditor` component controlling language mode, theme, lint annotations, and `onRunTest` wiring.
- **File input** – Drag-and-drop built on native `DataTransfer`. Custom hook owns chunking logic and surfaces queue state to UI components.
- **Feedback** – Toast provider for global success/error, inline `Callout` component for contextual warnings, `AlertDialog` for destructive confirmation.
- **Keyboard support** – Provide shortcuts for switching editor tabs and triggering tests; always preserve visible focus outlines using tokens.

---

## 7. Dependencies & tooling decisions

| Dependency | Decision | Rationale |
| --- | --- | --- |
| Vite, React, TypeScript | ✅ Adopt | Fast feedback loop and TS-first developer experience. |
| React Router v6 data APIs | ✅ Adopt | Nested layouts + loader/action pattern match our route structure and error handling needs. |
| @tanstack/react-query | ✅ Adopt | Manages server state, caching, and mutation lifecycles with minimal boilerplate. |
| React Hook Form + Zod | ✅ Adopt | Lightweight, type-safe forms aligned with backend validation. |
| Radix UI primitives | ✅ Adopt | Accessible building blocks for modals, tabs, accordions, and badges without custom a11y work. |
| @tanstack/react-table | ✅ Adopt | Headless table utilities reused across library and results screens. |
| @tanstack/react-virtual | ✅ Adopt (Results view only) | Required to keep run results responsive with large datasets. |
| @monaco-editor/react | ✅ Adopt | Script editing with minimal integration cost. |
| Storybook | ✅ Adopt | Component workbench for shared primitives (navigation, table states, toasts). |
| Playwright | ✅ Adopt | Deterministic end-to-end and smoke tests for critical flows. |
| File upload helpers (Uppy / tus-js-client) | ⏸️ Defer | Native chunked uploads are sufficient until we hit resumable/parallel needs. |

---

## 8. Data & state management

- **HTTP client** – Typed wrapper around `fetch` with AbortController support lives in `frontend/src/lib/apiClient.ts`.
- **Query keys** – Follow `['workspace', workspaceId, 'documentTypes']` patterns; invalidate only scopes impacted by a mutation.
- **Normalization** – API responses return normalized objects so UI can update deterministically without manual refetches.
- **Optimistic updates** – Restrict to low-risk fields (names, descriptions). Publishing/promoting waits for backend confirmation.
- **Error handling** – Route-level error boundaries with retry controls; global errors surface in a dedicated support panel with context.
- **Local persistence** – Only store UI preferences (e.g., table column visibility) in `localStorage` via typed helpers.

---

## 9. Pre-build requirements

1. **API contracts** – Backend confirms payload shape for document types, configurations, columns, runs, and diff responses before API hooks are written.
2. **Fixtures** – Provide anonymized data for empty, loading, and failure states across key surfaces to unblock Storybook states.
3. **Design tokens** – Finalize color palette, typography scale, and spacing tokens before component build-out to avoid churn.
4. **Testing hooks** – Backend exposes stable IDs/attributes (e.g., run IDs) so Playwright tests can target elements reliably.
5. **Environment parity** – Local `.env` aligns with staging domains to keep React Query cache keys and CORS expectations consistent.

---

## 10. Implementation path (v1 focus)

1. **Foundation**
   - Scaffold Vite + React + Router + React Query with Vitest, Storybook, and Playwright wired into CI.
   - Build application shell (navigation, top bar, toast system) and implement design tokens/layout primitives.
2. **Document type views**
   - Implement library table with filters and creation modal.
   - Deliver detail view with configuration rail and summary panel.
3. **Configuration workspace**
   - Ship column list, Monaco editor tabs, inspector rail, autosave, and inline testing workflow.
   - Add publish/promote flows with confirmation dialogs.
4. **Run management & results**
   - Build upload console with queue, run setup form, and SSE-driven progress timeline.
   - Implement results/diff view with paged table, virtualization, validation stack, and deep links back to workspace.

Each milestone includes accessibility review and regression tests before handoff.

---

## 11. Explicitly out of scope for v1

- Onboarding tours, contextual walkthroughs, marketing pages.
- Global search or command palette.
- Real-time collaboration, presence indicators, annotations, or comments.
- Mobile portrait layouts.
- Advanced analytics dashboards or bespoke visualizations.

Keep this document current as we learn from users. Clear rationale prevents churn and keeps engineering, design, and AI agents aligned while we deliver ADE’s core UI.
