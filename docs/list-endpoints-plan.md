# Pagination, Sorting, and Filtering Plan

This document captures the full design for implementing a standardized pagination, sorting, and filtering stack across ADE list endpoints.

## Context & Goal

- Stack: FastAPI + SQLAlchemy 2.x + Pydantic v2 on Python 3.12.
- Database assumptions: PostgreSQL primary, but approach remains SQLite-safe.
- Objective: introduce a shared layer so every list endpoint shares the same query grammar and response envelope without breaking existing semantics.
- Scope: users (global), workspace-scoped documents, jobs, configs.

## Repository Layout (Target)

```
apps/api/app/
  core/settings.py
  shared/
    types.py
    filters.py
    sorting.py
    pagination.py
    sql.py
  features/
    users/
      sorting.py
      filters.py
      routes.py
    documents/
      sorting.py
      filters.py
      routes.py
      ...
  shared/db.py
```

## Shared Query Contract

### Query Parameters Available Everywhere

- `page`: integer, 1-based, `>= 1`, default `1`.
- `page_size`: integer, default `25`, capped at `100`.
- `include_total`: boolean, default `false`.
- `sort`: comma-separated tokens, `-field` for descending; case-insensitive and trimmed.
- Resource filters:
  - Equality: `field=value`
  - Membership: `field_in=a,b,c` (CSV or repeated params)
  - Range: `field_from`, `field_to` using half-open `[from, to)`
  - Null checks: `field_is_null=true|false`
  - Text search: `q` with resource-specific semantics and bounded length

### Response Envelope (uniform on all list endpoints)

```json
{
  "items": [...],
  "page": 1,
  "page_size": 25,
  "has_previous": false,
  "has_next": true,
  "total": 42   // omitted when include_total=false (response_model_exclude_none=True)
}
```

## Sorting Rules

- Only whitelisted fields per resource accepted; unknown field -> 422 with allowed list.
- Tokens case-insensitive, duplicates removed while preserving order.
- If client omits PK, auto-append PK with direction matching first token to guarantee determinism.
- Allowed sorts documented in each resource’s dependency (description mentions example `-created_at,name`).
- Max `MAX_SORT_FIELDS = 3`.

## Pagination Rules

- Look-ahead strategy (`LIMIT page_size+1`) when `include_total=false` to compute `has_next`.
- Full `COUNT(*)` performed via subquery with `order_by(None)` when `include_total=true`.
- Out-of-range pages return 200 with empty `items` and `has_next=false`.
- `has_previous` equals `page > 1`.

## Filtering Rules

- All filter models inherit `FilterBase` with `extra="forbid"` to reject stray keys (422).
- `q` inputs trimmed and length-bounded (`MIN_SEARCH_LEN=2`, `MAX_SEARCH_LEN=128`).
- Range filters always half-open `[from, to)`.
- For joins that can duplicate rows (e.g., document tags) use `reselect_distinct_by_pk`.

## Shared Modules to Implement

### `core/settings.py`

```python
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_SORT_FIELDS = 3
MIN_SEARCH_LEN = 2
MAX_SEARCH_LEN = 128
```

### `shared/types.py`

```python
from typing import Any, Mapping, Tuple
from sqlalchemy.sql.elements import ColumnElement

OrderBy = Tuple[ColumnElement[Any], ...]
SortAllowedMap = Mapping[str, Tuple[ColumnElement[Any], ColumnElement[Any]]]
```

### `shared/filters.py`

```python
from pydantic import BaseModel

class FilterBase(BaseModel):
    model_config = {"extra": "forbid"}
```

### `shared/sql.py`

```python
from sqlalchemy import select

def reselect_distinct_by_pk(stmt, *, entity, pk_col):
    ids = stmt.with_only_columns(pk_col).distinct().order_by(None).subquery()
    return select(entity).join(ids, ids.c[pk_col.key] == pk_col)
```

### `shared/pagination.py`

Implements:

- `PageParams` (page, page_size, include_total)
- `Page` (envelope schema)
- `paginate_sql(...)`
- `paginate_sequence(...)`

See spec for full implementation including look-ahead + total logic.

### `shared/sorting.py`

Responsibilities:

- `_dedupe_preserve_order`
- `parse_sort`
- `resolve_sort`
- `make_sort_dependency`

Ensures token parsing, validation versus allowed map, enforcing PK tie-breaker, and generating FastAPI dependency with descriptive docstring.

## Resource-Level Specifications

### Users

