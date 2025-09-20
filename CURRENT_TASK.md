## 1. Executive Summary
- The current FastAPI-powered ADE backend exposes health, authentication, configuration, document, job, and event APIs, but the generated OpenAPI document is skeletal. It lacks required metadata, security schemes, consistent operation summaries, and machine-friendly examples, which impairs SDK generation and client integration.
- Runtime behavior already enforces multiple authentication modes, emits diverse error payloads, and applies ad-hoc pagination. None of these contracts are standardised or documented, creating ambiguity for external consumers and making change management risky.
- The target outcome is an OpenAPI 3.1 specification that encodes ADE's real security posture (HTTP Basic and Bearer), describes every operation and schema with clear prose, standardises error handling around RFC 7807 Problem Details with ADE-specific error codes, and unifies pagination/list responses. The documentation should ship with validated tooling (lint + diff gates) and narrative guides so future contributors can keep the contract stable with minimal runtime adjustments beyond envelope/metadata alignment.

## 2. Current State (Findings)
### Inventory of public endpoints
- **health** (`backend/app/routes/health.py`)
  - `GET /health` – No authentication dependency; returns `HealthResponse` with `{status: str, purge: AutoPurgeStatus|None}`. No documented failure modes or cache hints.
- **auth** (`backend/app/routes/auth.py`)
  - `POST /auth/login` – Basic credentials extracted from `Authorization` header; issues session cookie + JSON body. Raises bare `HTTPException` strings for 4xx results.
  - `POST /auth/logout` – Requires active session cookie; returns `204 No Content`; no error schema.
  - `GET /auth/session` – Requires valid session cookie; responds `AuthSessionResponse`; emits 401 with string detail when missing/expired.
  - `GET /auth/me` – Requires any authenticated context; returns same envelope; pulls session info opportunistically.
  - `GET /auth/sso/login` – Redirect (307) to IdP; raises 404 when SSO disabled.
  - `GET /auth/sso/callback` – Exchanges OIDC code; responds `AuthSessionResponse`; surfaces exchange errors as `400` with plain string detail.
- **configurations** (`backend/app/routes/configurations.py` – depends on `get_current_user` for all routes)
  - `POST /configurations` – Creates config, returns 201 with body only (no `Location`). Conflicts yield 409 with string detail.
  - `GET /configurations` – Returns raw JSON array of `ConfigurationResponse` without pagination metadata.
  - `GET /configurations/{configuration_id}` – 200 with resource; 404 returns string detail.
  - `GET /configurations/active/{document_type}` – Normalises path parameter; emits 422 with Pydantic error list and 404 string detail.
  - `GET /configurations/{configuration_id}/events` – Returns `EventListResponse` envelope (items + total + limit + offset + entity).
  - `PATCH /configurations/{configuration_id}` – Returns updated resource; handles 404/409 like POST.
  - `DELETE /configurations/{configuration_id}` – 204 with empty body; on 404 returns string detail.
- **jobs** (`backend/app/routes/jobs.py` – all routes require `get_current_user`)
  - `POST /jobs` – 201 with `JobResponse`; raises multiple custom exceptions mapped to 404, 409, 422 with plain strings.
  - `GET /jobs` – Returns bare list of jobs; query params `limit` (1-200), `offset`, `input_document_id`. No total/envelope.
  - `GET /jobs/{job_id}` – 200 resource or 404 string detail.
  - `GET /jobs/{job_id}/events` – Returns `EventListResponse` envelope; query filters similar to `/events`.
  - `PATCH /jobs/{job_id}` – Returns updated resource; 409/422 string detail; 404 string detail.
  - `DELETE /jobs/{job_id}` – Hard-coded 405 with string detail in body.
- **documents** (`backend/app/routes/documents.py` – all routes require `get_current_user`)
  - `POST /documents` – Multipart upload; returns 201 `DocumentResponse`. Emits 413/422 with bespoke `detail` dicts (`{error, message, ...}`) that differ from other errors.
  - `GET /documents` – Returns bare list ordered by recency; same pagination params as jobs without metadata.
  - `GET /documents/{document_id}` – 200 resource or 404 string detail.
  - `GET /documents/{document_id}/jobs` – Returns `DocumentJobsResponse` envelope with nested lists; 404 string detail if missing.
  - `PATCH /documents/{document_id}` – 200 updated resource; 404 string detail.
  - `GET /documents/{document_id}/download` – Streams file; 404/500 surfaced as string detail.
  - `DELETE /documents/{document_id}` – Returns 200 `DocumentResponse` (soft delete) instead of 204; 404 errors as strings.
  - `GET /documents/{document_id}/events` – Returns `EventListResponse` envelope.
