# Work Package: Documents Filter Redesign

## Summary
Redesign the documents grid end to end so filtering, sorting, pagination, and URL state are shared between the frontend and backend. Ship the work in deliberate phases that harden the database first, adopt consistent terminology, introduce backend-enforced filters with a shared limit/offset pagination helper, and finally align the UI.

## Phased delivery plan

### Phase 1 – Database schema consolidation (SQLite-first, Postgres-ready)
- Update `ade/db/migrations/versions/0001_initial_schema.py` directly, then recreate the local database (no data backfill required).
- Apply the following deltas to the `documents` table:
  - `uploaded_by_user_id TEXT NULL` referencing `users(user_id)` with `ON DELETE SET NULL`.
  - `status TEXT NOT NULL CHECK (status IN ('uploaded','processing','processed','failed','archived'))`.
  - `source TEXT NOT NULL CHECK (source IN ('manual_upload')) DEFAULT 'manual_upload'`.
  - `last_run_at TIMESTAMP NULL` (timezone-aware in Postgres, nullable and should sort last when absent).
  - Retain `created_at` as the canonical uploaded timestamp.
- Create the `document_tags` join table: `(document_id TEXT, tag TEXT, PRIMARY KEY(document_id, tag))`.
- Add indexes:
  - `documents(workspace_id, status, created_at DESC)`
  - `documents(workspace_id, last_run_at DESC)`
  - `documents(workspace_id, source)`
  - `documents(workspace_id, uploaded_by_user_id)`
  - `document_tags(document_id)` (add `document_tags(tag)` when tag filtering ships).

### Phase 2 – Backend filtering primitives
- Introduce a canonical filter schema that matches the updated terminology.
- Define shared enums/constants for `status`, `source`, sortable fields, and the shared ULID identifier type.
- Model tag relationships via SQLAlchemy relationships or lightweight join queries.
- Add validation utilities for repeatable list filters and date windows.

### Phase 3 – API contract & pagination
- Define a `FilterParams` Pydantic model injected with `Depends`, using `list[...]` for repeatable params.
- Add a shared pagination helper (e.g., `ade/platform/pagination.py`) that exposes `PaginationParams` (page/per_page validation, optional `include_total`) and `paginate_query(query, params)` to apply SQLAlchemy `offset/limit` and return `{items, page, per_page, has_next}` by default, adding `total` when totals are requested; make it reusable across feature routers.
- Flatten the query string: `status=processing&status=processed` rather than JSON:API namespaces.
- Build a query builder that translates `FilterParams` into SQLAlchemy filters (AND across keys, OR within repeatable values).
- Support the following fields/operators:

| Concern | Field(s) | Operators | Notes |
| --- | --- | --- | --- |
| Ownership | `uploader=me`, `uploader_id` | `eq` (server-resolved) / repeatable IDs | `uploader=me` resolves to `uploaded_by_user_id` server-side; `uploader_id` accepts explicit ULIDs (repeatable). |
| Status | `status` | repeatable equality | Allowed values: `uploaded`, `processing`, `processed`, `failed`, `archived`. |
| Source | `source` | repeatable equality | Allowed value today: `manual_upload`. |
| Tags | `tag` | repeatable equality | Any-of semantics (OR within tags). |
| Search | `q` | substring match | Case-insensitive match across the stored filename and uploader display name. |
| Created window | `created_from`, `created_to` | inclusive datetime bounds | UTC ISO-8601 applied to `created_at`. |
| Last run window | `last_run_from`, `last_run_to` | inclusive datetime bounds | UTC ISO-8601 applied to nullable `last_run_at`; treat `NULL` as "never". |
| Byte size | `byte_size_min`, `byte_size_max` | numeric bounds | Optional filter. |

- Sorting: accept a single `sort` field with optional `-` prefix. Allowed values: `created_at` (default `-created_at`), `status`, `last_run_at`, `byte_size`, `source`, `name` (maps to the `original_filename` column). Null `last_run_at` sorts last.
- Pagination: `page` and `per_page` (default 50, max 200). Response shape: `{ "items": [...], "page": 1, "per_page": 50, "has_next": false }` by default; include `"total": 321` only when `include_total=true` is supplied.
- Return payloads that expose `document_id` consistently across list and detail endpoints (alias to `id` internally only when needed).
- Validation: reject unknown parameters or operators with HTTP 400 (Problem+JSON).

### Phase 4 – Frontend integration & UX alignment
- Update the Documents route to read/write flat query params and omit defaults when serialising the URL.
- Introduce a shared hook/utility for translating between component state and the canonical filter schema.
- Refresh toolbar controls to match the filter model: uploader toggle (All ↔ Me) that sets/clears `uploader=me`, status multiselect, tag combobox, substring search (`q`), date range pickers, and reset control.
- Ensure pagination controls mirror backend expectations (page/per_page, has-next summary by default, show totals when available).
- Update telemetry to emit the flattened filter payload and respect ULID string identifiers throughout.

### Phase 5 – Verification & rollout
- Add unit tests for filter serialisation/deserialisation and the query builder.
- Add endpoint tests covering validation failure modes, pagination metadata, and tag any-of semantics.
- QA the frontend to confirm URL round-tripping, inclusive date filters, nullable `last_run_at` sorting last, and `uploader=me` resolution.
- Document migration steps (DB recreation) and rollout notes in `CHANGELOG.md` when shipping.

## API contract

### Request
`GET /api/v1/workspaces/{workspace_id}/documents`

