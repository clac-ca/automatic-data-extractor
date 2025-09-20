# CURRENT\_TASK.md — OpenAPI Contract & Docs Execution Plan

## Goal

Ship a **clean, correct OpenAPI 3.1** for the ADE backend that:

* Documents **auth** (HTTP Basic and Bearer) and session semantics.
* Standardizes **errors** on **Problem Details** (RFC **9457**, which **obsoletes** RFC 7807). ([RFC Editor][1])
* Unifies **pagination** and list responses; documents sorting/filters.
* Fixes **status code semantics** (e.g., `201 Location`, `405 Allow`). ([RFC Editor][2])
* Adds high‑quality **schemas, examples, tags, and operationIds**.
* Installs **lint + diff** gates to keep the contract stable. ([Stoplight][3])

> We will not change core runtime logic beyond envelope/metadata alignment; the focus is on contract, documentation, and thin glue code.

---
## Work Items (in the order to implement)

### 1) Centralized OpenAPI builder (FastAPI)

**Files:** `backend/app/api/openapi.py`, `backend/app/main.py`
**What to do**

* Implement `build_openapi(app)`: call `fastapi.openapi.utils.get_openapi()`, then inject:

  * **info** (title/description/contact/license), **servers**, **tags** (with descriptions), **externalDocs**.
  * `components.securitySchemes` for **basic** + **bearer**.
  * `components.responses` for common errors (all reference **Problem Details** schema).
  * `components.parameters` for shared `limit` and `offset`, plus common filter params.
  * **examples** for success and errors.
* Cache with `app.openapi_schema` and assign `app.openapi = build_openapi(app)` (on startup).
  **Why:** FastAPI supports overriding the generated schema cleanly. ([FastAPI][4])
  **OpenAPI 3.1 note:** 3.1 aligns with JSON Schema 2020‑12—use it to improve schema fidelity. ([Swagger][5])
  **Acceptance**
* `GET /openapi.json` includes `info`, `servers`, curated `tags`, `components.securitySchemes`, reusable `responses/parameters`, and `examples`.

**Skeleton**

```py
# backend/app/api/openapi.py
from fastapi.openapi.utils import get_openapi

def build_openapi(app):
    if getattr(app, "openapi_schema", None):
        return app.openapi_schema
    doc = get_openapi(
        title="ADE API",
        version="1.0.0",
        description="Authenticated endpoints for configurations, documents, jobs, and events.",
        routes=app.routes,
    )
    # Inject servers, tags, components, examples…
    doc["servers"] = [{"url": "https://api.example.com"}]  # add dev/staging as needed
    doc.setdefault("tags", [
        {"name": "health", "description": "Service readiness and liveness"},
        {"name": "auth", "description": "Authentication and session lifecycle"},
        {"name": "configurations", "description": "Document configuration versions"},
        {"name": "documents", "description": "Document ingestion and retrieval"},
        {"name": "jobs", "description": "Extraction job orchestration"},
        {"name": "events", "description": "Audit timeline and history"},
    ])
    doc.setdefault("components", {}).setdefault("securitySchemes", {
        "basicAuth": {"type": "http", "scheme": "basic"},
        "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
    })
    # Add components.responses, components.parameters, schemas, examples…
    app.openapi_schema = doc
    return app.openapi_schema
```

---

### 2) Security: document Basic + Bearer, set global requirements

**Files:** `backend/app/api/openapi.py`, router decorators
**What to do**

* Set global OpenAPI `security` to **either** Basic **or** Bearer:

  ```json
  "security": [{"basicAuth": []}, {"bearerAuth": []}]
  ```
* For **public** `/health`, override via `openapi_extra={"security": []}`.
* Ensure descriptions mention `WWW-Authenticate` challenges.
  **Why:** Correctly publishing Basic (RFC 7617) and Bearer (RFC 6750) and their `WWW-Authenticate` hints is standard practice. ([IETF Datatracker][6])
  **Acceptance**