- **events** (`backend/app/routes/events.py` – requires `get_current_user`)
  - `GET /events` – Returns `EventListResponse` envelope; validates entity filters; errors as string details.

### Current authentication presentation vs. runtime behaviour
- `get_current_user` in `backend/app/auth/dependencies.py` supports cookie-based sessions, HTTP Basic, HTTP Bearer (SSO), and a development-only `none` mode. It assembles `WWW-Authenticate` headers combining `Basic` and `Bearer` when relevant.
- The generated OpenAPI spec (`app.openapi()`) contains no `components.securitySchemes`, no `security` requirements, and therefore falsely suggests every endpoint is unauthenticated.
- Session cookies issued by Basic/SSO flows are not represented in OpenAPI descriptions; `AuthSessionResponse.modes` lists configured auth modes but lacks explanatory text.
- The “open access” (`auth_modes=none`) behaviour is not surfaced anywhere; there is no warning about its development-only intent.

### Current error responses vs. RFC 7807
- `HTTPException` calls throughout routes use plain strings or ad-hoc dicts under `detail`. None include `type`, `title`, or ADE-specific error codes.
- Validation errors propagated from FastAPI/Pydantic remain as default FastAPI 422 payloads (list of errors) rather than structured Problem Details.
- 401 vs. 403 handling varies: e.g., inactive user during login yields 403, but missing credentials return 401. There is no documentation clarifying when each occurs.
- `WWW-Authenticate` headers are set by `get_current_user` but their possible values (`Basic realm="ADE"`, `Bearer realm="ADE"`) are not documented.
- No reusable error responses exist in `components.responses`; each route implicitly redefines its own error payload.

### Current pagination patterns and inconsistencies
- Query parameters for pagination (`limit`, `offset`) are repeated manually per endpoint; there is no shared dependency or `components.parameters` entry.
- Response shapes differ: `/events` and nested timeline endpoints return `{items, total, limit, offset, entity}`, while `/jobs` and `/documents` return raw arrays without metadata, making client pagination guesswork.
- Sorting/order guarantees (e.g., “ordered by creation time descending”) live in docstrings but not in schema descriptions or OpenAPI response metadata.
- No cursor-based option or pagination link metadata exists; expiry semantics for offsets are undefined.

### Schema/field description and example gaps
- Many Pydantic models in `backend/app/schemas.py` omit `Field` descriptions (e.g., `AuthSessionResponse`, `JobResponse`, `JobMetrics`, `EventResponse`). Timestamp fields are typed as `str` without format guidance or timezone expectations.
- Schemas expose aliased fields (`metadata_` vs. `metadata`) without clarifying serialization, and optionality/nullability is implied rather than explicitly documented.
- Request models (`JobCreate`, `DocumentUpdate`, etc.) lack examples illustrating common payloads; enums (e.g., `JobStatus`) are defined but not described.
- There is no canonical example object for success or error responses in OpenAPI.

### OperationId, tag organisation, and missing global metadata
- OpenAPI `info` currently contains only title and version; there is no description, contact, license, or external docs link.
- No `servers` array is defined, so consumers must guess base URLs for staging/production.
- Tags derive directly from router tags with no descriptions or order; the UI displays endpoints alphabetically rather than in a curated journey.
- Operation summaries default to camel-cased function names (e.g., “Create Job Endpoint”) and descriptions mirror docstrings without enforcing consistent tone.
- Operation IDs follow FastAPI defaults (`create_job_endpoint_jobs_post`), making SDK regeneration unstable and verbose.