Query parameters (all optional, flat namespace, ULID identifiers rendered as 26-character strings):
- `status`: repeatable; allowed values `uploaded`, `processing`, `processed`, `failed`, `archived`.
- `source`: repeatable; allowed values `manual_upload` (future sources extend the enum).
- `tag`: repeatable; matches tag strings with any-of semantics.
- `uploader`: `me` (server resolves to the authenticated user’s ID).
- `uploader_id`: repeatable; explicit user IDs (ULIDs).
- `q`: substring search across document name and uploader metadata.
- `created_from`, `created_to`: inclusive UTC timestamps (ISO-8601) applied to `created_at`.
- `last_run_from`, `last_run_to`: inclusive UTC timestamps applied to nullable `last_run_at`.
- `byte_size_min`, `byte_size_max`: byte bounds.
- `sort`: one of `created_at`, `-created_at`, `status`, `-status`, `last_run_at`, `-last_run_at`, `byte_size`, `-byte_size`, `source`, `-source`, `name`, `-name`.
- `page`: 1-based page number (default 1).
- `per_page`: page size (default 50, max 200).
- `include_total`: boolean flag (default `false`) that triggers a total count query when true.

### Response
Default responses include `{"items", "page", "per_page", "has_next"}`. When `include_total=true` the payload also returns a `total` count, as illustrated below.
```json
{
  "items": [
    {
      "document_id": "01HZ4GQ2VTWQX9SZ4CE00N7AZQ",
      "name": "Quarterly Report.pdf",
      "status": "processed",
      "source": "manual_upload",
      "tags": ["finance", "2024"],
      "created_at": "2024-03-18T15:42:00Z",
      "last_run_at": "2024-03-18T16:00:00Z",
      "byte_size": 123456,
      "content_type": "application/pdf",
      "uploader": { "id": "01HYWQPZYTN7Z8KRYFXS8V1E4T", "name": "Alice Example", "email": "alice@example.com" }
    }
  ],
  "page": 1,
  "per_page": 50,
  "has_next": false,
  "total": 321
}
```

### Behavioural notes
- Unknown parameters or values outside the whitelists return HTTP 400 with Problem+JSON details.
- `uploader=me` resolves server-side using the authenticated principal; omit client heuristics.
- Tag filtering is inclusive OR within tags, AND across other filter categories.
- Date range filters are inclusive and expect UTC ISO-8601 timestamps.
- `last_run_at` is nullable; surface `null` when no extraction has run and treat those records as last when sorting (after non-null timestamps).
- Pagination uses the shared helper so every endpoint returns the `{items, page, per_page, has_next}` envelope consistently, appending `total` when explicitly requested.
- Document and user identifiers are ULIDs (26-character strings) exposed as plain strings in the API.
- `name` remains the display-friendly field mapped from `original_filename` across the API and UI.

## Minimal, consistent grid UX
- Toolbar controls: uploader toggle (All / Me) mapped to `uploader` (`me` sets the filter, clearing returns to all), optional uploader picker for admins, status multiselect, tag combobox, substring search (`q`), date range pickers for created/last run, reset button, and upload CTA.
- Active filters display as dismissible chips that mirror the flat query params (omit defaults in the URL).
- Table columns: Document, Status, Source, Created (absolute + relative), Last run, Size, Tags, Actions. Column sorts align with backend-enforced options.
- Pagination footer: page selector, per-page selector (25/50/100/200 capped at 200), has-next summary by default (show totals when available), upload shortcut.
- Empty states add “Clear filters” when any filter is active and reuse existing copy otherwise.

## Acceptance criteria
1. Database schema matches Phase 1 (including new indexes) by editing `ade/db/migrations/versions/0001_initial_schema.py`; local databases are recreated with the new structure.
2. Backend filters honour the flat query parameters, resolve `uploader=me`, apply tag any-of semantics, and treat date ranges as inclusive.
3. Sorting accepts only the approved single-field values, maps `name` to `original_filename`, keeps created-date pagination stable via a `created_at DESC, document_id DESC` tie-breaker, and orders `last_run_at` nulls last.
4. Pagination uses `page`/`per_page`, caps `per_page` at 200, and responds with `{items, page, per_page, has_next}` by default, adding `total` only when `include_total=true`.
5. URL state and UI state round-trip without defaults: clearing filters removes params; adding filters populates matching keys.
6. Validation rejects unknown parameters/operators with HTTP 400 (Problem+JSON).
7. Pagination flows through the shared helper; tests cover validation, pagination, and query-builder branching.

## FastAPI implementation notes
- Define a `FilterParams` Pydantic model with fields matching the URL keys; inject via `Depends`.
- Use `list[...]` annotations for repeatable params (`status`, `source`, `tag`, `uploader_id`).
- Normalise `uploader=me` inside the dependency by looking up the authenticated user.
- Build a query builder that converts `FilterParams` into SQLAlchemy filters (AND between categories, OR across repeatables).
- Implement `ade/platform/pagination.py` (or similar) with `PaginationParams`, `Paginated[T]` response model, and a helper that applies `offset/limit`, exposes `has_next`, and optionally performs a `select(func.count())` when `include_total` is true.
- Keep response models and enums in `ade/features/documents/schemas.py` for reuse by tests, re-exporting the shared `Paginated[DocumentOut]` type.

## Decision record
We will replace the ad-hoc, client-only filters with a backend-enforced contract that keeps terminology, ULID identifiers, and pagination consistent across the stack. Locking the schema first eliminates downstream churn, and adopting flat query parameters plus a reusable limit/offset helper keeps FastAPI endpoints predictable without adding third-party dependencies. The phased approach ensures the API and frontend evolve together while remaining testable and predictable.
