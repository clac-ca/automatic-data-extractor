# ADE frontend core blueprint

ADE's frontend must make complex extraction workflows feel approachable. This revision narrows the blueprint to the smallest set of layouts, interactions, and dependencies required for a reliable v1. Anything beyond these fundamentals stays out of scope until the core surfaces are live and stable.

---

## 1. Purpose & scope

- **Source of truth** – Defines layout, interaction patterns, and supporting tooling for ADE's web client.
- **Scope** – Desktop-first React application built for analysts and engineers. Mobile-first layouts, onboarding, and personalization are intentionally deferred.
- **Maintainability** – Favor predictable layouts, typed APIs, and clear seams for testing. Ship fewer, sturdier components over speculative abstractions.
- **Change hygiene** – Update this file whenever layout decisions, dependencies, or API expectations shift. Capture rationale so future contributors understand trade-offs.

---

## 2. Product guardrails

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
| Column | Ready ↔ Needs Attention | “Needs Attention” indicates missing callables, failing tests, or deprecated APIs. |
| Run | Queued → Running → Validating → Complete / Failed | Metadata flags (e.g., `needsApproval`) augment but never override states. |

Document types are logical containers without lifecycle. Governance metadata lives on configurations and columns.

---

## 4. Application skeleton

### 4.1 Shell & navigation
- **Navigation rail** – Persistent left rail with sections: *Document Types*, *Runs*, *Settings*. Collapse to an overlay drawer ≤1024 px while keeping top-level links available inside the drawer header.
- **Top bar** – Hosts workspace selector, user menu, inline system notices, and an unsaved-change indicator tied to the active route’s form state. No command palette in v1.
- **Content frame** – Page header (title, status chip, primary actions) followed by a body region organized with CSS grid. Default max width 1440 px with 32 px gutters; the grid snaps to an 8 px baseline for predictable spacing.
- **Feedback** – Toast stack anchored to the top-right corner of the content frame. Long-running actions surface inline progress rows aligned with the element that triggered them.

### 4.2 Layout primitives & tokens
- Core layout primitives (`Stack`, `Columns`, `Sidebar`, `Card`) live in `frontend/src/components/primitives/` and only express flex/grid behavior plus spacing hooks.
- Primitives consume CSS variables exported from `frontend/src/styles/tokens.ts`. Tokens cover color, spacing, radius, typography, elevation, and focus rings. Accessible contrast keeps dark mode viable later without extra work.
- Route-specific styles live alongside the page component using CSS modules. Avoid global overrides and utility soup to keep styles predictable.

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

Each surface outlines layout, essential interactions, data requirements, and implementation notes so effort can be estimated and backend contracts verified upfront.

### 5.0 Surface overview

| Route | Primary objective | Layout snapshot |
| --- | --- | --- |
| `/document-types` | Understand portfolio and spot work-in-progress. | Header with filters above a dense table. |
| `/document-types/:id` | Govern configurations for one document type. | Split view with configuration list beside detail panel. |
| `/configurations/:id` | Edit scripts, metadata, and validation for a configuration. | Two-column workspace with tabbed editor. |
| `/runs/new` | Launch document processing runs. | Dual-card layout for file queue and run options. |
| `/runs/:id` | Review run outcomes and compare to baseline. | Header summary plus tabbed results/diff tables. |

The remainder of this section expands each route.

### 5.1 Document type library (`/document-types`)

**Layout**
- Header: title, status filter chips (Active, Drafts, Attention), primary action “Create document type”.
- Body: full-width table with sticky header row; actions appear inline on hover to keep rows readable.
- Empty state: centered illustration, short copy, primary CTA to create the first document type.

**Data contracts**
- `GET /document-types` → array of `{ id, name, activeConfiguration, draftCount, lastRun: { status, finishedAt }, hasAttentionItems }`.
- Query params: `status[]`, `search`, and pagination `page`/`pageSize`.

**Key interactions**
- Clicking a row routes to `/document-types/:id`.
- Inline actions: open active configuration, start new draft (opens modal or navigates to creation form).
- Filters and pagination persist via URL params.

**Implementation notes**
- Use shared `DataTable` primitive (TanStack Table + house styling) for consistent header, empty, and error states.
- React Query query key mirrors route + params to enable cache sharing with detail view prefetch.
- Keep interactions deterministic—no inline editing in the table for v1.

**Readiness questions**
- Confirm backend supports combined status filtering and pagination.
- Decide whether `lastRun.status` is nullable and how to render “No runs yet”.
- Clarify copy for attention badge (“Needs attention” vs “All good”).

### 5.2 Document type detail (`/document-types/:id`)

**Layout**
- Sticky page header with document type name, state chip for the active configuration, and action menu (create draft, publish, retire).
- Two-column body:
  - Left rail: list grouped by state (Active, Published, Drafts, Retired) with count badges.
  - Right panel: tabs for **Overview** and **Activity**. Overview shows metadata, readiness checklist, and quick links to recent runs. Activity lists promotions and approvals.