- Table: `users`, PK `user_id`.
- Default sort `-created_at`, tie-breaker `user_id`.
- Allowed sort fields: `id`, `created_at`, `updated_at`, `email`, `display_name`, `last_login_at`.
- Filters:
  - `q` across `email` + `display_name`.
  - `is_active`, `is_service_account`.
  - `created_at_from/to`, `last_login_from/to`.
- Files:
  - `features/users/sorting.py` (constants per spec).
  - `features/users/filters.py` (model + `apply_user_filters`).

### Documents (workspace-scoped)

- Table: `documents`, PK `document_id`.
- Default sort `-created_at`, tie-breaker `document_id`.
- Allowed sort fields: `id`, `created_at`, `last_run_at`, `byte_size`, `original_filename`, `status`.
- Filters:
  - Path-scoped `workspace_id` (not part of filter model).
  - `status_in`, `source_in`, `uploaded_by_user_id`.
  - Date ranges on `created_at`, `last_run_at`.
  - `q` on `original_filename`.
  - Soft delete excluded unless `include_deleted=true`.
  - `tag_in` (join `document_tags` and dedupe).
  - `DocumentFilter` + `apply_document_filters` handle logic, including `reselect_distinct_by_pk`.

### Jobs (workspace-scoped)

- Table: `jobs`, PK `job_id`.
- Default sort `-created_at`, tie-breaker `job_id`.
- Allowed sort fields: `id`, `created_at`, `queued_at`, `started_at`, `completed_at`, `status`.
- Filters:
  - Path-scoped `workspace_id`.
  - `status_in`, `config_id`, `config_version_id`.
  - `submitted_by_user_id`, `trace_id`, `retry_of_job_id`.
  - `created_at_from/to`.

### Configs (workspace-scoped, soft-delete)

- Table: `configs`, PK `config_id`.
- Default sort `-created_at`, tie-breaker `config_id`.
- Allowed sort fields: `id`, `created_at`, `updated_at`, `slug`, `title`.
- Filters:
  - Path-scoped `workspace_id`.
  - `slug`, `title` (ILIKE), `created_by_user_id`.
  - `created_at_from/to`.
  - Soft delete excluded unless `include_deleted=true`.

## Route Pattern

Each feature module exposes a list endpoint following this template (example: documents):

```python
router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])

get_sort_order = make_sort_dependency(
    allowed=SORT_FIELDS,
    default=DEFAULT_SORT,
    id_field=ID_FIELD,
)

@router.get("/", response_model=Page[DocumentOut], response_model_exclude_none=True)
def list_documents(
    workspace_id: str,
    page: Annotated[PageParams, Depends()],
    order_by = Depends(get_sort_order),
    filters: Annotated[DocumentFilter, Depends()],
    session: Session = Depends(get_session),
):
    stmt = select(Document).where(Document.workspace_id == workspace_id)
    stmt = apply_document_filters(stmt, filters)
    return paginate_sql(
        session,
        stmt,
        page=page.page,
        page_size=page.page_size,
        order_by=order_by,
        include_total=page.include_total,
    )
```

Users route follows the same pattern without workspace scoping; other resources substitute their models, filters, and prefixes accordingly.

## Optional Index Alignment

- `documents (workspace_id, status, created_at DESC, document_id)`
- `documents (workspace_id, created_at DESC, document_id)`
- `jobs (workspace_id, created_at DESC, job_id)`
- `configs (workspace_id, created_at DESC, config_id)`
- Users already covered via `users (is_active, created_at, user_id)`.

## Acceptance Criteria

1. Uniform parameters and envelope for all list endpoints.
2. Sorting enforces whitelist, deduped tokens, PK tie-breaker, descriptive error on invalid fields.
3. Filters forbid unknown keys, obey length bounds, use half-open ranges, dedupe after joins.
4. Pagination logic provides accurate `has_next/has_previous`, honors `include_total`, and handles out-of-range pages gracefully.
5. Query plans remain stable/deterministic; subqueries clear ordering before counts.
6. Sort dependency descriptions enumerate allowed fields and include example `-created_at,name`.
7. Tests cover:
   - Sorting: multi-token support, unknown field rejection, PK tie-breaker.
   - Pagination: look-ahead behavior, out-of-range response.
   - Filtering: range semantics, membership filters, soft-delete defaults, tag join dedupe.

## Deliverables

- Shared helper modules implemented per spec.
- Sorting maps, filter models, and application logic for users, documents, jobs, configs.
- Routes wired to use shared pagination/sorting/filtering.
- Brief doc/readme snippet (this file) outlining grammar and envelope.
