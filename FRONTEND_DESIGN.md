# ADE frontend core blueprint

ADE's frontend must make complex extraction workflows feel approachable. This document captures the minimum structure we need to ship a credible v1: which screens exist, how they are laid out, which dependencies unlock velocity, and what the backend must provide. Anything outside these foundations can wait.

---

## 1. Purpose & scope

- **Source of truth** – Defines layout, interaction patterns, and supporting tooling for ADE's web client.
- **Scope** – Desktop-first React application built for analysts and engineers. Mobile portrait layouts, onboarding tours, and growth features remain out of scope for the first release.
- **Change hygiene** – Update this file with rationale whenever we refine layout decisions, add dependencies, or adjust API expectations.

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
- Minimize blocking modals; prefer inline rails or drawers to preserve context.

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

## 4. Layout architecture

### 4.1 Application shell
- **Navigation** – Persistent left rail with sections: *Document Types*, *Runs*, *Settings*. Collapse to an overlay drawer ≤1024 px while keeping top-level links available inside the drawer header.
- **Top bar** – Hosts workspace selector, user menu, inline system notices, and an unsaved-change indicator tied to the active route’s form state. No command palette in v1.
- **Content frame** – Page header (title, status chip, primary actions) followed by a body region organized with CSS grid. Default max width 1440 px with 32 px gutters; the grid snaps to an 8 px baseline to keep spacing predictable.
- **Feedback** – Toast stack anchored to the top-right corner of the content frame. Long-running actions surface inline progress rows aligned with the element that triggered them.

### 4.2 Layout primitives & tokens
- Core layout primitives (`Stack`, `Columns`, `Sidebar`, `Card`) live in `frontend/src/components/primitives/` and only express flex/grid behavior plus spacing hooks.
- Primitives consume CSS variables exported from `frontend/src/styles/tokens.ts`. Tokens cover color, spacing, radius, typography, elevation, and focus rings. Choosing accessible color pairs now keeps dark mode viable later without extra work.
- Route-specific styles live alongside the page component using CSS modules. We avoid global overrides and utility soup to keep styles predictable.

### 4.3 Route skeleton

```
/document-types                 # Library overview
/document-types/:id             # Governance view for a document type
/configurations/:id             # Column editing workspace
/runs/new                       # Upload & run console
/runs/:id                       # Run results & comparison
```

Nested routes share the shell so navigation and feedback remain consistent.

---

## 5. Core product surfaces

Each surface description covers layout, essential interactions, and implementation notes so we can estimate work and backend contracts confidently.

### 5.1 Document type library (`/document-types`)
- **Layout** – Page header with title, status filter chips, and primary action “Create document type”. Body renders a dense table showing document type name, active configuration label, draft count, latest run status summary, and attention badge column.
- **Core interactions** – Row click routes to detail view. Inline actions limited to “Open active configuration” and “Create new draft” to avoid accidental promotions.
- **Data contract** – `GET /document-types` returns document type metadata, counts of draft/published configurations, last run summary (status, finishedAt), and boolean `hasAttentionItems`.
- **Implementation notes** – Table uses TanStack Table with server-driven pagination. Empty/error states are deterministic and documented in Storybook. Badges and filter chips reuse Radix primitives for accessibility.

### 5.2 Document type detail (`/document-types/:id`)
- **Layout** – Two-pane composition. Left rail lists configurations (name, status chip, last updated, owner). Right pane shows summary of the selected configuration with sections for readiness score, outstanding issues, recent runs, and contextual actions.
- **Core interactions** – Create configuration (modal with name + optional copy-from source), promote published configuration to active, open configuration workspace in a new route.
- **Data contract** – `GET /document-types/:id` returns document type metadata, ordered configurations with promotion eligibility flags, aggregated readiness score, outstanding issues count, and last three runs.
- **Implementation notes** – Promotion flow uses Radix `AlertDialog` with explicit copy describing downstream impact. We refresh the configuration list after mutations resolve instead of optimistic updates so ordering stays deterministic.

