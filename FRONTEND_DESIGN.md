# ADE frontend architecture blueprint

ADE's frontend turns the backend rewrite into analyst-friendly workflows. This
blueprint captures the smallest dependable surface area we need for v1 and how
the UI collaborates with the FastAPI services that already exist. Treat it as
the contract for structure, state management, and integration points—update it
whenever those decisions shift.

---

## 1. Objectives & guardrails

- **Source of truth** – Describe the application skeleton, feature boundaries,
and backend contracts for ADE's web client.
- **Scope** – Desktop-first React + TypeScript app delivered by Vite. Touch and
mobile optimisations, theming, and advanced personalization remain out of scope
until the core workflows are stable.
- **Design ethos** – Prefer predictable layout primitives, typed APIs, and
explicit state transitions. Avoid speculative abstractions; optimise when usage
data proves the need.
- **Change hygiene** – When the backend introduces or removes endpoints, or we
change how routes behave, update this blueprint and cross-link to the backend
plan so future contributors have the full context.

---

## 2. Domain alignment with the backend

The backend rewrite currently exposes synchronous workflows centred on
documents, configurations, jobs, and extracted results. The frontend mirrors
those modules; every page should rely on the existing endpoints before inventing
new state.

| Backend module | Primary endpoints | Key fields surfaced to the UI |
| --- | --- | --- |
| **Documents** (`/documents`) | `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/download`, `DELETE /documents/{id}` | `id`, `original_filename`, `content_type`, `document_type`, `created_at`, `expires_at`, soft-delete metadata |
| **Configurations** (`/configurations`) | `GET /configurations`, `GET /configurations/{id}`, `GET /configurations/{id}/events` | `configuration_id`, `document_type`, `title`, `version`, `is_active`, `payload` (JSON), timestamps |
| **Jobs** (`/jobs`) | `POST /jobs`, `GET /jobs`, `GET /jobs/{id}` | `job_id`, `document_type`, `configuration_id`, `configuration_version`, `status`, `metrics`, `logs`, timestamps |
| **Results** (`/jobs/{id}/tables`) | `GET /jobs/{id}/tables`, `GET /jobs/{id}/tables/{table_id}`, `GET /documents/{id}/tables` | `table_id`, `sequence_index`, `title`, `row_count`, `columns`, `sample_rows`, `metadata` |
| **Events** | `GET /configurations/{id}/events` | Audit timeline entries surfaced in detail drawers |
| **Workspaces & auth** | Workspace-scoped routers enforce permissions. Every request requires `workspace_id` in headers/query (handled by API client). |

Backend assumptions to bake into the UI:

1. **Workspace context** – All routers are workspace-scoped. The frontend must
select a workspace before showing data and include the context in API calls.
2. **Deterministic processing** – Jobs execute synchronously. Polling for job
status is safe, but websockets/background queues do not exist yet.
3. **No document-type catalog API** – `document_type` is a string on
configurations/documents. Aggregate lists derive from existing payloads rather
than separate endpoints.
4. **Read-only configurations** – The backend currently exposes read routes and
events. Authoring/publishing flows are future work; the UI should only display
metadata and event logs for now.
5. **Result availability** – `/jobs/{id}/tables` returns 409 if the job is not
`Succeeded`. Surfaces must handle this conflict explicitly.

Consult `BACKEND_REWRITE_PLAN.md` when extending the UI to confirm upcoming
capabilities (e.g., retention policies) and to avoid diverging terminology.

---

## 3. Application architecture

### 3.1 Entry point & routing

- `frontend/src/app/App.tsx` creates the React Router data router, wraps it in
providers (React Query, theming, toast notifications), and exports `createApp()`
for tests and Storybook.
- Routes live under `frontend/src/features/<domain>/pages`. Each page exports:
  - `Component` – the React component rendered by the route.
  - `loader` – fetches initial data, seeds React Query, and resolves redirects.
  - `action` – optional mutation handler invoked by `<Form>` submissions.
  - `ErrorBoundary` – localized fallback aligned to the page layout.
