# ADE frontend core blueprint

ADE's frontend must make complex extraction workflows feel approachable. This revision narrows the blueprint to the smallest set
of layouts, interactions, and dependencies required for a reliable v1. Anything beyond these fundamentals—tours, heavy
customization, deep analytics—stays out of scope until the core surfaces are live and stable.

---

## 1. Purpose & scope

- **Source of truth** – Defines layout, interaction patterns, and supporting tooling for ADE's web client.
- **Scope** – Desktop-first React application built for analysts and engineers. Portrait mobile layouts, onboarding flows, and
  growth hooks are intentionally deferred.
- **Maintainability** – Favor predictable layouts, typed APIs, and clear seams for testing. Prefer shipping fewer, sturdier
  components over speculative abstractions.
- **Change hygiene** – Update this file whenever layout decisions, dependencies, or API expectations shift. Capture rationale so
  future contributors understand trade-offs.

---

## 2. Product truths & guardrails

### 2.1 Why ADE exists
- Turn messy spreadsheets/PDFs into trustworthy tables with auditable logic.
- Let operations teams iterate, compare, and promote extraction logic without touching backend code.

### 2.2 First principles
1. **Immediate clarity** – Every surface answers “What is this and what changed?” before exposing controls.
2. **Confidence while iterating** – Users should see progress, test outcomes, and promotion states without hunting.
3. **Deterministic actions** – Buttons, shortcuts, and navigation affordances do exactly what they say. No hidden side effects.
4. **Layered complexity** – Start with the smallest workable feature slice and leave obvious seams for follow-on enhancements.

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
| Column | Ready ↔ Needs Attention | "Needs Attention" indicates missing callables, failing tests, or deprecated APIs. |
| Run | Queued → Running → Validating → Complete / Failed | Metadata flags (e.g., `needsApproval`) augment but never override states. |

Document types are logical containers without lifecycle. Governance metadata lives on configurations and columns.

---

## 4. Layout architecture

### 4.1 Application shell
- **Navigation** – Persistent left rail with sections: *Document Types*, *Runs*, *Settings*. Collapse to an overlay drawer ≤1024 px
  while keeping top-level links available inside the drawer header.
- **Top bar** – Hosts workspace selector, user menu, inline system notices, and an unsaved-change indicator tied to the active
  route’s form state. No command palette in v1.
- **Content frame** – Page header (title, status chip, primary actions) followed by a body region organized with CSS grid. Default
  max width 1440 px with 32 px gutters; the grid snaps to an 8 px baseline for predictable spacing.
- **Feedback** – Toast stack anchored to the top-right corner of the content frame. Long-running actions surface inline progress
  rows aligned with the element that triggered them.

### 4.2 Layout primitives & tokens
- Core layout primitives (`Stack`, `Columns`, `Sidebar`, `Card`) live in `frontend/src/components/primitives/` and only express
  flex/grid behavior plus spacing hooks.
- Primitives consume CSS variables exported from `frontend/src/styles/tokens.ts`. Tokens cover color, spacing, radius, typography,
  elevation, and focus rings. Accessible contrast now keeps dark mode viable later without extra work.
- Route-specific styles live alongside the page component using CSS modules. Avoid global overrides and utility soup to keep styles
  predictable.

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

Each surface outlines layout, essential interactions, data requirements, and implementation notes so effort can be estimated and
backend contracts verified upfront.

### 5.1 Document type library (`/document-types`)
- **Layout** – Page header with title, status filter chips, and primary action “Create document type”. Body renders a dense table
  with columns: document type name, active configuration label, draft count, latest run status summary, attention badge.
- **Primary data** – `GET /document-types` returns metadata, counts of draft/published configurations, last run summary
  (`status`, `finishedAt`), boolean `hasAttentionItems`.
- **Key interactions** – Row click routes to detail view. Inline actions limited to “Open active configuration” and “Create new
  draft” to avoid accidental promotions.
- **Implementation approach** – Compose a `DocumentTypeTable` using TanStack Table inside a shared `DataTable` shell for empty/error
  states. Data loads via `useDocumentTypesQuery` (React Query) with pagination and filter params forwarded as query keys. Buttons
  dispatch router navigation; no optimistic updates required.

### 5.2 Document type detail (`/document-types/:id`)
- **Layout** – Two-pane composition. Left rail lists configurations (name, status chip, last updated, owner). Right pane shows
  summary of the selected configuration with sections for readiness score, outstanding issues, recent runs, and contextual
  actions.
- **Primary data** – `GET /document-types/:id` returns document type metadata, ordered configurations with promotion eligibility
  flags, aggregated readiness score, outstanding issues count, and last three runs.
- **Key interactions** – Create configuration (modal with name + optional copy-from source), promote published configuration to
  active, open configuration workspace in a new route.