### 5.3 Configuration workspace (`/configurations/:id`)
- **Layout** – Three-column grid on desktop, stacking into two sections on smaller widths:
  1. **Column list** – Compact list with readiness filter chips (All, Ready, Needs Attention) and iconography for script presence.
  2. **Editor canvas** – Tabbed Monaco editor for detection/validation/transformation scripts. Test output panel expands directly under the active tab.
  3. **Inspector rail** – Metadata (description, field type, optional/required toggle, sample values). History view can be added later once API support exists.
- **Core interactions** – Edit scripts with explicit “Save draft” action, execute column tests, publish configuration, inspect recent validation errors.
- **Data contract** – `GET /configurations/:id` returns column list with readiness indicators, script bodies, validation errors, and metadata. `POST /configurations/:id/columns/:columnId/test` returns structured logs, sample output, and pass/fail boolean.
- **Implementation notes** – Save actions dispatch React Query mutations with undo-friendly error handling; dirty state feeds the shell indicator. Monaco integrates via `@monaco-editor/react` with a thin wrapper for language mode, formatting, and `onRunTest` callback.

### 5.4 Upload & run console (`/runs/new`)
- **Layout** – Split view. Left pane contains drag-and-drop area with queued files table (filename, size, validation status). Right pane contains run setup form (configuration multi-select, run name, notes) and a progress timeline that appears after submission.
- **Core interactions** – Add/remove files, start a run, observe live progress, retry failed documents individually.
- **Data contract** – `POST /runs` accepts metadata and file handles, responding with run ID. `GET /runs/:id` returns summary status, timeline events, and per-document outcomes. `/runs/:id/stream` (SSE) emits incremental updates keyed by document ID.
- **Implementation notes** – Use `react-dropzone` for accessible drag-and-drop. Uploads rely on multi-part `FormData` via native `fetch`; chunking and resumable uploads are deferred. Progress timeline entries use Radix `Accordion` for optional log expansion, and SSE events hydrate React Query caches with derived status for each file.

### 5.5 Run results & comparison (`/runs/:id`)
- **Layout** – Page header summarizing status, duration, triggering user, and primary action “Mark as reviewed”. Body contains tabs: **Results** (paged table of extracted rows) and **Diff** (side-by-side comparison with baseline configuration).
- **Core interactions** – Toggle tabs, filter/sort results, export CSV, mark run as reviewed, and deep-link to the configuration workspace for problematic columns.
- **Data contract** – `GET /runs/:id/results` supports pagination, column metadata, validation flags, and CSV export URL. `GET /runs/:id/diff` returns baseline run metadata plus column-level diffs and severity.
- **Implementation notes** – Favor server pagination over virtualization for v1 to keep implementation predictable. Diff tab reuses tokenized semantic colors for additions/removals and surfaces aggregate counts at the top. “Mark as reviewed” triggers a mutation that invalidates run list and document type library caches.

---

## 6. Component architecture & interaction patterns

- **File organization** – Domain screens live under `frontend/src/features/<domain>/pages`. Shared widgets sit in `frontend/src/components/`. Hooks encapsulating data fetching or mutations live in `frontend/src/features/<domain>/hooks`. This separation keeps presentation and data concerns testable in isolation.
- **Forms** – React Hook Form + Zod handle validation. Inputs surface inline errors on blur or submit. Submit buttons stay disabled while pending and re-enable on error with retry guidance.
- **Tables & lists** – TanStack Table powers sorting/filtering. A shared `DataTable` wrapper owns skeleton, empty, and error states so every table has consistent affordances.
- **Script editing** – A dedicated `ScriptEditor` component wraps Monaco, providing language mode switching, lint annotations, formatting, and the `onRunTest` handler. Height expands to show test output without reflowing surrounding columns.
- **File input** – Drag-and-drop uses `react-dropzone`; a `useFileQueue` hook manages acceptance rules, derived statuses, and ties into React Query mutations.
- **Feedback** – Toast provider surfaces success/error. Inline `Callout` component conveys warnings or blockers. Destructive flows rely on Radix `AlertDialog` with explicit copy.
- **Keyboard & accessibility** – Provide shortcuts for editor tab switching and running tests. All focus states use tokenized outlines; components expose `aria-live` updates for long-running tasks (uploads, tests).