**Data contracts**
- `GET /document-types/:id` → metadata plus `configurations[]` with `{ id, name, state, updatedAt, owner, readiness }`.
- `GET /runs?documentTypeId=<id>&limit=5` powers recent activity list.
- Mutations: `POST /document-types/:id/configurations` (create draft), `POST /configurations/:id/publish`, `POST /configurations/:id/retire`.

**Key interactions**
- Selecting a configuration highlights it and reveals summary metadata in the right panel.
- Promote draft → confirmation dialog, server mutation, refresh configuration list.
- Links to configuration workspace and related runs.

**Implementation notes**
- Keep readiness checklist limited to binary signals: required columns complete, tests passing, approvals collected. Defer granular scorecards.
- Use React Query mutations without optimistic updates; rely on server response to avoid state drift.
- Ensure navigation focus returns to the configuration list after actions for accessibility.

**Readiness questions**
- Align on required readiness checks and backend fields delivering them.
- Decide if promotions require comment text; if so, capture via Radix `AlertDialog` with a simple textarea.
- Confirm whether retired configurations remain editable (assumed no for v1).

### 5.3 Configuration workspace (`/configurations/:id`)

**Layout**
- Header: configuration name, state chip, actions (“Save draft”, “Publish”).
- Body: left column lists columns grouped by readiness (Ready, Needs attention); right column hosts tabs **Schema**, **Scripts**, **Tests**.
  - **Schema** – simple form listing column name, data type, required flag, description.
  - **Scripts** – Monaco editor with sub-tabs for detection, validation, transformation. Output panel sits below editor at fixed height.
  - **Tests** – table of test cases with last run result and actions to run or duplicate. Creating complex suites is out of scope.

**Data contracts**
- `GET /configurations/:id` → metadata, column definitions, script bodies, readiness flags.
- `GET /configurations/:id/tests` → array of tests with `{ id, name, lastRun: { status, finishedAt }, lastOutput }`.
- Mutations: `PATCH /configurations/:id` for metadata, `PUT /configurations/:id/columns/:columnId` for column details, `PUT /configurations/:id/scripts` for script text, `POST /configurations/:id/tests/run` to execute tests.

**Key interactions**
- Select column to focus the right-panel tabs on its details.
- Edit metadata and scripts, save to persist draft.
- Run tests; display status updates inline and pin most recent output.
- Publish once required columns are marked ready.

**Implementation notes**
- Monaco loads lazily and registers language features (TypeScript, Python) based on backend script type metadata.
- React Hook Form handles metadata; script editor uses controlled inputs with manual dirty tracking for unsaved indicator.
- Poll test execution every few seconds until completion; encapsulate polling logic in a hook to swap for websockets later.

**Readiness questions**
- Confirm script languages supported and whether backend returns lint diagnostics.
- Define payload for marking a column “Ready” vs “Needs attention”.
- Clarify how large scripts can be before chunking/upload concerns arise (assumed manageable for v1).

### 5.4 Upload & run console (`/runs/new`)

**Layout**
- Header: page title, short helper text linking to docs.
- Body: left card contains drag-and-drop area, queued files with status badges, and remove buttons. Right card contains form inputs: document type selector, configuration selector (filtered by chosen document type), optional metadata fields, submit button.
- Progress section below form shows latest submission status when a run is in flight.

**Data contracts**
- `GET /document-types` and `GET /document-types/:id/configurations?state=active|published` feed selectors.
- `POST /runs` accepts `{ documentTypeId, configurationId, metadata, files[] }` and returns `{ runId }`.
- `GET /runs/:id` returns `{ status, timeline[], documents[] }` for polling.
- `POST /runs/:id/retry` requeues failed documents.

**Key interactions**
- Validate files (type/size) before accepting into queue.
- Submit run → disable form, show inline progress, re-enable after success/failure.
- Retry failed document from queue list.

**Implementation notes**
- `react-dropzone` ensures accessible drag-and-drop; custom hook `useFileQueue` stores `FileWithId`, validation errors, and derived totals.
- Polling interval stored in hook; pause when page is backgrounded using Page Visibility API to reduce load.
- Reuse toast system for success/error; inline callout summarises aggregated failures.

**Readiness questions**
- Verify upload size limits and whether backend expects chunked uploads (assumed not for v1).
- Confirm metadata schema (e.g., optional labels) and validation rules.
- Decide what happens to partially completed runs if user navigates away (assume backend continues and UI can reattach later).

### 5.5 Run results & comparison (`/runs/:id`)

**Layout**
- Header: run status badge, duration, triggered by, and action “Mark as reviewed”.
- Tabs beneath header: **Results** (primary) and **Diff** (against baseline configuration).
- Results tab: table with pagination, filter row for validation status, inline row expansion for error context.
- Diff tab: two-column grid showing baseline vs current values grouped by column.

**Data contracts**
- `GET /runs/:id` for high-level summary (status timeline, metadata, review state).
- `GET /runs/:id/results?page=&pageSize=&filters=` returning rows, column metadata, validation flags, csvExportUrl.
- `GET /runs/:id/diff` returning baseline run id, changed columns, severity classification.
- Mutation: `POST /runs/:id/review` toggles reviewed state.

