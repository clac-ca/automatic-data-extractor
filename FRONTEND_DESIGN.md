# ADE frontend design

This document describes how the Automatic Data Extractor (ADE) web client should
look, feel, and stay aligned with the FastAPI backend. Treat it as the source of
truth for product scope, UX patterns, technical architecture, and directory
structure. Update it whenever the backend contracts or roadmap shift.

---

## 1. Purpose & scope

- **Goals**
  - Give workspace members a predictable way to upload documents, launch
    extraction jobs, and inspect results.
  - Provide a calm, accessible UI that mirrors backend capabilities without
    inventing extra abstractions.
  - Standardise the frontend project structure so new contributors understand
    where features live and how they integrate with ADE services.
- **Non-goals**
  - Designing marketing pages or anonymous experiences.
  - Supporting multi-tenant UX beyond the existing workspace concept.
  - Implementing speculative workflows that the backend does not yet expose.

---

## 2. Product context

- **Personas**
  - *Workspace analyst* – uploads documents, triggers jobs, reviews extracted
    tables, exports data.
  - *Reviewer* – audits job outputs, compares versions, and flags issues back to
    analysts.
  - *Workspace admin* – manages workspace metadata, memberships, and available
    document-type configurations.
- **Experience principles**
  - *Workspace anchored* – the selected workspace scopes every request; switching
    workspaces clears cached data and redirects to the equivalent route.
  - *Guided clarity* – each screen shows current state, primary actions, and
    contextual help or empty states instead of error modals.
  - *Accessible calm* – high contrast neutrals, visible focus outlines, and
    motion limited to subtle hover or progress feedback.

---

## 3. Information architecture

### 3.1 Application shell

- **Top bar** – persistent workspace switcher (mirrors `GET /workspaces`),
  document-type filter (derived from active configurations), and user menu
  (profile + sign out). The selected document type is stored in local storage and
  applied wherever relevant.
- **Side navigation** – sections align with backend modules: Overview,
  Documents, Jobs, Results, Configurations, Workspace settings. Collapse to icon
  rail on narrow viewports while keeping accessible labels.
- **Content area** – 12-column responsive grid with 24 px outer gutters, 16 px
  card spacing, 8 px radius, and 1 px neutral borders. Context headers provide
  breadcrumb, title, and page-level actions. Toasts appear bottom-right; a status
  tray surfaces long-running uploads or jobs.

### 3.2 Route map

| Route | Purpose | Key data sources |
| ----- | ------- | ---------------- |
| `/sign-in` | Credential form, posts to token endpoint. | `POST /auth/token` |
| `/workspaces` | Workspace directory and recent activity. | `GET /workspaces` |
| `/workspaces/:workspaceId/overview` | Summary cards: workspace metadata, recent documents, active jobs. | `GET /workspaces/{id}`, `GET /documents`, `GET /jobs` |
| `/workspaces/:workspaceId/documents` | Document library, upload drawer, metadata detail. | `GET/POST/DELETE /documents`, `GET /documents/{id}/tables` |
| `/workspaces/:workspaceId/jobs` | Job list, submission flow, job detail. | `GET/POST /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/tables` |
| `/workspaces/:workspaceId/results` | Results explorer with table previews and exports. | `GET /jobs/{id}/tables`, `GET /documents/{id}/tables` |
| `/workspaces/:workspaceId/configurations` | Manage configuration versions and activation. | `GET/POST/PUT /configurations`, `POST /configurations/{id}/activate` |
| `/workspaces/:workspaceId/settings` | Workspace metadata and membership management. | `GET/PATCH /workspaces/{id}`, `GET/PATCH/DELETE /workspaces/{id}/members` |

---

## 4. Core workflows

### 4.1 Document ingestion

1. Analyst lands on Documents page with the workspace-selected document type
   pre-filtered.
2. Upload drawer exposes a drag-and-drop zone, queued file list, and inline form
   for metadata.
3. "Advanced options" reveals configuration overrides allowing a single
   configuration or multiple configurations to be selected per upload. The
   default selection is the workspace’s current configuration for the chosen
   document type.
4. On submit, files upload via multipart `POST /documents`; progress and errors
   surface in the status tray and toasts.

### 4.2 Job submission & monitoring

- Jobs list groups by status with optional polling while the tab is visible.
- Submitting a job follows a three-step form: pick documents, choose
  configuration (filtered by document type), review + submit.
- Detail view shows status timeline, configuration metadata, related documents,
  and links to extracted tables. HTTP 409 responses display an inline processing
  banner and retry automatically until terminal.

### 4.3 Results review

- Results page defaults to the top-bar document type and lists recent jobs.
- Selecting a job opens a split-pane viewer: virtualised table grid on the left
  and schema/metadata/actions on the right.
- Analysts can pin two jobs to compare table schemas and sample rows, highlighting
  differences before export.

### 4.4 Configuration management

- Cards summarise active configuration versions by document type.
- Detail pages use a two-column layout: metadata summary and JSON editor with
  Zod-backed validation. Buttons provide activate, clone, and delete where
  permitted.
- Creating a new version uses a modal or dedicated page with document type,
  title, and payload fields.

### 4.5 Workspace administration

- Members tab lists users, roles, and defaults with inline edit/remove actions.
- Metadata form allows updating name, description, slug, and retention policy.
- Provide a call-to-action to mark the current workspace as the default for the
  signed-in user.

---