- **Implementation approach** – Left rail implemented with a selectable list component backed by React Router search params to
  persist selection. Modals reuse Radix `Dialog`; promotion flow uses Radix `AlertDialog` with explicit copy describing downstream
  impact. Mutations invalidate `document-types` and `configurations` queries to keep ordering deterministic.

### 5.3 Configuration workspace (`/configurations/:id`)
- **Layout** – Three-column grid on desktop, collapsing to stacked sections <1280 px:
  1. **Column list** – Compact list with readiness filter chips (All, Ready, Needs Attention) and icons for script presence.
  2. **Editor canvas** – Tabbed Monaco editor for detection/validation/transformation scripts. Test output panel expands directly
     under the active tab.
  3. **Inspector rail** – Metadata (description, field type, optional/required toggle, sample values). Version history and
     comments are deferred until APIs exist.
- **Primary data** – `GET /configurations/:id` returns column list with readiness indicators, script bodies, validation errors,
  and metadata. `POST /configurations/:id/columns/:columnId/test` returns structured logs, sample output, and pass/fail boolean.
- **Key interactions** – Edit scripts with explicit “Save draft”, execute column tests, publish configuration, inspect recent
  validation errors.
- **Implementation approach** – Monaco integrates via `@monaco-editor/react` wrapped by `ScriptEditor` to manage language mode,
  formatting, and keyboard shortcuts. Save actions dispatch React Query mutations; dirty state feeds both local banners and the
  shell indicator. Test execution renders the API response logs in order; no streaming in v1. Failures highlight the related
  metadata section inside the inspector.

### 5.4 Upload & run console (`/runs/new`)
- **Layout** – Split view. Left pane contains drag-and-drop area with queued files table (filename, size, validation status).
  Right pane contains run setup form (configuration multi-select, run name, notes) and a progress timeline that appears after
  submission.
- **Primary data** – `POST /runs` accepts metadata and file handles, responding with run ID. `GET /runs/:id` returns summary
  status, timeline events, and per-document outcomes.
- **Key interactions** – Add/remove files, start a run, observe progress, retry failed documents individually.
- **Implementation approach** – Use `react-dropzone` with a `useFileQueue` hook managing acceptance rules and deduplication.
  After submission, poll `GET /runs/:id` at a modest fixed interval; capture the interval in a hook so upgrading to server
  events later is isolated. Timeline entries render simple status rows, with optional expansion handled via Radix `Accordion`.
  Retry action re-queues a single file via `POST /runs/:id/retry` and refreshes the run query.

### 5.5 Run results & comparison (`/runs/:id`)
- **Layout** – Page header summarizing status, duration, triggering user, and primary action “Mark as reviewed”. Body contains
  tabs: **Results** (paged table of extracted rows) and **Diff** (side-by-side comparison with baseline configuration).
- **Primary data** – `GET /runs/:id/results` supports pagination, column metadata, validation flags, and CSV export URL. `GET
  /runs/:id/diff` returns baseline run metadata plus column-level diffs and severity indicators.
- **Key interactions** – Toggle tabs, filter/sort results, export CSV, mark run as reviewed, deep-link to the configuration
  workspace for problematic columns.
- **Implementation approach** – Results tab reuses the shared `DataTable` wrapper with server pagination. Diff tab reuses the
  same table shell to render grouped additions/removals with semantic tokens; keep the layout deterministic and avoid
  virtualization. “Mark as reviewed” triggers a mutation invalidating run list and document type library caches.

### 5.6 Deferred for post-v1
- In-app tours, onboarding checklists, and personalization.
- Inline commenting, version timelines, and advanced audit diff visualizations.
- Realtime run streaming and resumable uploads.
- Theming, per-user preferences, and complex analytics dashboards.

---

## 6. Component architecture & interaction patterns

### 6.1 File organization
- Domain screens live under `frontend/src/features/<domain>/pages`.
- Shared widgets sit in `frontend/src/components/`.
- Hooks encapsulating data fetching or mutations live in `frontend/src/features/<domain>/hooks`.
- Tests colocate with components or hooks using `.test.tsx` or `.test.ts` suffixes.

### 6.2 Data fetching & state
- React Query handles server state, caching, invalidation, and polling. Query keys mirror API routes plus parameter objects.
- Local UI state (filters, selection, modals) stays within components or context providers scoped to a feature to avoid global
  stores.
- API helpers in `frontend/src/api/client.ts` wrap `fetch` with JSON parsing, error normalization, and abort handling.

### 6.3 Forms
- React Hook Form + Zod power validation. Inputs surface inline errors on blur or submit.
- Submit buttons stay disabled while pending and re-enable on error with retry guidance.
- Multi-step flows use a single form element with context sections rather than nested forms.