- Route configuration resides in `frontend/src/app/router.tsx` and wires shared
layouts. Nested routes share the application shell so navigation and feedback are
consistent.

### 3.2 Layout shell

- **Navigation rail** – Persistent left rail housing links for Documents,
Configurations, Jobs, and Admin. Collapse into an overlay drawer ≤1024 px.
- **Top bar** – Workspace selector, user menu, global notices, unsaved indicator
hooked into a shared form state context. Also exposes a “Copy API token” entry
point for developers.
- **Content frame** – Page header (title, primary actions, status chip) above a
CSS grid body. Max width 1440 px, 32 px gutters, 8 px baseline for spacing.
- **Feedback** – Toast stack anchored top-right. Long-running actions show inline
progress rows pinned near their trigger.

### 3.3 Styling & primitives

- Layout primitives (`Stack`, `Columns`, `Sidebar`, `Card`, `DataTableShell`)
live in `frontend/src/components/primitives/`. They only express flex/grid
behaviour and spacing tokens—no business logic.
- Design tokens exported from `frontend/src/styles/tokens.ts` cover colour,
typography, radii, elevation, and focus rings. Global styles are limited to
`frontend/src/styles/global.css` (reset + typography scale).
- Icons are generated with SVGR into `frontend/src/components/icons/` with a
consistent 24 px canvas.

### 3.4 State & data fetching

- React Query manages server state. Query keys mirror the backend endpoints and
include parameter objects (`['jobs', { status, offset }]`).
- Route loaders call `prefetchQuery` + `dehydrate` so initial navigation renders
instantly without waterfalls.
- UI state (filters, drawers, selected rows) remains local to a feature via
context or component state. Introduce a dedicated store (e.g., Zustand) only if
React context becomes insufficient.
- API client (`frontend/src/api/client.ts`) wraps `fetch` with JSON parsing,
error normalization, request cancellation, and workspace header injection.
Endpoint helpers pair each call with a Zod schema so TypeScript types are inferred
from runtime validation.

### 3.5 Forms & validation

- React Hook Form + Zod power form state. Inputs live under
`frontend/src/components/form/` and forward refs + aria props.
- Submit buttons disable while pending. Errors render inline and map to backend
field names when available.
- Multi-step flows share a single `<form>` element; step navigation simply swaps
visible sections.
- Persist defaults via loader data or React Query caches instead of refetching on
repeat visits.

### 3.6 Testing & tooling

- Vitest + React Testing Library for unit/interaction tests colocated with their
components (`*.test.ts(x)`).
- Mock Service Worker (MSW) supplies deterministic API fixtures shared by tests
and Storybook.
- Playwright covers golden paths once routes stabilise (upload document, submit
job, review results).
- CI runs `npm run lint`, `npm run typecheck`, `npm run test`, and Playwright
smoke specs.

---

## 4. Primary routes & workflows

The frontend leans on five high-value routes. Each section outlines layout,
data requirements, and implementation notes tied to backend reality.

### 4.1 Workspace gate (`/`)

- **Purpose** – Ensure a workspace is selected before showing domain data.
- **Layout** – Centered card listing permitted workspaces. Selecting one stores
the identifier in `localStorage` and redirects to Documents.
- **Implementation notes** – All API helpers read the stored workspace id and
attach it via header/query per backend requirements. If the token lacks
permissions, surface the `403` response in a callout with retry guidance.

### 4.2 Document catalogue (`/documents`)

**Layout**
- Page header with “Upload document” primary action and filters for status
(active vs soft-deleted) and document type (derived from query results).
- Body renders a table: filename, document type, uploaded by, created date,
expiration, last job status. Row actions: download, view tables, submit job.
- Empty state shows guidance and upload CTA.

**Backend integration**
- List view calls `GET /documents?limit=&offset=` and `GET /jobs?input_document_id`
for recent job context (prefetched per row).
- Upload drawer posts `FormData` to `POST /documents` (metadata serialized JSON).
- Download button hits `GET /documents/{id}/download` streaming endpoint.
- Delete action sends `DELETE /documents/{id}` with optional reason body.