* Swagger UI shows lock icons for protected routes; `/health` shows none.

---

### 3) Standardize errors on **Problem Details** (RFC 9457)

**Files:** `backend/app/api/errors.py`, update all routers to use it
**What to do**

* Implement `ProblemDetail` Pydantic model (core fields: `type`, `title`, `status`, `detail`, `instance`; add `code`, optional `errors`, `trace_id`).
* Provide a helper `problem(status, code, title, detail=None, type_url=None, **ctx)` returning `JSONResponse` with `Content-Type: application/problem+json`.
* Replace ad‑hoc `HTTPException(detail="…")` with `problem(...)`.
* Map existing domain exceptions to ADE codes (e.g., `documents.not_found`, `jobs.invalid_status`).
  **Why:** RFC **9457** defines the standard shape and media type (`application/problem+json`). ([RFC Editor][1])
  **Acceptance**
* All 4xx/5xx responses from routes return the documented Problem Details shape with `code` and stable `type` URIs (e.g., `https://developer.ade.local/problems/documents.not_found`).

---

### 4) Pagination: single envelope + shared params

**Files:** `backend/app/api/pagination.py`, `backend/app/schemas.py`, list endpoints in all routers
**What to do**

* Create a **shared dependency**:

  ```py
  from fastapi import Query
  def parse_pagination(
      limit: int = Query(50, ge=1, le=200),
      offset: int = Query(0, ge=0),
  ) -> tuple[int, int]: return limit, offset
  ```
* Standard **response envelope**:

  ```json
  { "items": [ ... ], "page_info": { "limit": 50, "offset": 0, "total": 123, "next_offset": 50, "has_more": true } }
  ```
* Update `/jobs`, `/documents`, `/events` (+ nested) to return the envelope consistently; document order guarantees.
* Optionally include **`Link` header** (`rel="next"`) following RFC **8288** (if you add links). ([IETF Datatracker][7])
  **Note:** We remain on **offset/limit** for now; the doc can mention that cursor pagination is superior for large datasets but is out of scope. (Stripe’s `has_more` style is a well-known pattern.) ([Stripe Docs][8])
  **Acceptance**
* All list endpoints use `items + page_info`; shared `limit/offset` parameters are referenced from `components.parameters`.

---

### 5) Status codes & headers hygiene

**Files:** All routers
**What to do**

* POST that creates resources returns **`201 Created`** **with `Location`** pointing at the canonical resource URL. ([RFC Editor][2])
* For unsupported delete on jobs, return **`405 Method Not Allowed`** **and include `Allow`** header listing supported methods (spec requirement). ([RFC Editor][2])
* For downloads, return proper content type and **`Content-Disposition`** per RFC **6266**; avoid unsafe filenames. ([IETF Datatracker][9])
  **Acceptance**
* Tests assert presence of `Location` for creates and `Allow` for 405.

---

### 6) Tagging, summaries, and **operationId** convention

**Files:** All routers
**What to do**

* Use curated tags: `health`, `auth`, `configurations`, `documents`, `jobs`, `events` (match OpenAPI builder tags).
* Set concise `summary` and rich `description` per operation.
* Enforce **unique** `operationId` with `<tag>_<action>` (e.g., `jobs_list`, `documents_download`). OpenAPI recommends uniqueness; tools rely on it. ([Swagger][10])
  **Acceptance**
* Spectral passes `operation-operationId-unique`. ([Redocly][11])

---

### 7) Schema polish (all public models)

**Files:** `backend/app/schemas.py`
**What to do**

* Every field has `Field(description=…, examples=[…])`.
* Timestamps: use `datetime` or document `format: date-time` (RFC 3339). ([Document360][12])
* Clarify optional vs nullable; document any aliases.
  **Acceptance**
* No missing descriptions on public schemas in Spectral; timestamps show `format: date-time`.

---

### 8) Reusable responses/parameters/examples

**Files:** `backend/app/api/openapi.py`, `docs/examples/*` (optional)
**What to do**

