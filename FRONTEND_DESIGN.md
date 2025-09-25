# ADE frontend design guide

This guide defines how the ADE web client should be organized while the backend
rewrite lands. Treat it as the contract for front-end work: when backend
capabilities or UX priorities shift, update this guide before writing code so
the app stays coherent.

---

## 1. Product intent & UX guardrails

- **Primary outcome** – Analysts upload semi-structured documents, run
  deterministic extraction jobs, and review tables inside their workspace.
- **Audience** – Internal desktop users. Tablet/mobile refinements can wait
  until core workflows stabilize.
- **Voice** – Predictable and auditable. Favor explicit state transitions over
  clever abstractions so QA can follow the trail.
- **Accessibility** – Respect focus rings, keyboard navigation, and high
  contrast defaults from day one. Screen-reader polish should not require
  structural rewrites later.

---

## 2. Technical baseline

### 2.1 Framework & tooling

- **Build system** – Vite + React 18 + TypeScript in strict mode.
- **Routing** – React Router v6 data APIs for nested layouts and loaders.
- **Server state** – TanStack Query (React Query) with workspace-aware keys.
- **Tables** – TanStack Table for data grids with virtualization hooks.
- **Forms** – React Hook Form + Zod schemas mirroring backend Pydantic models.
- **Styling** – CSS Modules + design tokens exposed as CSS variables. Radix UI
  primitives back interactive widgets (dialog, toast, dropdown).
- **Testing** – Vitest for unit tests, React Testing Library + MSW for
  components, Playwright for end-to-end smoke tests.

### 2.2 Backend alignment

All requests flow through workspace-scoped FastAPI routers under
`backend/app/api/modules`. Workspace context is always encoded in the URL prefix
`/workspaces/{workspace_id}` and validated by backend middleware.

| Domain | Endpoints (prefix omitted) | UI considerations |
| --- | --- | --- |
| Documents | `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/download`, `DELETE /documents/{id}` | Uploads use multipart form data. Deleting supports optional reason payload and soft delete. |
| Jobs | `POST /jobs`, `GET /jobs`, `GET /jobs/{id}` | Submission requires `input_document_id`, `configuration_id`, `configuration_version`. List filters by status and document. |
| Results | `GET /jobs/{id}/tables`, `GET /jobs/{id}/tables/{table_id}`, `GET /documents/{id}/tables` | Returns 409 while processing; only render tables after terminal job status. |
| Configurations | `GET /configurations`, `GET /configurations/active`, CRUD endpoints | Optimistic edits must surface backend validation errors inline. |
| Workspaces | `GET /workspaces`, `GET /workspaces/{id}`, membership CRUD | Needed for workspace switcher and admin flows. |
| Auth | `/auth` module endpoints | HTTP client attaches tokens and relays 401/403 back to auth layer. |

Backend properties to surface in the UI:

1. **Synchronous execution** – Jobs run inline; polling intervals of 3–5 s are
   safe.
2. **Deterministic results** – Cache busting is safe; re-fetching tables should
   reproduce the same payload.
3. **Permission-aware responses** – 403 errors are expected and should disable
   UI affordances instead of generic toasts.
4. **Structured error envelopes** – Many responses return `{ "detail": { ... } }`.
   Normalize this shape so forms can map field errors directly.

---

## 3. Application architecture

### 3.1 Routing shell

All authenticated routes live beneath `/workspaces/:workspaceId`. The navigation
surface mirrors backend modules:

```
/workspaces/:workspaceId
  ├─ documents
  │   ├─ :documentId
  │   └─ upload (modal/drawer via route state)
  ├─ jobs
  │   ├─ new
  │   └─ :jobId
  ├─ configurations
  │   └─ :configurationId
  └─ admin
      └─ members
```

`App.tsx` hosts the router, error boundaries, and layout shell (navigation rail,
workspace switcher, content area, optional context panel).

### 3.2 Data and state management

- React Query keys follow `[workspaceId, domain, params]` so switching
  workspaces invalidates caches automatically.
- Loaders prefetch canonical queries and dehydrate results into `Hydrate`
  boundaries. Unauthorized loads redirect to the workspace picker.
- Mutations live in feature hooks (e.g., `useSubmitJob`). Success handlers
  invalidate downstream queries and optionally navigate to success routes.
- Large payloads (document downloads, table exports) bypass JSON utilities and
  stream via `fetch` + `Response.blob()` while preserving auth headers.

### 3.3 Forms & validation