### 6.4 Tables & lists
- TanStack Table powers sorting/filtering. Shared `DataTable` wrapper owns skeleton, empty, and error states so every table has
  consistent affordances.
- Pagination is server-driven; virtualization is deferred until we see sustained performance issues.

### 6.5 Script editing
- `ScriptEditor` wraps Monaco, providing language mode switching, lint annotations, formatting, and the `onRunTest` handler.
- Test output renders in a fixed-height panel beneath the active tab to prevent layout thrash.
- Keyboard shortcuts include save (`mod+s`), run test (`mod+enter`), and tab switching (`alt+[ / ]`).

### 6.6 File input
- Drag-and-drop uses `react-dropzone`; `useFileQueue` manages acceptance rules, derived statuses, and ties into React Query
  mutations.
- Upload errors surface inline per file, with aggregated errors summarized in a callout.

### 6.7 Feedback & accessibility
- Toast provider surfaces success/error with sensible auto-dismiss. Inline `Callout` component conveys warnings or blockers.
- Destructive flows rely on Radix `AlertDialog` with explicit copy.
- All focus states use tokenized outlines; components expose `aria-live` updates for long-running tasks (uploads, tests).

---

## 7. External dependencies & tooling

| Dependency | Decision | Rationale & usage notes |
| --- | --- | --- |
| Vite, React, TypeScript | ✅ Adopt | Fast feedback loop, TS-first DX, and consistent bundling story. |
| React Router v6 data APIs | ✅ Adopt | Nested layouts, loader/action pattern, and error boundaries fit our routing needs. |
| @tanstack/react-query | ✅ Adopt | Manages server state, caching, retries, and polling with minimal boilerplate. |
| React Hook Form + Zod | ✅ Adopt | Lightweight, type-safe forms aligned with backend validation schemas. |
| Radix UI primitives | ✅ Adopt | Accessible building blocks for dialogs, tabs, accordions, and badges without custom a11y work. |
| @tanstack/react-table | ✅ Adopt | Headless table utilities reused across library, results, and diff screens. |
| @monaco-editor/react | ✅ Adopt | Script editing with minimal integration cost; aligns with developer expectations. |
| Storybook + MSW | ✅ Adopt | Component workbench with deterministic API mocks for visual states and regression testing. |
| Vitest + React Testing Library | ✅ Adopt | Unit and interaction tests mirroring component usage. |
| Playwright | ✅ Adopt | Deterministic end-to-end and smoke tests for critical flows. |
| react-dropzone | ✅ Adopt | Handles accessible drag-and-drop without reinventing browser quirks. |
| @tanstack/react-virtual | ⏸️ Defer | Server pagination keeps v1 simple; revisit once tables regularly exceed a page. |
| File upload helpers (Uppy / tus-js-client) | ⏸️ Defer | Resumable uploads can wait until file sizes or network failures demand them. |

We intentionally avoid full design-system frameworks to keep styling predictable and ownership clear.

---

## 8. Build sequencing & readiness checklist

1. **Foundations** – Establish tokens, primitives, routing scaffold, and shared providers (React Query, toasts, error boundary).
2. **Navigation shell** – Implement left rail, top bar, and content frame. Wire workspace selector to placeholder data until
   backend contract finalizes.
3. **API layer** – Build typed `fetch` helpers and query hooks for document types, configurations, and runs. Confirm error shapes
   with backend.
4. **Feature slices** – Ship surfaces in this order to unblock backend collaboration:
   1. Document type library (read-only)
   2. Document type detail (read-only then mutating flows)
   3. Configuration workspace (scripts + tests)
   4. Upload & run console
   5. Run results & comparison
5. **Testing** – For each slice add Storybook stories (default, empty, error), unit tests for hooks/components, and Playwright
   smoke covering the golden paths (e.g., edit script, run documents, review results).
6. **Telemetry & logging** – After core flows work, add basic page view and error logging hooks; defer advanced analytics.

Before starting implementation, confirm the backend exposes the endpoints listed in Section 5, finalizes payload schemas, and
documents authentication headers. Any gaps should be captured as follow-up tasks rather than patched in ad hoc.

---

## 9. Integration checkpoints
- **Authentication** – Lock the header format, refresh behavior, and how credentials surface in local development.
- **Error contract** – Capture the JSON error envelope (code, message, field errors) so hooks can normalize consistently.
- **Sample data** – Gather anonymized documents and canonical API responses to drive Storybook stories and Playwright fixtures.
- **Environment config** – Decide on a single entry point for runtime configuration (e.g., `window.__ADE_CONFIG__`) to avoid
  hardcoding URLs in bundles.
- **Permissions** – Clarify whether routes hide or disable actions based on roles; defer to backend feature flags when uncertain.