## 5. UI system & accessibility

- **Typography** – Inter (system UI fallback). Type ramp: `h1 28/36`, `h2 24/32`,
  `h3 20/28`, body `16/24`, caption `13/18`. Use weight 600 for section titles
  and 500 for buttons.
- **Color tokens** – Neutral background `#F8FAFC`, surfaces `#FFFFFF`, accent
  `brand-500` for primary actions, semantic tokens `success-500`, `warning-500`,
  `error-500` aligned with backend emails.
- **Controls** – Maintain 1 px focus outlines in accent color. Buttons and inputs
  use 8 px radius with `0.2s ease` transitions. Skeleton loaders cover tables or
  cards while data fetches.
- **Forms** – React Hook Form + Zod provide validation and error messaging.
  Inline errors list backend validation issues mapped by field path.
- **Responsive behaviour** – Layout adapts from desktop grid to stacked cards on
  small screens; navigation collapses to a menu toggle below 1024 px.

---

## 6. Technical architecture

- **Framework & tooling** – Vite + React + TypeScript, Vitest + Testing Library,
  ESLint + Prettier, and React Router for routing.
- **Data fetching** – TanStack Query handles caching, deduplication, retries, and
  background refresh. Query keys follow `[workspaceId, domain, filters]` so cache
  invalidation on workspace change is automatic.
- **State management** – Lightweight context for authentication session and
  workspace selection. All other domain state lives in React Query or component
  state.
- **API layer** – `src/api/` exposes a thin `ApiClient` wrapper around `fetch`
  plus typed helper modules per backend domain (documents, jobs, etc.). Error
  mapping converts backend error shapes into friendly messages. If `VITE_API_BASE_URL` is not set,
  the client defaults to `http://127.0.0.1:8000` during local development.
  document-type filter). Changes trigger React Query invalidation to reflect new
  context.
- **Error handling** – 401/403 responses clear auth state, show toast, and
  redirect to sign-in. Non-field errors surface through the toast provider while
  forms display inline feedback.
- **Testing** – Component tests live beside features, integration tests under
  `frontend/tests/`. Critical workflows (sign-in, document upload, job creation)
  have happy-path and error-state coverage. Playwright end-to-end tests can be
  added once the core flows stabilise.

---

## 7. Project structure

```
frontend/
├─ public/                 # Static assets (favicons, manifest)
├─ src/
│  ├─ app/                 # Application shell, global providers, router
│  ├─ api/                 # ApiClient, typed domain clients, error helpers
│  ├─ features/            # Domain modules (documents, jobs, results, etc.)
│  ├─ pages/               # Route-level components composing features
│  ├─ components/          # Shared presentational primitives (buttons, tables)
│  ├─ hooks/               # Cross-cutting hooks (useWorkspaceId, useToast)
│  ├─ styles/              # Global styles, design tokens, CSS utilities
│  └─ utils/               # Pure helpers (formatters, schema mappers)
├─ tests/                  # Vitest integration and provider-level tests
└─ vite.config.ts          # Build configuration
```

Guidelines:
- Pages orchestrate data fetching and side effects; presentational components
  remain stateless.
- Feature directories contain domain-specific components, hooks, and tests.
- Co-locate Vitest files with the code they exercise when they are unit scoped;
  use `frontend/tests/` for integration helpers and cross-feature cases.

---

## 8. Backend alignment

| Frontend area | Backend module | Key endpoints |
| ------------- | -------------- | ------------- |
| Workspaces & shell | `backend/api/modules/workspaces` | `GET /workspaces`, `GET /workspaces/{id}`, `PATCH /workspaces/{id}`, `POST /workspaces/{id}/default` |
| Documents | `backend/api/modules/documents` | `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/download`, `DELETE /documents/{id}`, `GET /documents/{id}/tables` |
| Jobs | `backend/api/modules/jobs` | `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/tables` |
| Results | `backend/api/modules/results` | `GET /jobs/{id}/tables`, `GET /jobs/{id}/tables/{table_id}`, `GET /documents/{id}/tables` |
| Configurations | `backend/api/modules/configurations` | `GET /configurations`, `POST /configurations`, `PUT /configurations/{id}`, `DELETE /configurations/{id}`, `POST /configurations/{id}/activate` |
| Authentication | `backend/api/modules/auth` | `POST /auth/token` |

Any change to backend response shapes must be reflected in the corresponding
client module and documented here.

---

## 9. Delivery roadmap

1. **Shell & foundation** – Build sign-in flow, app layout, workspace switcher,
   persisted document-type filter, and overview cards.
2. **Documents & jobs** – Implement document library with upload drawer,
   advanced configuration overrides, job submission wizard, and job detail with
   polling.
3. **Results explorer** – Ship results list, table viewer, export actions, and
   comparison mode.
4. **Configuration workflows** – Deliver configuration list/detail CRUD,
   activation flow, and validation.
5. **Workspace settings** – Implement membership management, metadata forms, and
   default workspace toggle.
6. **Polish & automation** – Accessibility audit, keyboard shortcuts, toast
   refinements, and end-to-end coverage.

---

## 10. Maintenance

- Keep this document and `BACKEND_REWRITE_PLAN.md` in sync; update both when
  endpoints, workflows, or priorities change.
- When adding a feature, document the new route, data requirements, and testing
  expectations before coding to avoid drift.
- Prefer incremental changes that ship with tests, accessible UI, and descriptive
  commit history.