## 3. Decisions & Standards
- **Pagination style**: Keep offset-based pagination for consistency with current queries. Define reusable `limit` (default 50, max 200) and `offset` parameters, plus optional `sort`/filter parameters per resource. All list endpoints will return an envelope containing `items` plus a `page_info` object with `limit`, `offset`, `total`, and `next_offset` (nullable) plus boolean `has_more`. Document ordering guarantees per endpoint.
- **Error envelope**: Adopt RFC 7807 `application/problem+json` for all client-visible errors (400, 401, 403, 404, 409, 422, 429, 500). Extend with ADE-specific fields: `code` (stable identifier) and optional `errors` for field-level issues. Use canonical `type` URLs rooted at the future developer portal (`https://developer.ade.local/problems/{code}` placeholder until portal lives).
- **Domain error codes**: Introduce a controlled list aligned with existing exceptions, e.g., `auth.invalid_credentials`, `auth.account_inactive`, `auth.session_missing`, `documents.not_found`, `documents.too_large`, `documents.invalid_expiration`, `jobs.not_found`, `jobs.invalid_status`, `jobs.immutable`, `configurations.conflict_active`, `configurations.not_found`, `events.invalid_filter`, `general.internal_error`. Each Problem Details response will include `code` and machine-readable context (e.g., `max_upload_bytes`). Document the taxonomy in OpenAPI `components.schemas.ErrorCode` and in narrative docs.
- **Tags and tone**: Standard tag set with descriptions and display order: `health` (“Service readiness and liveness”), `auth` (“Authentication and session lifecycle”), `configurations` (“Document configuration versions”), `documents` (“Document ingestion and retrieval”), `jobs` (“Extraction job orchestration”), `events` (“Audit timeline and history”). Operation summaries use imperative voice (“Create a configuration version”) and descriptions remain concise active voice.
- **OperationId convention**: `<tag>_<action>` where `tag` is the singular tag name (`jobs`, `documents`, etc.) and `action` is a verb phrase (`create`, `list`, `get`, `update`, `delete`, `list_events`, `download`). Compound actions (e.g., `/documents/{id}/jobs`) become `documents_list_jobs`. Ensure stability by explicitly setting `operation_id` in route decorators.
- **Security documentation**: Define `basicAuth` (HTTP scheme `basic`) and `bearerAuth` (HTTP scheme `bearer`, format `JWT`). Apply global security requirement `[{"basicAuth": []}, {"bearerAuth": []}]` so either scheme satisfies the API. Public endpoints (currently only `/health`) must set `dependencies=[]` and `include_in_schema=True` but override security to `[]`. Session-cookie semantics will be described in operation docs and narrative sections. Development-only “open access” remains undocumented as a scheme but explained in prose with warnings.
- **Response code policy**: GET returns 200, POST create returns 201 with `Location` header referencing canonical resource URL, PATCH returns 200 with updated body, PUT (unused) reserved for full replacement, DELETE returns 204 for destructive operations unless a body is contractually required (document soft delete may continue returning body but must justify and document idempotency). Async operations (if introduced) use 202. 401 reserved for unauthenticated, 403 for authenticated but forbidden.
- **Content negotiation and formats**: Default `application/json` for request/response except file download which returns appropriate `Content-Type` plus documented `Content-Disposition`. Timestamps documented as RFC 3339 with timezone (`Z` or offset), second-level precision unless otherwise noted.
- **OpenAPI delivery**: Override `app.openapi` to build from a single generator function that injects metadata (info, servers, externalDocs, tags, reusable components, examples). Persist generated JSON under `build/openapi/openapi.json` for lint/diff tooling.
- **Documentation tone**: All descriptions use second-person, active voice, and avoid internal jargon. Examples highlight typical success and failure flows aligned with tests.

## 4. Planned Changes (No Code Yet)
#### T1 – Centralise OpenAPI generation
- **Intent/Why**: Ensure a single source of truth that enriches metadata, components, tags, and examples (Objectives 1, 9).
- **Affected Areas**: `backend/app/main.py`, new module `backend/app/api/openapi.py` (or similar), build artefacts directory.
- **Implementation Notes**: Create helper that calls `fastapi.openapi.utils.get_openapi`, injects `info` (description covering auth modes narrative, contact, license), `servers` for dev/staging/prod, tag definitions with order, and `externalDocs`. Override `app.openapi = custom_builder` during startup and write JSON file during CI/docs build.
- **Risks & Mitigations**: Risk of drift if JSON export skipped; mitigate by adding CI step to regenerate and compare. Ensure override caches spec to avoid performance hit.
- **Acceptance Criteria**: OpenAPI document includes enriched `info`, `servers`, curated `tags`, and `externalDocs`; generated file matches runtime `app.openapi()` and passes validators.