- React Hook Form handles state with Zod for synchronous validation against the
  backend contract (`JobSubmissionRequest`, `ConfigurationCreate`, etc.).
- Mutations should map backend `detail.field` errors back into the form state.
- Deletion, activation, and other simple mutations can use `<Form>` elements
  from React Router where no complex state is required.

### 3.4 Error handling & resilience

- HTTP client normalizes errors to `{ type, message, fieldErrors? }`.
- Route-level `ErrorBoundary` components display contextual messaging and retry
  actions. Global `SessionExpired` boundary clears auth state and redirects to
  login on 401.
- Toasts announce background successes/failures; inline alerts surface
  validation problems.

### 3.5 Shared UI system

- Design tokens define color, spacing, typography, and focus states under
  `styles/tokens.ts`.
- Layout primitives (Stack, Columns, PageHeader, Card) live in shared components
  and never access API state.
- Feedback widgets (Toast, Callout, EmptyState) live beside primitives and are
  reused across features.

---

## 4. Project structure

### 4.1 High-level layout

```
frontend/
├─ package.json
├─ tsconfig.json
├─ vite.config.ts
├─ public/              # static assets served as-is
├─ src/
│  ├─ app/              # bootstrap, providers, router, layout shell
│  │   ├─ App.tsx
│  │   ├─ main.tsx
│  │   ├─ providers/
│  │   └─ router/
│  ├─ api/              # HTTP client, query hooks, generated types
│  │   ├─ client.ts
│  │   ├─ schemas/
│  │   └─ workspace.ts
│  ├─ pages/            # Route entry points that compose features
│  │   ├─ documents/
│  │   ├─ jobs/
│  │   ├─ configurations/
│  │   ├─ results/
│  │   └─ admin/
│  ├─ features/         # Reusable feature slices (forms, tables, drawers)
│  │   ├─ documents/
│  │   │   ├─ components/
│  │   │   ├─ hooks/
│  │   │   └─ index.ts
│  │   ├─ jobs/
│  │   ├─ configurations/
│  │   ├─ results/
│  │   └─ workspaces/
│  ├─ components/       # Shared UI primitives (buttons, layout, feedback)
│  ├─ hooks/            # Cross-cutting hooks (useWorkspace, usePolling)
│  ├─ lib/              # Utilities (formatting, date helpers, query helpers)
│  ├─ styles/           # Global CSS, tokens, resets
│  ├─ mocks/            # MSW handlers and fixtures for tests/storybook
│  ├─ types/            # Global TypeScript types not generated elsewhere
│  └─ tests/            # Integration-level utilities (test renderers)
└─ tests/               # Playwright specs and fixtures
```

### 4.2 Folder responsibilities

- **`app/`** – Entry point (`main.tsx`), application shell, router configuration,
  global providers (QueryClientProvider, AuthProvider, PermissionProvider), and
  error boundaries.
- **`api/`** – HTTP client, API modules grouped by backend domain, and Zod
  schemas that mirror backend responses/requests. Provide thin query hooks
  (`useDocumentsQuery`) that pages/features consume.
- **`pages/`** – Route-level components that orchestrate feature pieces. A page
  composes layout primitives, triggers data fetching via hooks, and wires up
  feature components.
- **`features/`** – Self-contained UI building blocks centered on business
  actions (upload document, submit job, manage members). Each feature exposes its
  public API through `index.ts` and hides internal components/hooks.
- **`components/`** – Design-system primitives (buttons, inputs, layout, table
  shell) that are presentation-only.
- **`hooks/`** – Cross-cutting hooks not specific to any feature (polling,
  keyboard shortcuts, environment configuration).
- **`lib/`** – Pure utility functions (date formatting, table helpers, query key
  builders). No React imports.
- **`styles/`** – Global CSS reset, theme tokens, and utility classes.
- **`mocks/`** – MSW handlers, mock payloads, and Storybook fixtures aligned with
  backend test data.
- **`tests/`** – Shared test helpers for Vitest/RTL, plus Playwright configuration
  at the root-level `tests/` directory.

### 4.3 Feature module shape

Each folder in `features/` follows a predictable structure:

```
features/documents/
├─ components/
│   ├─ DocumentTable.tsx
│   ├─ DocumentUploadDrawer.tsx
│   └─ DocumentMetadataPanel.tsx
├─ hooks/
│   ├─ useDocumentList.ts
│   ├─ useUploadDocument.ts
│   └─ useDeleteDocument.ts
├─ constants.ts
├─ index.ts             # re-export public components/hooks
└─ types.ts             # feature-specific shared types
```