* Define `components.responses` for **400/401/403/404/409/422/429/500**, each referencing the Problem Details schema and containing examples.
* Define shared `components.parameters` (`limit`, `offset`, common filters).
* Add examples for typical 2xx and at least one error per operation; include multipart upload example for `/documents`. Good examples materially improve dev experience. ([Redocly][13])
  **Acceptance**
* Swagger UI shows named examples; Spectral DRY checks pass for reuse. ([OpenAPI Documentation][14])

---

### 9) `/health` behavior and caching

**Files:** `backend/app/routes/health.py`
**What to do**

* Keep it unauthenticated; document fields (`status`, `purge`).
* Add `Cache-Control: no-store` to **response**. (“no-store” is the directive that actually forbids storing.) ([MDN Web Docs][15])
  **Acceptance**
* Response includes `Cache-Control: no-store`; OpenAPI describes no auth and shows example.

---

### 10) DX: Swagger UI/Redoc curation

**Files:** `backend/app/main.py`
**What to do**

* Ensure `/docs` and `/redoc` pick up the enriched schema and tag order; add landing description that explains how to authenticate (Basic/Bearer) before “Try it”.
  **Acceptance**
* UIs reflect curated tags and metadata.

---

### 11) CI checks: lint + validate + diff

**Files:** `.spectral.yaml`, scripts
**What to do**

* **Spectral**: enable `spectral:oas` rules; at minimum enforce:

  * `operation-operationId-unique`, `no-empty-servers`, `no-inline-schemas`, required `info.contact/license`, examples for error responses. ([Stoplight][3])
* **Validation**: run `openapi-spec-validator` on the generated JSON. ([PyPI][16])
* **Diff**: run `oasdiff` to detect **breaking changes** vs baseline. ([GitHub][17])
  **Acceptance**
* A `make openapi-check` (or script) regenerates the spec, lints, validates, and fails the build on breaking diffs.

---

### 12) Narrative docs

**Files:** `docs/reference/api-schema.md`, `docs/security.md`, `CHANGELOG.md`
**What to include**

* Download link to OpenAPI, environments/base URLs, auth flows (Basic and Bearer), meaning of `WWW-Authenticate` challenges, and session cookie notes. ([MDN Web Docs][18])
* Error model (Problem Details) + ADE error code table with remediation. ([RFC Editor][1])
* Pagination (`limit`, `offset`, `page_info`, ordering); optional **`Link`** pagination header footnote (RFC 8288). ([IETF Datatracker][7])
* Status code policy (201/Location, 405/Allow, 204 deletes). ([RFC Editor][2])

---

### 13) (Optional) Rate limiting headers

**Files:** middleware or response layer (if applicable), docs
**What to do**