#### T2 – Define security schemes and apply global alternatives
- **Intent/Why**: Document Basic and Bearer auth without custom constructs; surface public vs. protected endpoints (Objective 2).
- **Affected Areas**: OpenAPI builder module, router decorators for `/health`, optional declarative security dependencies.
- **Implementation Notes**: Add `components.securitySchemes` entries, set global `security` to `[{"basicAuth": []}, {"bearerAuth": []}]`. For `/health`, set `@router.get(..., include_in_schema=True)` with `openapi_extra={"security": []}`. For authentication endpoints, describe behaviours and set security requirements appropriately (e.g., `/auth/login` accepts Basic).
- **Risks & Mitigations**: Misrepresenting cookie-based flows; mitigate by expanding descriptions to explain session issuance and emphasising cookies derive from Basic/Bearer exchange. Verify generated UI renders lock icons correctly.
- **Acceptance Criteria**: Swagger UI shows lock icons for protected endpoints, `/health` shows no security, and scheme descriptions outline usage and `WWW-Authenticate` values.

#### T3 – Implement RFC 7807 Problem Details helper
- **Intent/Why**: Standardise error payloads and enable reusable responses (Objective 3).
- **Affected Areas**: New module (e.g., `backend/app/api/errors.py`), all routers, services raising HTTP errors, corresponding tests.
- **Implementation Notes**: Create Pydantic model for Problem Details with additional fields (`code`, optional `errors`, context). Provide helper function to raise/return Problem Details with consistent headers (`Content-Type: application/problem+json`). Update routes to use helper instead of raw `HTTPException` for controlled errors.
- **Risks & Mitigations**: Widespread test updates required; mitigate by documenting mapping from existing exceptions to new helper, adding unit tests for helper, and performing incremental updates per router. Ensure existing error messages preserved in `detail` or `title` to avoid regressions.
- **Acceptance Criteria**: All documented 4xx/5xx responses conform to Problem Details schema, tests assert against `code`/`type`/`title`, and OpenAPI `components.schemas.ProblemDetail` matches runtime payloads.

#### T4 – Define ADE error code taxonomy and mapping
- **Intent/Why**: Provide stable machine-readable identifiers for clients (Objective 3).
- **Affected Areas**: Documentation in OpenAPI components, new constants module (e.g., `backend/app/api/error_codes.py`), exception handling in services/routes, docs reference tables.
- **Implementation Notes**: Enumerate codes per domain (auth, configurations, documents, jobs, events, general). Map existing custom exceptions to codes (e.g., `DocumentNotFoundError → documents.not_found`). Include optional metadata (e.g., `max_upload_bytes`). Update Problem Details helper to accept `code` and context. Document taxonomy in narrative reference.
- **Risks & Mitigations**: Missing edge cases; mitigate by auditing tests and services to ensure every `HTTPException` path uses a defined code. Reserve future-proof codes (e.g., `general.internal_error`).
- **Acceptance Criteria**: Problem Details responses always include a recognised `code`; OpenAPI lists allowed codes; docs include table describing meaning and remediation.

#### T5 – Create reusable error responses in OpenAPI components
- **Intent/Why**: Reduce duplication and ensure consistent documentation (Objective 3).
- **Affected Areas**: OpenAPI builder, router decorators, components definitions.
- **Implementation Notes**: Define `components.responses` for 400, 401, 403, 404, 409, 422, 429, 500 referencing the Problem Details schema with tailored descriptions and examples. Update route `responses` argument to reuse these components, adding operation-specific examples where necessary.
- **Risks & Mitigations**: Potential mismatch between documented and actual responses; mitigate by generating OpenAPI after code updates and running contract tests that exercise each error path.
- **Acceptance Criteria**: Every operation references the appropriate error components; Swagger UI displays example Problem Details payloads.

#### T6 – Standardise pagination parameters and envelopes
- **Intent/Why**: Align list semantics across endpoints (Objective 4).
- **Affected Areas**: Shared dependency module (e.g., `backend/app/api/pagination.py`), routers returning lists, schemas (`EventListResponse`, new `PaginatedResponse[T]` generics or dedicated responses), tests verifying list results.
- **Implementation Notes**: Introduce reusable dependency or function to parse `limit`/`offset` (with docs). Update `EventListResponse` to embed new `page_info` shape; create new `PaginatedJobsResponse`, `PaginatedDocumentsResponse`, etc., or adopt generic `ListResponse`. Adjust routes to return envelope with metadata, ensuring order semantics described in response model docstrings. Provide `components.parameters` for `limit`, `offset`, plus shared filter params where applicable.
- **Risks & Mitigations**: Breaking change for clients expecting bare arrays. Mitigate by flagging in Rollout plan (e.g., version bump, change log entry), providing migration guidance, and considering transitional support (e.g., query param opt-in) if required.
- **Acceptance Criteria**: All list endpoints respond with documented envelope containing `items` and `page_info`; OpenAPI reflects shared parameter references and includes examples of paginated responses.