Pages import from `features/documents` rather than digging into internals. Tests
for feature slices live alongside the implementation (`__tests__/` folders) to
keep scope contained.

---

## 5. Workflow outlines

### 5.1 Workspace landing & switching

- Boot loads memberships via `GET /workspaces`; store the default workspace in
  profile or `localStorage` fallback.
- Switching workspaces updates the router path and calls `queryClient.clear()`
  before hydrating new data.
- Admin users surface shortcuts to member management and workspace settings.

### 5.2 Document catalogue

- Paginated table driven by `GET /documents?limit=&offset=` with columns:
  filename, document type (from metadata), uploaded by, created_at, expires_at,
  status (active/deleted).
- Upload drawer provides drag-and-drop, metadata JSON editor, and expires_at
  picker. Submit via `POST /documents` and refresh list.
- Row actions cover download (`GET /documents/{id}/download`) and delete
  (`DELETE /documents/{id}` with optional reason). Soft deletes flag the row as
  deleted without removing it from history.
- Document detail route combines metadata, recent jobs filtered by
  `input_document_id`, and aggregated tables from `GET /documents/{id}/tables`.

### 5.3 Job management

- Job creation form (`/jobs/new`) lists active configurations via
  `GET /configurations/active?document_type=`. Submit to `POST /jobs` and route
  to job detail.
- Job list polls `GET /jobs` every ~15 s while the page is focused. Filters cover
  status, document, configuration.
- Job detail merges `GET /jobs/{id}` and `GET /jobs/{id}/tables`. If tables
  return 409, show a processing state and poll job status until terminal before
  re-requesting tables.

### 5.4 Configuration library

- List view groups configurations by document type using `GET /configurations`.
- Detail drawer exposes metadata, payload JSON, and activation action hitting
  `POST /configurations/{id}/activate`.
- Create/edit forms validate JSON with Zod, surfacing backend validation errors
  inline. Refresh both list and active configuration queries after mutations.

### 5.5 Results exploration

- Table viewers consume `GET /jobs/{id}/tables` and `GET /jobs/{id}/tables/{table_id}`.
  Use TanStack Table with virtualization above ~200 rows.
- Provide CSV download, JSON view, and schema copy. Empty states distinguish
  between pending (409) and absent results.
- Document detail route reuses the same viewer but grouped by job.

### 5.6 Workspace administration

- Member table reads `GET /workspaces/{id}/members` and shows role badges.
- Add/remove actions call POST/PATCH/DELETE endpoints with confirmation dialogs
  and inline permission errors.
- Workspace metadata editor sends `PATCH /workspaces/{id}` with optimistic UI.

---

## 6. Delivery roadmap

1. **Bootstrap shell (first milestone)** – Initialize Vite project with strict
   TypeScript, set up router under `/workspaces/:workspaceId`, configure global
   providers (React Query, Auth, Permissions), and implement navigation shell
   with placeholder pages.
2. **HTTP client & mocks** – Build `api/client.ts`, domain modules, React Query
   hooks, and MSW mocks mirroring backend schemas.
3. **Documents slice** – Document list, upload flow, detail view, download, and
   delete actions.
4. **Configurations slice** – List, detail, create/edit, activate.
5. **Job submission & detail** – New job form, list with polling, detail view,
   and tables integration.
6. **Document-centric results** – Aggregate tables per document.
7. **Workspace admin** – Member management and workspace settings.
8. **Hardening** – Accessibility sweep, Playwright smoke path, bundle monitoring,
   and CI hooks.

Each milestone ships Storybook coverage, Vitest specs, and MSW fixtures so
backend/front-end parity is preserved.

---

## 7. Collaboration checkpoints

- **Schema parity** – Mirror Pydantic models into Zod types. Add CI that fails
  when contracts drift.
- **Error documentation** – Capture exact error envelopes for Storybook and
  regression tests (upload limits, job failure scenarios, permission denials).
- **Sample data** – Maintain anonymized fixtures in `frontend/src/mocks/` that
  align with backend tests under `backend/tests/`. Update both when payloads
  change.
- **Configuration** – Read API base URL, auth client ID, and feature flags from
  `import.meta.env` to support staging/production consistency.

Keep this guide synchronized with `BACKEND_REWRITE_PLAN.md`. If the backend
introduces background processing, streaming logs, or new permissions, update the
relevant sections before coding so engineering efforts stay aligned.