* If we expose rate limits, prefer the emerging **RateLimit**/**RateLimit-Policy** header fields (IETF httpapi draft) or clearly document legacy `X-RateLimit-*` with `Retry-After` on `429`. ([IETF][19])
  **Acceptance**
* Docs reflect whichever approach we use; `429` example includes headers.

---

## Code patterns to copy

**Problem Details helper**

```py
# backend/app/api/errors.py
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

class ProblemDetail(BaseModel):
    type: str = Field(..., description="URI reference that identifies the problem type")
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    # ADE extensions
    code: str
    errors: dict | list | None = None
    trace_id: str | None = None

def problem(status: int, code: str, title: str, detail: str | None = None,
            type_url: str | None = None, instance: str | None = None, **ext):
    body = ProblemDetail(
        type=type_url or f"https://developer.ade.local/problems/{code}",
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        code=code,
        **({"errors": ext.pop("errors")} if "errors" in ext else {}),
        **ext,
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")
```

**A typical route (auth-protected, with operationId and examples)**

```py
@router.get(
    "/jobs",
    response_model=PaginatedJobsResponse,
    summary="List jobs",
    operation_id="jobs_list",
    responses={
        401: {"$ref": "#/components/responses/Unauthorized"},
        422: {"$ref": "#/components/responses/UnprocessableEntity"},
    },
)
def list_jobs_endpoint(p: Pagination = Depends(parse_pagination), db: Session = Depends(get_db)) -> PaginatedJobsResponse:
    items, total = list_jobs(db, limit=p.limit, offset=p.offset)  # your service
    next_off = p.offset + p.limit if (p.offset + p.limit) < total else None
    return PaginatedJobsResponse(
        items=[...],
        page_info=PageInfo(limit=p.limit, offset=p.offset, total=total, next_offset=next_off, has_more=next_off is not None),
    )
```

**Public health endpoint (no auth, no-store)**

```py
@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    openapi_extra={"security": []},
    summary="Readiness check",
    operation_id="health_get",
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    response = HealthResponse(status="ok", purge=get_auto_purge_status(db))
    from fastapi import Response
    r = Response(content=response.model_dump_json(), media_type="application/json")
    r.headers["Cache-Control"] = "no-store"  # don't cache health
    return r
```

---

## Definition of Done (DoD)

* **Spec**: `openapi.json` includes auth schemes, reusable errors/params, examples; all routes have `operationId` + curated tags.
* **Runtime**: Routes return Problem Details on errors; list endpoints use `items + page_info`; `201` includes `Location`; `405` includes `Allow`; `/health` sets `Cache-Control: no-store`.
* **Quality gates**: `spectral` and `openapi-spec-validator` pass; `oasdiff` shows no unintended breaking changes.
* **Docs**: `docs/reference/api-schema.md` explains auth, errors, pagination, and status code policy; changelog updated for API‑visible changes.

---

## File‑by‑file checklist

* `backend/app/api/openapi.py` — OpenAPI builder with info/servers/tags/components/examples & global security.
* `backend/app/api/errors.py` — Problem Details model + `problem()` helper.
* `backend/app/api/pagination.py` — `parse_pagination`, `PageInfo`, shared params constants.
* `backend/app/schemas.py` — Field descriptions, `format: date-time`; paginated response models.
* `backend/app/routes/*` — Set `summary`, `description`, `operation_id`; convert list routes to envelope; standardize errors; add `Location`/`Allow`/download headers; override `/health` security and add `no-store`.
* `build/openapi/openapi.json` — Generated output (kept in repo for diffing).
* `.spectral.yaml`, `scripts/check-openapi.sh` (or Makefile) — lint/validate/diff in one command.
* `docs/reference/api-schema.md`, `docs/security.md`, `CHANGELOG.md` — narrative and change notes.

---

## References (key best practices)

* **Problem Details (errors):** RFC 9457 (obsoletes RFC 7807) and practical guidance. ([RFC Editor][1])
* **OpenAPI 3.1:** Spec overview; JSON Schema alignment. ([Swagger][5])
* **Auth schemes:** HTTP Basic (RFC 7617), OAuth 2.0 Bearer (RFC 6750), `WWW-Authenticate` header semantics. ([IETF Datatracker][6])
* **Status codes/headers:** `201 Location` and `405 Allow` (RFC 9110). ([RFC Editor][2])
* **Downloads:** `Content-Disposition` (RFC 6266). ([IETF Datatracker][9])
* **Pagination links:** Web Linking (RFC 8288); Stripe’s `has_more` reference. ([IETF Datatracker][7])
* **Caching:** `Cache-Control: no-store` guidance (MDN). ([MDN Web Docs][15])
* **Lint/validate/diff:** Spectral ruleset; openapi-spec-validator; oasdiff. ([Stoplight][3])

---

### Notes

* We keep ADE’s **session cookie** behavior described in docs (not modeled as a separate OpenAPI scheme). Mention in `/auth/*` operation descriptions and the narrative security page.
* If rate limiting is exposed now or later, prefer the IETF **RateLimit** header fields or document legacy `X‑RateLimit-*` + `Retry‑After`. (Draft status noted in docs.) ([IETF][19])

---