---

## 7. External dependencies & tooling

| Dependency | Decision | Rationale |
| --- | --- | --- |
| Vite, React, TypeScript | ✅ Adopt | Fast feedback loop and TS-first developer experience. |
| React Router v6 data APIs | ✅ Adopt | Nested layouts and loader/action pattern match our route structure and error handling needs. |
| @tanstack/react-query | ✅ Adopt | Manages server state, caching, and mutation lifecycles with minimal boilerplate. |
| React Hook Form + Zod | ✅ Adopt | Lightweight, type-safe forms aligned with backend validation. |
| Radix UI primitives | ✅ Adopt | Accessible building blocks for modals, tabs, accordions, and badges without custom a11y work. |
| @tanstack/react-table | ✅ Adopt | Headless table utilities reused across library and results screens. |
| @monaco-editor/react | ✅ Adopt | Script editing with minimal integration cost. |
| Storybook + MSW | ✅ Adopt | Component workbench and predictable API mocks for visual states. |
| Vitest + React Testing Library | ✅ Adopt | Unit and interaction tests that mirror component usage. |
| Playwright | ✅ Adopt | Deterministic end-to-end and smoke tests for critical flows. |
| react-dropzone | ✅ Adopt | Handles accessible drag-and-drop without reinventing browser quirks. |
| @tanstack/react-virtual | ⏸️ Defer | Server pagination keeps v1 simple; revisit when runs regularly exceed page size. |
| File upload helpers (Uppy / tus-js-client) | ⏸️ Defer | Resumable uploads can wait until file sizes or failures demand them. |

We intentionally avoid full design-system frameworks to keep styling predictable and ownership clear.

---

## 8. Data flow & state management

- **HTTP client** – Typed wrapper around `fetch` with `AbortController` support lives in `frontend/src/lib/apiClient.ts`. The same module exposes helpers for SSE consumption that translate events into React Query cache updates.
- **Route loaders** – React Router loaders fetch primary data for each page, streamlining skeleton states and letting error boundaries surface API issues without extra code.
- **Query keys** – Use explicit tuples (`['workspace', workspaceId, 'documentTypes']`) so invalidation stays precise. Mutations return typed payloads that update caches via `queryClient.setQueryData` when feasible.
- **Error handling** – Loader errors route to descriptive boundaries; in-component mutations map server validation errors to field-level messages. Toasts reinforce blocking issues.
- **Data shaping** – Backend responses should already be normalized; frontend selectors derive computed summaries (e.g., readiness score) instead of mutating cached objects in place.
- **Streaming updates** – SSE endpoints feed a `useEventStream` helper that batches updates to avoid thrashing renders while keeping progress indicators responsive.

---

## 9. Implementation checkpoints

To keep delivery predictable, start with shared scaffolding and add vertical slices in this order:

1. Establish design tokens, layout primitives, and Storybook stories for the shell.
2. Build the application shell and navigation, backed by mocked loaders.
3. Implement the `DataTable` wrapper and document type library with MSW fixtures.
4. Layer in the configuration detail flows (document type detail + configuration workspace) with React Query hooks.
5. Add the upload console and SSE plumbing, validating concurrency and retry behaviors with mocked endpoints.
6. Deliver the run results surface, ensuring table filters, diff visuals, and CSV export interactions are test-covered.
7. Harden through Playwright smoke tests covering save/publish, upload/run, and review flows before shipping.
