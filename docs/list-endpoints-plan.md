Below is a clean, “boringly standard” **work plan** you can hand to an AI agent to implement **pagination, sorting, and filtering** across your FastAPI + SQLAlchemy (async) + Pydantic v2 backend. It uses common names and patterns that are widely understood, efficient, and easy to maintain.

---

# Pagination · Sorting · Filtering (PSF) — Implementation Plan

## 1) Objectives

* Provide a **uniform query grammar** and **single response envelope** for all list endpoints.
* Keep the implementation **async**, **deterministic**, and **index‑friendly**.
* Minimize surprises: predictable defaults, clear errors, and stable ordering.

---

## 2) Design Principles

* **Common naming**: `page`, `page_size`, `include_total`, `sort`, `q`, `<field>_in`, `<field>_from`, `<field>_to`, `<field>_is_null`.
* **Offset pagination** by default (page/size) with optional `COUNT` (for totals).
* **Stable sorting**: whitelisted fields only; always append a **PK tie‑breaker**.
* **Half‑open ranges**: `[from, to)` everywhere.
* **Async all the way**: use `AsyncSession` and `await` DB I/O.
* **Swagger‑friendly**: params modeled with Pydantic; descriptions on fields.
* **Performance aware**: use look‑ahead, clear orderings in subqueries, avoid duplicate rows after joins.

---

## 3) API Contract

### 3.1 Query Parameters (available on every list endpoint)

* `page` — integer ≥ 1 (default: `1`)
* `page_size` — integer (default: `25`, cap: `100`)
* `include_total` — boolean (default: `false`)
* `sort` — CSV of field tokens; `-field` means DESC, `field` means ASC

  * **Case‑insensitive**, tokens **deduped**, **whitelist enforced**
* **Filters (per resource)**:

  * Equality: `field=value`
  * Membership: `field_in=a,b,c` **or** `field_in=a&field_in=b` (CSV or repeated)
  * Ranges: `field_from`, `field_to` (both datetimes normalized to **UTC**; upper bound **exclusive**)
  * Null checks: `field_is_null=true|false`
  * Text search: `q` (trimmed, length‑bounded)

### 3.2 Response Envelope (always the same)

```json
{
  "items": [...],
  "page": 1,
  "page_size": 25,
  "has_previous": false,
  "has_next": true,
  "total": 42   // present only when include_total=true
}
```

### 3.3 Sorting Rules

* Only **whitelisted** fields are accepted per resource; unknown ⇒ HTTP 422 (list allowed fields).
* Tokens are case‑insensitive and whitespace‑tolerant; duplicates removed.
* If the client does not sort by the resource’s **primary key**, append the **PK** as a final order column using the **first sort token’s direction**.
  (e.g., users → `user_id`, documents → `document_id`, jobs → `job_id`, configs → `config_id`)
* For nullable sort columns, prefer **NULLS LAST** (Postgres). On other DBs, no‑op gracefully.

### 3.4 Pagination Rules

* When `include_total=false`: use **look‑ahead** (`LIMIT page_size+1`) to compute `has_next`; do **not** run `COUNT`.
* When `include_total=true`: run `COUNT(*)` via a **subquery** with `order_by(None)` (planner‑friendly).
* Out‑of‑range pages return **200** with `items: []` and `has_next: false`.

### 3.5 Filtering Rules

* All filter models inherit a base with `extra="forbid"` to **reject unknown keys** (422).
* `*_in` fields accept **CSV or repeated** query params; enforce a **small cap** (e.g., ≤ 50 values).
* Normalize datetimes to **UTC**; treat naive datetimes as UTC.
* If filters require 1..many joins (e.g., tags), **dedupe** the result by reselecting distinct PKs **before pagination**.

---

## 4) Repository Layout

```
apps/api/app/
  settings.py
  shared/
    types.py
    filters.py
    validators.py
    sorting.py
    pagination.py
    sql.py
  features/
    <resource>/
      sorting.py
      filters.py
      routes.py
  shared/db.py   # AsyncSession dependency
```

---

## 5) Shared Modules — Responsibilities & Skeletons

### 5.1 Settings

```python
# apps/api/app/settings.py
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_SORT_FIELDS = 3
MIN_SEARCH_LEN = 2
MAX_SEARCH_LEN = 128
MAX_SET_SIZE = 50                  # cap for *_in lists
COUNT_STATEMENT_TIMEOUT_MS = None  # optional (Postgres), e.g., 500
```

### 5.2 Types

