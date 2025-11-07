# AGENT EXECUTION SPEC — Pagination, Sorting, Filtering (PSF)

**Stack**: FastAPI · SQLAlchemy 2.x (select/execute) · Pydantic v2 · Python 3.12
**DB**: PostgreSQL primary (must remain SQLite‑safe)
**Scope (this pass)**: `users` (global), `documents` (workspace‑scoped), `jobs` (workspace‑scoped), `configs` (workspace‑scoped)
**Goal**: Shared, **boringly‑standard** PSF layer used by all list endpoints. Uniform query grammar + response envelope. No breaking semantics.

---

## 0) High‑Level Rules (apply everywhere)

1. **Query params**

   * `page`: `int` ≥ 1, default 1
   * `page_size`: `int` with cap (default 25, max 100)
   * `include_total`: `bool`, default `false`
   * `sort`: CSV of tokens; `-field` = DESC, `field` = ASC; **case‑insensitive**, whitespace‑tolerant, duplicates removed; unknown field → **422** (list allowed fields)
   * Filters:

     * Equality: `field=value`
     * Membership: `field_in=a,b,c` (CSV or repeated params)
     * Range: `field_from`, `field_to` as **half‑open** `[from, to)` (works for `datetime` and numeric)
     * Null: `field_is_null=true|false`
     * Text search: `q` (trimmed; bounded length; simple `ILIKE`, resource‑specific)

2. **Sorting**

   * Only **whitelisted** fields per resource.
   * If client omits PK sort, **append PK** as deterministic tie‑breaker, using the **first** token’s direction.
   * PKs:

     * users: `user_id`
     * documents: `document_id`
     * jobs: `job_id`
     * configs: `config_id`

3. **Pagination**

   * If `include_total=false`: **look‑ahead** (`LIMIT page_size+1`) to compute `has_next`.
   * If `include_total=true`: `COUNT(*)` over a **subquery** with `order_by(None)`.
   * Out‑of‑range page: return `200` with `items: []`, `has_next: false`.

4. **Filtering**

   * All filter models inherit `FilterBase` with `extra="forbid"` (unknown keys → **422**).
   * `q` length limits apply globally; ranges are always `[from, to)` (exclusive upper bound).
   * If filters introduce 1..many joins (e.g., tags), dedupe using **reselect‑by‑PK**.

5. **Response envelope** (always, no header mode)

```json
{
  "items": [...],
  "page": 1,
  "page_size": 25,
  "has_previous": false,
  "has_next": true,
  "total": 42  // present only when include_total=true (use response_model_exclude_none=True)
}
```

---

## 1) Repository Layout (target)

```
apps/api/app/
  settings.py
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
    jobs/
      sorting.py
      filters.py
      routes.py
    configs/
      sorting.py
      filters.py
      routes.py
  shared/db.py
```

---

## 2) Implement Shared Modules (exact content)

### 2.1 `settings.py`

```python
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_SORT_FIELDS = 3
MIN_SEARCH_LEN = 2
MAX_SEARCH_LEN = 128
```

### 2.2 `shared/types.py`

```python
from typing import Any, Mapping, Tuple
from sqlalchemy.sql.elements import ColumnElement

OrderBy = Tuple[ColumnElement[Any], ...]
SortAllowedMap = Mapping[str, Tuple[ColumnElement[Any], ColumnElement[Any]]]
```

### 2.3 `shared/filters.py`

```python
from pydantic import BaseModel

class FilterBase(BaseModel):
    model_config = {"extra": "forbid"}  # reject unknown query keys
```

### 2.4 `shared/sql.py`

```python
from sqlalchemy import select

def reselect_distinct_by_pk(stmt, *, entity, pk_col):
    """
    For 1..many joins that may duplicate rows: select distinct IDs, then reselect by PK.
    Clears ordering for the planner.
    """
    ids = stmt.with_only_columns(pk_col).distinct().order_by(None).subquery()
    return select(entity).join(ids, ids.c[pk_col.key] == pk_col)
```

### 2.5 `shared/pagination.py`