**Implementation notes**
- File intake uses `react-dropzone`; a `useFileQueue` hook handles validation and
progress for sequential uploads. Persist queue state in `sessionStorage` to
survive accidental refreshes.
- Table built on the shared `DataTable` primitive (TanStack Table). Filters map
onto URL search params for shareable views.
- Prefetch extracted tables via `queryClient.prefetchQuery(['documents', id, 'tables'])`
when hovering “View tables”. Handle 404/409 gracefully (document deleted or no
results yet).

### 4.3 Configuration directory (`/configurations` and `/configurations/:id`)

**Layout**
- `/configurations` displays a grouped list by `document_type` with active
versions highlighted. Search filters by title/document type.
- `/configurations/:id` shows metadata summary, version details, payload preview
(JSON viewer), and the audit event timeline.

**Backend integration**
- List view calls `GET /configurations?limit=&offset=&document_type=`; since the
API is read-only, editing actions are hidden until backend support arrives.
- Detail page fetches `GET /configurations/{id}` plus
`GET /configurations/{id}/events` for timeline rows.

**Implementation notes**
- Because `payload` is opaque JSON, render a read-only inspector with collapsed
sections (split between core keys vs advanced metadata).
- Event timeline entries reuse shared `ActivityFeed` components for consistency
with other audit surfaces.
- When configuration data is missing (404), redirect to the list with an inline
toast.

### 4.4 Job submission console (`/jobs/new`)

**Layout**
- Dual-panel page: left column lists uploaded documents (search + pagination);
right column hosts the job submission form with document selector, configuration
selector, and optional configuration version override.
- Inline status panel shows the most recent submission result.

**Backend integration**
- Documents dropdown consumes `GET /documents` data (reuse cache from catalogue).
- Configurations dropdown uses `GET /configurations` results filtered by
`document_type` when a document is chosen.
- Submitting the form posts `JobSubmissionRequest` to `POST /jobs` and navigates
to `/jobs/{job_id}` on success.

**Implementation notes**
- Validate the configuration/document pairing on the client before submission.
- While the backend executes jobs synchronously, keep the submit button disabled
until the promise resolves and display any `JobExecutionError` payload returned
from the API.
- Persist last-selected document/configuration combination in `localStorage`
(scoped per workspace) for faster repeat submissions.

### 4.5 Job detail & monitoring (`/jobs` and `/jobs/:id`)

**Layout**
- `/jobs` lists recent jobs with filters for status and document type. Columns:
job id, document, configuration version, status badge, created date, duration.
- `/jobs/:id` shows status summary, metrics, logs, and extracted tables.
  - Summary header: status, created at, created by, configuration version.
  - Tabs: **Overview** (metrics, log entries), **Tables** (list from results
module).

**Backend integration**
- List view queries `GET /jobs?limit=&offset=&status=&input_document_id=`.
- Detail view loads `GET /jobs/{id}` plus `GET /jobs/{id}/tables`. If the tables
endpoint returns 409 (job incomplete), poll `GET /jobs/{id}` until status is a
terminal state before retrying the tables call.

**Implementation notes**
- Encapsulate polling in `useJobPolling(jobId)`; pause when the tab is hidden via
Page Visibility API.
- Logs arrive as `list[dict[str, Any]]`; present them via structured accordions,
falling back to JSON viewer for unknown shapes.
- `Mark as reviewed` is deferred until the backend introduces the endpoint; keep
space in the layout but hide the action for now.

### 4.6 Document results (`/documents/:id`)

**Layout**
- Header summarises document metadata. Tabs: **Activity** (recent jobs) and
**Tables** (aggregated extracted tables across jobs).

**Backend integration**
- Metadata from `GET /documents/{id}`. Activity tab reuses `GET /jobs` filtered
by `input_document_id`. Tables tab calls `GET /documents/{id}/tables` and links to
individual job table views.

**Implementation notes**
- When `/documents/{id}/tables` returns empty, show an informative empty state
with CTA to run a job.
- Keep interactions read-only until backend supports editing metadata post-upload.