```python
# apps/api/app/shared/types.py
from typing import Any, Mapping, Tuple
from sqlalchemy.sql.elements import ColumnElement

OrderBy = Tuple[ColumnElement[Any], ...]
SortAllowedMap = Mapping[str, Tuple[ColumnElement[Any], ColumnElement[Any]]]
```

### 5.3 Filter Base & Validators

```python
# apps/api/app/shared/filters.py
from pydantic import BaseModel
class FilterBase(BaseModel):
    model_config = {"extra": "forbid"}  # reject unknown query keys
```

```python
# apps/api/app/shared/validators.py
from typing import Iterable, Optional, Set
from datetime import datetime, timezone

def parse_csv_or_repeated(value) -> Optional[Set[str]]:
    if value is None: return None
    if isinstance(value, str):
        return {p.strip() for p in value.split(",") if p.strip()}
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        out: Set[str] = set()
        for item in value:
            if isinstance(item, str):
                out.update(p.strip() for p in item.split(",") if p.strip())
            else:
                out.add(str(item))
        return out or None
    return {str(value)}

def normalize_utc(dt: datetime | None) -> datetime | None:
    if dt is None: return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
```

### 5.4 Sorting

```python
# apps/api/app/shared/sorting.py
from typing import Iterable, Sequence, Any
from fastapi import Query, HTTPException
from apps.api.app.settings import MAX_SORT_FIELDS
from apps.api.app.shared.types import OrderBy, SortAllowedMap

def _dedupe_preserve_order(tokens: list[str]) -> list[str]:
    seen, out = set(), []
    for t in tokens:
        if t not in seen:
            seen.add(t); out.append(t)
    return out

def parse_sort(raw: str | None) -> list[str]:
    if not raw: return []
    tokens = []
    for t in raw.split(","):
        t = t.strip()
        if not t: continue
        neg = t.startswith("-")
        name = (t[1:] if neg else t).strip().lower()
        tokens.append(f"-{name}" if neg else name)
    tokens = _dedupe_preserve_order(tokens)
    if len(tokens) > MAX_SORT_FIELDS:
        raise HTTPException(422, f"Too many sort fields (max {MAX_SORT_FIELDS}).")
    return tokens

def resolve_sort(
    tokens: Iterable[str],
    *,
    allowed: SortAllowedMap,  # field -> (asc, desc)
    default: Sequence[str],
    id_field,                  # (id.asc(), id.desc())
) -> OrderBy:
    tokens = list(tokens) or list(default)
    if not tokens:
        raise HTTPException(422, "No sort tokens provided.")
    order, first_desc, names = [], None, []
    for tok in tokens:
        desc = tok.startswith("-"); name = tok[1:] if desc else tok
        names.append(name)
        cols = allowed.get(name)
        if cols is None:
            allowed_list = ", ".join(sorted(allowed.keys()))
            raise HTTPException(422, f"Unsupported sort field '{name}'. Allowed: {allowed_list}")
        order.append(cols[1] if desc else cols[0])
        if first_desc is None: first_desc = desc
    if "id" not in names:  # PK tie-breaker
        order.append(id_field[1] if first_desc else id_field[0])
    return tuple(order)

def make_sort_dependency(*, allowed: SortAllowedMap, default: Sequence[str], id_field):
    doc = "CSV; prefix '-' for DESC. Allowed: " + ", ".join(sorted(allowed.keys())) + ". Example: -created_at,name"
    def dep(sort: str | None = Query(None, description=doc)) -> OrderBy:
        return resolve_sort(parse_sort(sort), allowed=allowed, default=default, id_field=id_field)
    return dep
```

### 5.5 SQL Utilities

```python
# apps/api/app/shared/sql.py
from sqlalchemy import select
def reselect_distinct_by_pk(stmt, *, entity, pk_col):
    ids = stmt.with_only_columns(pk_col).distinct().order_by(None).subquery()
    return select(entity).join(ids, ids.c[pk_col.key] == pk_col)

def nulls_last(ordering):  # Postgres adds .nulls_last(); others ignore
    try: return ordering.nulls_last()
    except AttributeError: return ordering
```

### 5.6 Pagination (Async)