```python
from typing import Generic, Sequence, TypeVar, Optional, Any, Sequence as Seq
from pydantic import BaseModel, Field, conint
from sqlalchemy import func, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm import Session
from itertools import islice
from apps.api.app.settings import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar("T")

class PageParams(BaseModel):
    page: conint(ge=1) = Field(1, description="1-based page number")
    page_size: conint(ge=1, le=MAX_PAGE_SIZE) = Field(
        DEFAULT_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})"
    )
    include_total: bool = Field(False, description="Include total item count")

class Page(BaseModel, Generic[T]):
    items: Sequence[T]
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
    total: Optional[int] = None  # omitted when response_model_exclude_none=True

def paginate_sql(
    session: Session,
    stmt: Select,                                  # filtered; not ordered
    *,
    page: int,
    page_size: int,
    order_by: Seq[ColumnElement[Any]],
    include_total: bool = False,
) -> Page[T]:
    offset = (page - 1) * page_size
    stmt = stmt.order_by(*order_by)

    if include_total:
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = session.execute(count_stmt).scalar_one()
        items = session.execute(stmt.limit(page_size).offset(offset)).scalars().all()
        has_next = (page * page_size) < total
    else:
        rows = session.execute(stmt.limit(page_size + 1).offset(offset)).scalars().all()
        has_next = len(rows) > page_size
        items = rows[:page_size]
        total = None

    return Page(
        items=items,
        page=page,
        page_size=page_size,
        has_next=has_next,
        has_previous=page > 1,
        total=total,
    )

def paginate_sequence(iterable, *, page: int, page_size: int, include_total: bool = False) -> Page[T]:
    start = (page - 1) * page_size
    if include_total:
        data = list(iterable)
        total = len(data)
        items = data[start:start + page_size]
        has_next = start + page_size < total
    else:
        window = list(islice(iterable, start, start + page_size + 1))
        has_next = len(window) > page_size
        items = window[:page_size]
        total = None

    return Page(
        items=items,
        page=page,
        page_size=page_size,
        has_next=has_next,
        has_previous=page > 1,
        total=total,
    )
```

### 2.6 `shared/sorting.py`

```python
from typing import Iterable, Sequence, Any
from fastapi import Query, HTTPException
from sqlalchemy.sql.elements import ColumnElement
from apps.api.app.settings import MAX_SORT_FIELDS
from apps.api.app.shared.types import OrderBy, SortAllowedMap

def _dedupe_preserve_order(tokens: list[str]) -> list[str]:
    seen, out = set(), []
    for t in tokens:
        if t not in seen:
            seen.add(t); out.append(t)
    return out

def parse_sort(raw: str | None) -> list[str]:
    if not raw:
        return []
    # normalize: trim, lower-case names; preserve leading '-'
    tokens = []
    for t in raw.split(","):
        t = t.strip()
        if not t:
            continue
        desc = t.startswith("-")
        name = (t[1:] if desc else t).strip().lower()
        tokens.append(f"-{name}" if desc else name)
    tokens = _dedupe_preserve_order(tokens)
    if len(tokens) > MAX_SORT_FIELDS:
        raise HTTPException(status_code=422, detail=f"Too many sort fields (max {MAX_SORT_FIELDS}).")
    return tokens

def resolve_sort(
    tokens: Iterable[str],
    *,
    allowed: SortAllowedMap,                                   # field -> (asc, desc)
    default: Sequence[str],
    id_field: tuple[ColumnElement[Any], ColumnElement[Any]],
) -> OrderBy:
    tokens = list(tokens) or list(default)
    if not tokens:
        raise HTTPException(status_code=422, detail="No sort tokens provided.")

    order: list[ColumnElement[Any]] = []
    first_desc = None
    names: list[str] = []

    for tok in tokens:
        desc = tok.startswith("-")
        name = tok[1:] if desc else tok
        names.append(name)
        cols = allowed.get(name)
        if cols is None:
            allowed_list = ", ".join(sorted(allowed.keys()))
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported sort field '{name}'. Allowed: {allowed_list}",
            )
        order.append(cols[1] if desc else cols[0])
        if first_desc is None:
            first_desc = desc

    # deterministic PK tie-breaker if 'id' not explicitly used
    if "id" not in names:
        order.append(id_field[1] if first_desc else id_field[0])

    return tuple(order)

def make_sort_dependency(
    *,
    allowed: SortAllowedMap,
    default: Sequence[str],
    id_field: tuple[ColumnElement[Any], ColumnElement[Any]],
):
    doc = "CSV; prefix with '-' for DESC. Allowed: " + ", ".join(sorted(allowed.keys())) + ". Example: -created_at,name"
    def dep(sort: str | None = Query(None, description=doc)) -> OrderBy:
        return resolve_sort(parse_sort(sort), allowed=allowed, default=default, id_field=id_field)
    return dep
```

---

## 3) Resource‑Level Specs (exact mappings)

> Use SQLAlchemy models already present under each feature. **No schema changes**.

### 3.1 Users (table `users`; PK `user_id`)