### 4.7 Deferred for post-v1

- Configuration authoring, publishing, and script editing flows.
- Real-time job progress via websockets.
- Resumable uploads for large documents.
- Personalised dashboards or alerting rules.

---

## 5. Component systems & shared patterns

### 5.1 Tables & lists

- TanStack Table underpins all grid views. The shared `DataTable` component owns
header layout, skeleton states, pagination controls, and empty/error visuals.
- Server pagination is the default. Consider `@tanstack/react-virtual` only when
we observe sustained datasets beyond a few hundred rows.
- Column definitions live beside the page component. Compose filters from URL
search params via `useSearchParams()` helpers for shareable links.

### 5.2 Feedback & accessibility

- Toast provider handles success/error messages with sensible auto-dismiss
timeouts. Inline `Callout` components communicate warnings or blockers.
- Destructive flows rely on Radix `AlertDialog` with explicit button labelling.
- Maintain logical heading structure and skip links anchored to the content
frame. All focus states derive from tokens to ensure consistent contrast.
- Long-running operations (uploads, job execution polling) use `aria-live`
regions to announce updates.

### 5.3 API client patterns

- `api/client.ts` exposes `get`, `post`, `patch`, `del`, each returning a typed
result validated through Zod schemas.
- Inject workspace context header (e.g., `X-ADE-Workspace-ID`) and auth token via
a shared interceptor.
- Normalize error responses into `{ code, message, fieldErrors? }` so components
can render consistent messaging.
- Keep retries conservative—React Query defaults (retry 3 times for network
failures) are acceptable. For 4xx errors, surface immediately without retry.

### 5.4 Scripting + JSON viewers

- Until the backend exposes editable scripts, reuse a lightweight `JsonViewer`
component (virtualised tree) to render configuration payloads and result sample
rows. Monaco is unnecessary until editing arrives, reducing bundle size.

### 5.5 Testing strategy

- Every feature slice ships with:
  - Unit tests for hooks/utilities.
  - Component tests covering empty, loading, error, and populated states.
  - Storybook stories using MSW fixtures (default, error, empty).
- Playwright smoke tests cover upload → job submission → table review once the
primary routes are implemented.

---

## 6. Build sequencing

1. **Foundations** – Establish Vite project, TypeScript config, tokens, layout
primitives, API client scaffold, and routing shell with workspace guard.
2. **Documents workflow** – Implement catalogue table, upload drawer, download
stream, and soft delete. Validate against existing documents endpoints.
3. **Configurations browse** – Ship list + detail routes (read-only). Integrate
event timeline and JSON payload viewer.
4. **Job submission** – Build `/jobs/new` form, ensure validation against the
backend contract, and navigate to job detail upon success.
5. **Job detail & results** – Implement list + detail pages with polling, metrics
view, and tables tab wired to results endpoints.
6. **Document detail** – Aggregate runs and extracted tables per document.
7. **Testing & hardening** – Add Playwright smoke path, Storybook coverage, and
monitor bundle size (particularly JSON viewers and table libraries).

This sequencing lines up with the backend rewrite priorities (document intake →
job execution → result review). Additional backend milestones (cleanup policies,
expanded permissions) should trigger updates here when they land.

---

## 7. Integration checkpoints

- **Authentication & workspace header** – Confirm the exact header/query naming
for workspace context and ensure token refresh flows are centralised.
- **Error contracts** – Capture the JSON error envelope (code, message,
field-level details) so form handlers can display precise feedback.
- **Sample data** – Curate anonymised API fixtures (documents, jobs, tables) to
power Storybook stories and Playwright tests.
- **Permissions** – Align UI affordances with backend permission checks. Hide or
disable actions when `403` responses are expected.
- **Telemetry** – Once routes stabilize, emit page view and API failure metrics
via a lightweight analytics hook (deferred until after v1 launch).

Keep this document and `BACKEND_REWRITE_PLAN.md` in sync—backend changes to
workflow states or payloads should immediately reflect here.