```python
# apps/api/app/shared/pagination.py
from typing import Generic, Sequence, TypeVar, Optional, Any, Sequence as Seq
from pydantic import BaseModel, Field, conint
from sqlalchemy import func, select, text
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from itertools import islice
from apps.api.app.settings import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, COUNT_STATEMENT_TIMEOUT_MS

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
    total: Optional[int] = None

async def paginate_sql(
    session: AsyncSession,
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
        if COUNT_STATEMENT_TIMEOUT_MS and session.bind and session.bind.dialect.name == "postgresql":
            await session.execute(text(f"SET LOCAL statement_timeout = {int(COUNT_STATEMENT_TIMEOUT_MS)}"))
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = (await session.execute(count_stmt)).scalar_one()
        items = (await session.execute(stmt.limit(page_size).offset(offset))).scalars().all()
        has_next = (page * page_size) < total
    else:
        rows = (await session.execute(stmt.limit(page_size + 1).offset(offset))).scalars().all()
        has_next = len(rows) > page_size
        items = rows[:page_size]
        total = None

    return Page(items=items, page=page, page_size=page_size,
                has_next=has_next, has_previous=page > 1, total=total)

# Optional in-memory variant (unchanged)
def paginate_sequence(iterable, *, page: int, page_size: int, include_total: bool = False) -> Page[T]:
    start = (page - 1) * page_size
    if include_total:
        data = list(iterable); total = len(data)
        items = data[start:start + page_size]; has_next = start + page_size < total
        total_val = total
    else:
        window = list(islice(iterable, start, start + page_size + 1))
        has_next = len(window) > page_size; items = window[:page_size]; total_val = None
    return Page(items=items, page=page, page_size=page_size,
                has_next=has_next, has_previous=page > 1, total=total_val)
```

---

## 6) Resource Integration Pattern

For **each resource**, create:

* `sorting.py` — declare `SORT_FIELDS`, `DEFAULT_SORT`, `ID_FIELD` (asc/desc callables).
* `filters.py` — Pydantic model + `apply_<resource>_filters(stmt, filters)` that builds predicates and handles joins/dedupe.
* `routes.py` — thin route using dependencies and the shared paginator.

### 6.1 Sorting (example skeleton)

```python
# apps/api/app/features/<resource>/sorting.py
from apps.api.app.shared.sql import nulls_last
from .models import ResourceModel as M

SORT_FIELDS = {
    "id": (M.pk.asc(), M.pk.desc()),
    "created_at": (M.created_at.asc(), M.created_at.desc()),
    # add more; wrap nullable cols with nulls_last(...)
    # "name": (nulls_last(M.name.asc()), nulls_last(M.name.desc())),
}
DEFAULT_SORT = ["-created_at"]
ID_FIELD = (M.pk.asc(), M.pk.desc())
```

### 6.2 Filters (example skeleton)

```python
# apps/api/app/features/<resource>/filters.py
from typing import Optional, Set
from datetime import datetime
from pydantic import Field, field_validator
from sqlalchemy import and_
from apps.api.app.shared.filters import FilterBase
from apps.api.app.shared.validators import parse_csv_or_repeated, normalize_utc
from apps.api.app.settings import MIN_SEARCH_LEN, MAX_SEARCH_LEN, MAX_SET_SIZE
from .models import ResourceModel as M

class ResourceFilter(FilterBase):
    q: Optional[str] = Field(None, description="Free text search", min_length=MIN_SEARCH_LEN, max_length=MAX_SEARCH_LEN)
    created_at_from: Optional[datetime] = None
    created_at_to: Optional[datetime] = None
    # membership filters:
    tags_in: Optional[Set[str]] = None

    @field_validator("tags_in", mode="before")
    @classmethod
    def _csv(cls, v):
        s = parse_csv_or_repeated(v)
        if s and len(s) > MAX_SET_SIZE:
            from fastapi import HTTPException
            raise HTTPException(422, f"Too many values; max {MAX_SET_SIZE}.")
        return s

    @field_validator("created_at_from", "created_at_to", mode="before")
    @classmethod
    def _utc(cls, v): return normalize_utc(v)

def apply_resource_filters(stmt, f: "ResourceFilter"):
    preds = []
    if f.q:
        like = f"%{f.q.strip()}%"
        # preds.append(or_(M.name.ilike(like), M.slug.ilike(like)))
    if f.created_at_from: preds.append(M.created_at >= f.created_at_from)
    if f.created_at_to:   preds.append(M.created_at <  f.created_at_to)

    # handle joins if needed; then dedupe via reselect_distinct_by_pk(...)
    return stmt.where(and_(*preds)) if preds else stmt
```

### 6.3 Route (async)