#### T7 – Document filtering/sorting parameters centrally
- **Intent/Why**: Avoid drift and describe optional filters (Objective 4).
- **Affected Areas**: OpenAPI components (`components.parameters`), router signatures for events/jobs/documents.
- **Implementation Notes**: Create named parameters for `event_type`, `entity_type`, `occurred_before`, etc., with descriptions and formats. Reference them in route `openapi_extra` or dependencies. Document default ordering and filter behaviour in operation descriptions.
- **Risks & Mitigations**: Parameter names may need to remain to avoid breaking changes; ensure component references maintain same query string names. Validate with generated spec.
- **Acceptance Criteria**: Swagger UI parameter tables pull descriptions from shared definitions; no duplicated strings in code.

#### T8 – Enhance schema metadata and field descriptions
- **Intent/Why**: Provide field-level clarity (Objectives 1, 6).
- **Affected Areas**: `backend/app/schemas.py`, any additional schema modules, docstrings.
- **Implementation Notes**: Add `Field(description=..., examples=[...], json_schema_extra={...})` to each public field. Replace raw `str` timestamps with `datetime` in models if feasible or document format explicitly via `Field` metadata (`format="date-time"`). Clarify optionality, enumerations, alias behaviours, and include sample objects in docstrings.
- **Risks & Mitigations**: Changing field types may require migration; if using `datetime`, ensure `model_config` handles serialisation. If type change too invasive, keep `str` but set `pattern`/`format`. Update tests expecting dict equality as needed.
- **Acceptance Criteria**: JSON Schema in OpenAPI displays descriptions/formats/examples for every exposed field; linter (e.g., Spectral) reports no missing descriptions on public schemas.

#### T9 – Curate operation summaries, descriptions, and IDs
- **Intent/Why**: Improve readability and SDK generation stability (Objective 1).
- **Affected Areas**: Route decorators in all routers.
- **Implementation Notes**: Set `summary`, `description`, and `operation_id` explicitly per endpoint using the agreed convention and tone. Expand descriptions to clarify authentication expectations, side effects, idempotency, and output semantics. Include pointer to relevant examples and links to narrative docs via Markdown.
- **Risks & Mitigations**: Human error in operationId collisions; mitigate by adding script/check in CI (Quality Gates). Ensure translations reflect actual behaviour.
- **Acceptance Criteria**: Each operation has concise summary (<120 chars), informative description, and `operationId` matching `<tag>_<action>` with no duplicates.

#### T10 – Attach request/response examples
- **Intent/Why**: Aid SDK generation and testing (Objective 1).
- **Affected Areas**: OpenAPI builder (components.examples), route `responses`, schema definitions.
- **Implementation Notes**: Derive canonical examples from existing tests/fixtures. For each success response, add `examples` in route `responses`. For Problem Details, include representative 401/404/422 bodies. Provide multipart/form-data example for `/documents` upload and redirect example for SSO login.
- **Risks & Mitigations**: Examples drifting from actual payload; mitigate by building generator to load example JSON from static fixtures (e.g., `docs/examples/`). Keep examples lightweight to avoid maintenance burden.
- **Acceptance Criteria**: Swagger UI shows named examples for every 2xx and at least one error per operation; `spectral` lint passes no-empty-example rules.

#### T11 – Document /health and operational endpoints clearly
- **Intent/Why**: Give SREs predictable behaviour (Objective 8).
- **Affected Areas**: Health router, schema descriptions, docs narrative.
- **Implementation Notes**: Expand `HealthResponse` field descriptions (e.g., purge status semantics, possible `status` values). Document 503 behaviour if/when health indicates failure. Add example response showing purge metadata. Clarify caching headers or expectation (likely `Cache-Control: no-store`).
- **Risks & Mitigations**: If runtime never returns 503, clarify in docs to avoid false expectation. If we intend to add 503, ensure implementation plan captured separately.
- **Acceptance Criteria**: Health endpoint summary/description outlines success criteria, failure behaviour, and authentication (none). Example included in OpenAPI.