* **Default sort**: `-created_at` (tie‑breaker `user_id`)
* **ALLOWED sorts**:

  * `id` → `User.user_id`
  * `created_at` → `User.created_at`
  * `updated_at` → `User.updated_at`
  * `email` → `User.email_canonical`
  * `display_name` → `User.display_name` (use `.nulls_last()` in Postgres)
  * `last_login_at` → `User.last_login_at` (use `.nulls_last()`)
* **Filters**:

  * `q` over `User.email` + `User.display_name` (ILIKE; length `[2,128]`)
  * `is_active: bool`
  * `is_service_account: bool`
  * `created_at_from/to` (half‑open)
  * `last_login_from/to` (half‑open)

### 3.2 Documents (table `documents`; PK `document_id`; path‑scoped by `workspace_id`)

* **Default sort**: `-created_at` (tie‑breaker `document_id`)
* **ALLOWED sorts**:

  * `id` → `Document.document_id`
  * `created_at` → `Document.created_at`
  * `last_run_at` → `Document.last_run_at` (use `.nulls_last()`)
  * `byte_size` → `Document.byte_size`
  * `original_filename` → `Document.original_filename`
  * `status` → `Document.status`
* **Filters**:

  * `status_in: set[documentstatus]`
  * `source_in: set[documentsource]`
  * `uploaded_by_user_id: str`
  * `created_at_from/to`, `last_run_from/to` (half‑open)
  * `q` over `original_filename` (ILIKE; length `[2,128]`)
  * Soft delete excluded by default (`deleted_at IS NULL`); `include_deleted: bool` to include
  * `tag_in: set[str]` via join to `document_tags`, then **reselect by PK**

### 3.3 Jobs (table `jobs`; PK `job_id`; path‑scoped by `workspace_id`)

* **Default sort**: `-created_at` (tie‑breaker `job_id`)
* **ALLOWED sorts**:

  * `id` → `Job.job_id`
  * `created_at` → `Job.created_at`
  * `queued_at` → `Job.queued_at`
  * `started_at` → `Job.started_at` (use `.nulls_last()`)
  * `completed_at` → `Job.completed_at` (use `.nulls_last()`)
  * `status` → `Job.status`
* **Filters**:

  * `status_in: set[jobstatus]`
  * `config_id`, `config_version_id`
  * `submitted_by_user_id`, `trace_id`, `retry_of_job_id`
  * `created_at_from/to` (half‑open)

### 3.4 Configs (table `configs`; PK `config_id`; path‑scoped by `workspace_id`)

* **Default sort**: `-created_at` (tie‑breaker `config_id`)
* **ALLOWED sorts**:

  * `id` → `Config.config_id`
  * `created_at` → `Config.created_at`
  * `updated_at` → `Config.updated_at`
  * `slug` → `Config.slug`
  * `title` → `Config.title`
* **Filters**:

  * `slug: str` (exact)
  * `title: str` (ILIKE partial)
  * `created_by_user_id: str`
  * `created_at_from/to` (half‑open)
  * Soft delete excluded by default (`deleted_at IS NULL`); `include_deleted: bool` to include

---

## 4) Resource Files (create/update)

> For each resource: `sorting.py`, `filters.py`, `routes.py`.

### 4.1 Sorting files (example: `features/users/sorting.py`)

```python
from .models import User

SORT_FIELDS = {
    "id": (User.user_id.asc(), User.user_id.desc()),
    "created_at": (User.created_at.asc(), User.created_at.desc()),
    "updated_at": (User.updated_at.asc(), User.updated_at.desc()),
    "email": (User.email_canonical.asc(), User.email_canonical.desc()),
    "display_name": (User.display_name.asc().nulls_last(), User.display_name.desc().nulls_last()),
    "last_login_at": (User.last_login_at.asc().nulls_last(), User.last_login_at.desc().nulls_last()),
}
DEFAULT_SORT = ["-created_at"]
ID_FIELD = (User.user_id.asc(), User.user_id.desc())
```

(Implement analogous maps for `documents`, `jobs`, `configs` using the field mappings in §3.)

### 4.2 Filter files (example: `features/users/filters.py`)