```python
# apps/api/app/features/<resource>/routes.py
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.shared.db import get_session
from apps.api.app.shared.pagination import Page, PageParams, paginate_sql
from apps.api.app.shared.sorting import make_sort_dependency
from .sorting import SORT_FIELDS, DEFAULT_SORT, ID_FIELD
from .filters import ResourceFilter, apply_resource_filters
from .models import ResourceModel as M
from .schemas import ResourceOut

router = APIRouter(prefix="/resources", tags=["resources"])

get_sort_order = make_sort_dependency(allowed=SORT_FIELDS, default=DEFAULT_SORT, id_field=ID_FIELD)

@router.get("/", response_model=Page[ResourceOut], response_model_exclude_none=True)
async def list_resources(
    page: Annotated[PageParams, Depends()],
    order_by = Depends(get_sort_order),
    filters: Annotated[ResourceFilter, Depends()],
    session: AsyncSession = Depends(get_session),
):
    stmt = select(M)
    stmt = apply_resource_filters(stmt, filters)
    return await paginate_sql(
        session, stmt,
        page=page.page, page_size=page.page_size,
        order_by=order_by, include_total=page.include_total
    )
```

> For workspace‑scoped resources, add `workspace_id` to the route prefix and `where(M.workspace_id == workspace_id)` before filters.

---

## 7) Error Handling & Docs

* **422** for:

  * Unknown sort fields (message lists allowed fields).
  * Too many sort tokens (> `MAX_SORT_FIELDS`).
  * Unknown filter keys (thanks to `extra="forbid"`).
  * Oversized membership lists (> `MAX_SET_SIZE`).
* Add `description=` to `PageParams` and filter model fields so Swagger is descriptive.
* The `sort` dependency description should list **allowed fields** and show an example `-created_at,name`.

---

## 8) Performance Notes

* Ensure DB indexes cover:

  * Default sort combinations (`created_at` + PK).
  * High‑frequency filter keys (e.g., `status`, `workspace_id`).
* COUNT subqueries must call `.order_by(None)` to avoid planner overhead.
* Always append PK tie‑breaker for stable pagination under concurrent writes.
* For very large datasets or infinite scroll, consider **keyset (cursor) pagination** later (out of scope for this pass).

---

## 9) Test Plan (async)

* **Sorting**

  * Accepts multiple tokens; case‑insensitive; duplicates removed.
  * Unknown field ⇒ 422 with list of allowed fields.
  * PK tie‑breaker applied when not specified (deterministic ordering on ties).
* **Pagination**

  * `include_total=false`: look‑ahead sets `has_next` correctly at page boundaries.
  * `include_total=true`: returns correct `total`; `has_next` derived from total.
  * Out‑of‑range page returns 200 with empty `items`.
* **Filtering**

  * `q` bounds and trim applied.
  * `*_from/*_to` behave as **[from, to)** and normalize to UTC.
  * `*_in` supports CSV and repeated params; cap enforced (422 on overflow).
  * Join‑based filters (if any) do not produce duplicates (reselect‑by‑PK).
* **Docs**

  * Swagger shows all query params with descriptions; `total` omitted unless requested.

---

## 10) Definition of Done (DoD)

* All list endpoints accept the **same** params and return the **same** envelope.
* Shared modules exist and are reused across resources.
* Sorting, filtering, and pagination behave as specified; errors are clear and consistent.
* Tests for sorting, pagination, and filtering pass under async execution.
* Swagger UI shows clean, typed, documented parameters; `response_model_exclude_none=True` is used.

---

## 11) Implementation Order (for the agent)

1. Create shared modules: `settings.py`, `types.py`, `filters.py`, `validators.py`, `sql.py`, `sorting.py`, `pagination.py`.
2. Ensure `get_session` yields an **AsyncSession** and routes are `async def`.
3. For each resource:

   * Add `sorting.py` (allowed fields, defaults, PK pair).
   * Add `filters.py` (model + `apply_..._filters`).
   * Add `routes.py` (thin orchestration) with `response_model=Page[T]`.
4. Add/extend async tests as per the test plan.
5. Verify Swagger shows the parameters and the envelope as expected.

---

### Notes

* **Keep it simple**: CSV `sort` is common and flexible; Enums can be added later for clickable dropdowns.
* **Stay consistent**: same grammar, same envelope, same error semantics across all endpoints.
* **Be safe**: cap list sizes, normalize datetimes, and keep ordering stable with a PK tie‑breaker.

This plan is intentionally straightforward and idiomatic—easy for an AI agent to implement and for your team to maintain.