#### T12 – Provide Swagger UI and ReDoc configuration with curated defaults
- **Intent/Why**: Improve developer experience when browsing docs (Objective 9).
- **Affected Areas**: `backend/app/main.py` (FastAPI constructor parameters), potential static assets for theming, docs index page.
- **Implementation Notes**: Configure FastAPI to serve Swagger UI and ReDoc with custom title/intro text, default tag expansion order matching curated tags. Optionally add landing markdown describing how to authenticate before trying endpoints. Ensure toggles reference generated OpenAPI file.
- **Risks & Mitigations**: Over-customising UI can complicate upgrades; keep configuration minimal and document in comments.
- **Acceptance Criteria**: Visiting `/docs` and `/redoc` shows updated metadata, ordered tags, and introductory guidance.

#### T13 – Wire OpenAPI linting and diff checks into CI
- **Intent/Why**: Prevent regressions and enforce spec quality (Objective 9).
- **Affected Areas**: `pyproject.toml` (new dev dependencies), CI workflow (if available) or developer tooling scripts, documentation.
- **Implementation Notes**: Add `spectral` and `openapi-spec-validator` (or `prance`) to dev dependencies. Create `scripts/check-openapi.sh` (or Makefile target) that regenerates spec, runs validators, and stores JSON. Add `openapi-diff` (e.g., Redocly CLI or `oasdiff`) to compare against previous baseline. Document workflow in CONTRIBUTING/README.
- **Risks & Mitigations**: Toolchain may increase setup complexity; mitigate by pinning versions, providing installation instructions, and caching results. For lack of existing CI, ensure local pre-commit style instructions.
- **Acceptance Criteria**: `make openapi-check` (or equivalent) runs successfully, validators pass, diff fails on breaking changes (status codes, schemas) but allows additive changes with review.

#### T14 – Document OpenAPI generation workflow and artefact storage
- **Intent/Why**: Ensure contributors know how to regenerate docs (Objective 9).
- **Affected Areas**: `DOCUMENTATION.md` or new guide, README, `docs/reference/api-schema.md`.
- **Implementation Notes**: Describe where generated spec lives, how to regenerate (`python -m backend.app.cli export-openapi` or similar), and expectations for committing JSON artefacts. Reference lint/diff commands and doc site update steps.
- **Risks & Mitigations**: Without automation, human error possible; mitigate by coupling instructions with CI enforcement.
- **Acceptance Criteria**: Repository contains up-to-date instructions; next contributor can regenerate spec following documented steps.

#### T15 – Update narrative documentation and changelog references
- **Intent/Why**: Provide human-readable guidance on auth modes, errors, pagination, versioning (Objectives 7, 10).
- **Affected Areas**: `docs/reference/api-schema.md` (new), `docs/security` section, README/CHANGELOG (if new file), `DOCUMENTATION.md`.
- **Implementation Notes**: Draft `api-schema.md` referencing OpenAPI spec, error codes, and pagination scheme. Update security docs with Basic vs. Bearer, session cookies, dev-only `none` mode warnings. Add CHANGELOG entry template for future API-visible changes. Ensure README links to docs.
- **Risks & Mitigations**: Narrative drift; mitigate by referencing generated spec sections and cross-linking to Problem Details and pagination definitions.
- **Acceptance Criteria**: Narrative docs outline authentication modes, error handling, pagination, versioning, and change management. CHANGELOG location identified for ongoing updates.

## 5. Public Documentation Narrative
Proposed outline for the accompanying human-readable documentation (landing page or `docs/reference/api-schema.md`):
- **Introduction** – Purpose of the ADE API, link to OpenAPI download, supported authentication modes.
- **Environments & Base URLs** – Table listing development, staging, production base URLs with notes on TLS and sample hostnames.
- **Authentication**
  - HTTP Basic flow (when enabled) and session cookie issuance.
  - HTTP Bearer / SSO flow, including obtaining tokens and expected `WWW-Authenticate` headers.
  - Session cookies: lifetime, renewal, and interplay with API auth.
  - Development-only open access mode with explicit warning.
- **Error Handling**
  - Explanation of RFC 7807 structure (`type`, `title`, `status`, `detail`, `code`, `errors`).
  - Error code taxonomy table with remediation tips.
  - 401 vs. 403 policy, and expected `WWW-Authenticate` header values.
- **Pagination & Filtering**
  - Description of `limit`/`offset`, `page_info`, ordering guarantees.
  - Common filters per resource (document type, event type, occurred_at range).
  - Guidance on handling `has_more`/`next_offset`.
- **Resource Overview**
  - Per-tag summaries with links to OpenAPI sections.
  - Notes on idempotency (e.g., document deletion) and Location headers.
- **Versioning & Change Management**