```python
from typing import Optional
from datetime import datetime
from pydantic import Field
from sqlalchemy import and_, or_
from apps.api.app.shared.filters import FilterBase
from .models import User
from apps.api.app.settings import MIN_SEARCH_LEN, MAX_SEARCH_LEN

class UserFilter(FilterBase):
    q: Optional[str] = Field(None, description="Search email/display_name",
                             min_length=MIN_SEARCH_LEN, max_length=MAX_SEARCH_LEN)
    is_active: Optional[bool] = None
    is_service_account: Optional[bool] = None
    created_at_from: Optional[datetime] = None
    created_at_to: Optional[datetime] = None
    last_login_from: Optional[datetime] = None
    last_login_to: Optional[datetime] = None

def apply_user_filters(stmt, f: "UserFilter"):
    preds = []
    if f.q:
        like = f"%{f.q.strip()}%"
        preds.append(or_(User.email.ilike(like), User.display_name.ilike(like)))
    if f.is_active is not None:
        preds.append(User.is_active.is_(f.is_active))
    if f.is_service_account is not None:
        preds.append(User.is_service_account.is_(f.is_service_account))
    if f.created_at_from: preds.append(User.created_at >= f.created_at_from)
    if f.created_at_to:   preds.append(User.created_at <  f.created_at_to)
    if f.last_login_from: preds.append(User.last_login_at >= f.last_login_from)
    if f.last_login_to:   preds.append(User.last_login_at <  f.last_login_to)
    return stmt.where(and_(*preds)) if preds else stmt
```

(Implement `DocumentFilter`, `JobFilter`, `ConfigFilter` per §3.2–§3.4, including tag join + PK reselect for documents.)

### 4.3 Routes (example pattern: documents)

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from apps.api.app.shared.db import get_session
from apps.api.app.shared.pagination import Page, PageParams, paginate_sql
from apps.api.app.shared.sorting import make_sort_dependency
from .sorting import SORT_FIELDS, DEFAULT_SORT, ID_FIELD
from .filters import DocumentFilter, apply_document_filters
from .models import Document
from .schemas import DocumentOut

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
    order_by = Depends(get_sort_order),          # includes PK tie-breaker
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

(Replicate this for `users`, `jobs`, `configs`—`users` has no workspace path param; others are under `/workspaces/{workspace_id}/...`.)

---

## 5) API/Docs UX (subtle improvements)

* Add `description` on `PageParams` fields and filter fields so Swagger shows helpful help text.
* Keep `sort` as a free‑form CSV (to avoid a breaking change). Optionally add a note in the dependency docstring with an example (`-created_at,name`).
* Use `response_model_exclude_none=True` on list handlers so `total` is omitted unless requested.

---

## 6) Tests (minimal but sufficient)

Create tests covering:

1. **Sorting**

   * Accepts multiple tokens; trims/normalizes; dedupes.
   * Unknown field → 422 with allowed list in message.
   * PK tie‑breaker appended when not supplied (verify deterministic order on ties).

2. **Pagination**

   * `include_total=false`: look‑ahead sets `has_next` correctly at page boundaries.
   * `include_total=true`: count returned; `has_next` based on total.
   * Out‑of‑range page returns 200 + empty `items`.

3. **Filtering**

   * Half‑open ranges exclude the `to` boundary.
   * `q` obeys length bounds; trimmed.
   * `*_in` membership filters accept CSV list.
   * Documents: `tag_in` join dedupes rows (no duplicates in `items`).
   * Soft delete default behavior (`deleted_at IS NULL` when not `include_deleted`).

---

## 7) Operational Notes (index alignment; no code changes required)

* Existing indexes already align with defaults:

  * users: `(is_active, created_at, user_id)`
  * documents: `(workspace_id, status, created_at)`, `(workspace_id, created_at)`, `(workspace_id, last_run_at)`
  * jobs: `(workspace_id, status, created_at)`, `(status, queued_at)`
  * configs: `(workspace_id)` (+ sort on `created_at`)
* For deep feeds later: add keyset pagination separately (out of scope for this pass).

---

## 8) Acceptance Criteria (must satisfy)

* Uniform params & envelope on all list endpoints.
* Sorting: whitelist‑only; case‑insensitive; 422 on unknown; **PK tie‑breaker** present when omitted.
* Filtering: `extra="forbid"`, half‑open ranges, `q` bounded, join dedupe where needed.
* Pagination: look‑ahead vs. count implemented; correct `has_next`/`has_previous`.
* Stable ordering guaranteed; counts computed via subquery with `order_by(None)`.
* Swagger shows all query params with descriptions; `sort` dependency doc lists allowed fields + example.
* Tests for sorting, pagination, filtering pass.

---

### Implementation Order (for the agent)

1. Create shared modules (§2.1–§2.6).
2. Implement `users` feature (sorting/filter/routes).
3. Implement `documents` feature (incl. tag join dedupe).
4. Implement `jobs` feature.
5. Implement `configs` feature.
6. Wire routes; ensure `response_model_exclude_none=True`.
7. Add tests (§6).
8. Verify Swagger shows params & envelope; run tests.