**Key interactions**
- Paginate, filter, and export from Results tab.
- Inspect differences in Diff tab and deep-link to configuration workspace for problematic columns.
- Mark as reviewed once validation complete; disable button if already reviewed.

**Implementation notes**
- Shared `DataTable` handles pagination controls and skeleton states; avoid virtualization until data proves necessary.
- Diff tab reuses same table shell with row grouping semantics to keep keyboard navigation consistent.
- Persist active tab and filters in query params for shareable URLs.

**Readiness questions**
- Confirm baseline comparison logic (e.g., last active run vs manually selected reference).
- Ensure diff payload specifies severity taxonomy (info/warn/blocker) for consistent styling.
- Clarify review workflow: who can mark reviewed and whether undo is supported (assumed yes with same endpoint).

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
- Local UI state (filters, selection, modals) stays within components or context providers scoped to a feature to avoid global stores.
- API helpers in `frontend/src/api/client.ts` wrap `fetch` with JSON parsing, error normalization, and abort handling.

### 6.3 Forms
- React Hook Form + Zod power validation. Inputs surface inline errors on blur or submit.
- Submit buttons stay disabled while pending and re-enable on error with retry guidance.
- Multi-step flows use a single form element with context sections rather than nested forms.

### 6.4 Tables & lists
- TanStack Table powers sorting/filtering. Shared `DataTable` wrapper owns skeleton, empty, and error states so every table has consistent affordances.
- Pagination is server-driven; virtualization is deferred until we see sustained performance issues.

### 6.5 Script editing
- `ScriptEditor` wraps Monaco to provide language-aware editing, lint annotations (if supplied by backend), and a `Run test` action.
- Test output renders in a fixed-height panel beneath the active script tab to prevent layout shifts.
- Keyboard shortcuts are limited to essentials (`mod+s` save, `mod+enter` run test) to keep implementation scoped.

### 6.6 File input
- Drag-and-drop uses `react-dropzone`; `useFileQueue` manages acceptance rules, derived statuses, and ties into React Query mutations.
- Upload errors surface inline per file, with aggregated errors summarized in a callout.

### 6.7 Feedback & accessibility
- Toast provider surfaces success/error with sensible auto-dismiss. Inline `Callout` component conveys warnings or blockers.
- Destructive flows rely on Radix `AlertDialog` with explicit copy.
- All focus states use tokenized outlines; components expose `aria-live` updates for long-running tasks (uploads, tests).

### 6.8 Testing strategy
- Unit/interaction tests live beside components using Vitest + React Testing Library.
- Mock service worker (MSW) supplies deterministic API responses for Storybook and tests.
- Playwright covers golden-path scenarios (edit script, execute run, review diff) once primary routes stabilize.

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
| Playwright | ✅ Adopt | Deterministic end-to-end and smoke tests for critical flows once primary routes stabilize. |
| react-dropzone | ✅ Adopt | Handles accessible drag-and-drop without reinventing browser quirks. |
| @tanstack/react-virtual | ⏸️ Defer | Server pagination keeps v1 simple; revisit once tables regularly exceed a page. |
| File upload helpers (Uppy / tus-js-client) | ⏸️ Defer | Resumable uploads can wait until file sizes or network failures demand them. |

We intentionally avoid full design-system frameworks to keep styling predictable and ownership clear.

---

## 8. Build sequencing & readiness checklist

1. **Foundations** – Establish tokens, primitives, routing scaffold, and shared providers (React Query, toasts, error boundary).
2. **Navigation shell** – Implement left rail, top bar, and content frame. Wire workspace selector to placeholder data until backend contract finalizes.
3. **API layer** – Build typed `fetch` helpers and query hooks for document types, configurations, and runs. Confirm error shapes with backend.
4. **Feature slices** – Ship surfaces in this order to unblock backend collaboration:
   1. Document type library (read-only)
   2. Document type detail (read-only then mutating flows)
   3. Configuration workspace (scripts + tests)
   4. Upload & run console
   5. Run results & comparison
5. **Testing** – For each slice add Storybook stories (default, empty, error), unit tests for hooks/components, and Playwright smoke covering the golden paths (e.g., edit script, run documents, review results).
6. **Telemetry & logging** – After core flows work, add basic page view and error logging hooks; defer advanced analytics.

Before starting implementation, confirm the backend exposes the endpoints listed in Section 5, finalizes payload schemas, and documents authentication headers. Any gaps should be captured as follow-up tasks rather than patched in ad hoc.

---

## 9. Integration checkpoints
- **Authentication** – Lock the header format, refresh behavior, and how credentials surface in local development.
- **Error contract** – Capture the JSON error envelope (code, message, field errors) so hooks can normalize consistently.
- **Sample data** – Gather anonymized documents and canonical API responses to drive Storybook stories and Playwright fixtures.
- **Environment config** – Decide on a single entry point for runtime configuration (e.g., `window.__ADE_CONFIG__`) to avoid hardcoding URLs in bundles.
- **Permissions** – Clarify whether routes hide or disable actions based on roles; defer to backend feature flags when uncertain.
