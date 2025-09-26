# FastAPI Best Practice Violations

The following findings were documented after reviewing the repository against the guidance in `fastapi-best-practices.md`. Each item links to the relevant best-practice section and the exact location in the codebase so future contributors can quickly triage and address them.

## 1. Let FastAPI parse request bodies with Pydantic
- **Best practice**: “Excessively use Pydantic” to validate and transform request data directly in route signatures.【F:fastapi-best-practices.md†L200-L224】
- **Issue**: Multiple routes pull `request.json()` manually and then call `model_validate`, bypassing FastAPI’s automatic body parsing and native 422 error responses.
- **Why it matters**: Manual parsing side-steps FastAPI’s validation pipeline, making error handling inconsistent and increasing boilerplate. Moving these payloads into the function signature (e.g., `payload: JobSubmissionRequest`) restores automatic 422 responses, ensures dependency caching, and simplifies unit testing.
- ✅ **Progress**: `JobsRoutes.submit_job` now accepts `JobSubmissionRequest` directly on the handler signature, letting FastAPI perform validation and emit native 422 errors.【F:backend/api/modules/jobs/router.py†L74-L116】
- ✅ **Progress**: `AuthRoutes.create_api_key` now relies on FastAPI to instantiate `APIKeyIssueRequest`, removing the manual dependency wrapper and restoring native validation errors.【F:backend/api/modules/auth/router.py†L1-L120】
- ✅ **Progress**: `WorkspaceRoutes.add_member` now accepts `WorkspaceMemberCreate` directly so FastAPI validates the request body and returns native 422 responses without the helper dependency.【F:backend/api/modules/workspaces/router.py†L1-L99】
- ✅ **Suggested fix** – rely on FastAPI’s signature parsing:
  ```python
  @router.post("/jobs", response_model=JobRecord, status_code=201)
  async def submit_job(payload: JobSubmissionRequest) -> JobRecord:
      return await service.submit_job(
          input_document_id=payload.input_document_id,
          configuration_id=payload.configuration_id,
          configuration_version=payload.configuration_version,
      )
  ```
  FastAPI will now build `payload` (with consistent 422 errors) before the handler runs.

## 2. Rely on response models instead of custom JSON serialization *(Resolved)*
- **Best practice**: Avoid instantiating/serialising Pydantic responses manually—FastAPI already validates and renders objects declared via `response_model`.【F:fastapi-best-practices.md†L514-L548】
- ✅ **Status**: `/health` now returns the `HealthCheckResponse` instance directly so FastAPI performs validation and serialisation without the custom `JSONResponse` wrapper.【F:backend/api/modules/health/router.py†L1-L28】【F:backend/api/modules/health/service.py†L12-L30】
- **Notes**: Follow the same pattern for future endpoints—if a service already yields a schema, return it from the route and let FastAPI handle the response.

## 3. Expose documentation endpoints only in safe environments *(Resolved)*
- **Best practice**: Hide the OpenAPI/Swagger docs by default unless the API is public or the environment is explicitly allowed.【F:fastapi-best-practices.md†L609-L625】
- ✅ **Status**: `Settings.docs_enabled` now auto-enables documentation only for the `local`/`staging` environments and requires explicit overrides elsewhere, keeping the OpenAPI/Swagger routes hidden by default in production.【F:backend/api/settings.py†L29-L118】【F:backend/api/main.py†L15-L55】
- **Notes**: Operators can still force-enable (or disable) docs via `ADE_ENABLE_DOCS`, and the app factory respects the resolved URLs through `Settings.docs_urls` and `Settings.openapi_docs_url`.

## 4. Split settings by domain instead of one monolithic `BaseSettings`
- **Best practice**: Break large configuration surfaces into focused `BaseSettings` classes per module or domain to keep concerns isolated and maintainable.【F:fastapi-best-practices.md†L259-L306】
- **Issue**: `backend/api/settings.py` defines a single `Settings` class that mixes environment flags, database tuning, authentication secrets, SSO settings, retention policies, and documentation toggles in one object.【F:backend/api/settings.py†L14-L109】
- **Why it matters**: The growing settings surface becomes harder to reason about, test, and override. Following the guide’s approach (e.g., `AuthConfig`, `DatabaseConfig`) would let each module own its configuration, simplify dependency overrides in tests, and prevent unrelated changes from rippling across the entire app configuration.
- ✅ **Suggested fix** – compose settings from smaller domains:
  ```python
  class AuthConfig(BaseSettings):
      token_secret: str
      token_expiry_minutes: int = 60


  class DatabaseConfig(BaseSettings):
      url: PostgresDsn
      pool_size: int = 5


  class Settings(BaseSettings):
      auth: AuthConfig = AuthConfig()
      database: DatabaseConfig = DatabaseConfig()
  ```
  Each module then depends on the slice it needs, avoiding cross-module churn.

## 5. Document non-200 responses for complex endpoints
- **Best practice**: Declare alternative responses (status codes, models, descriptions) in the route decorator so the generated docs reflect real error paths.【F:fastapi-best-practices.md†L609-L655】
- **Issue**: Several endpoints raise multiple `HTTPException`s but the decorator only documents the happy-path response:
  - `JobsRoutes.submit_job` returns 201 on success yet emits 400/404/422/500 errors without listing them in `responses` or providing descriptions.【F:backend/api/modules/jobs/router.py†L76-L112】
  - `DocumentsRoutes.upload_document`, `download_document`, and `delete_document` emit 400/404/413 errors but expose only the default response in the decorator.【F:backend/api/modules/documents/router.py†L40-L150】
  - `WorkspaceRoutes.add_member` raises 400/409 errors that are invisible to consumers inspecting the OpenAPI schema.【F:backend/api/modules/workspaces/router.py†L71-L108】
  - Auth routes like `issue_token`, `create_api_key`, and the SSO callback surface 400/401/403/404 failures without any OpenAPI documentation, so client SDKs miss the authentication failure shapes they need to handle.【F:backend/api/modules/auth/router.py†L38-L200】【F:backend/api/modules/auth/service.py†L124-L141】
  - Extraction results endpoints emit 404 and 409 errors but only describe the 200 response, hiding concurrency and missing-resource behaviours from the docs.【F:backend/api/modules/results/router.py†L20-L76】
- **Why it matters**: Omitting error responses from the OpenAPI spec leaves client developers guessing about failure modes and complicates automated client generation. Adding `responses={...}` entries (with structured error models where possible) will keep docs aligned with runtime behaviour and make the API safer to consume.
- ✅ **Suggested fix** – mirror runtime errors in the decorator:
  ```python
  @router.post(
      "/jobs",
      response_model=JobRecord,
      status_code=status.HTTP_201_CREATED,
      responses={
          status.HTTP_400_BAD_REQUEST: {"description": "Invalid configuration"},
          status.HTTP_404_NOT_FOUND: {"description": "Document or configuration missing"},
          status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation failed"},
          status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Job execution failed"},
      },
  )
  async def submit_job(payload: JobSubmissionRequest) -> JobRecord:
      ...
  ```
  Clients inspecting the OpenAPI schema now see every documented failure mode.

## 6. Validate workspace path parameters via dependencies instead of inline guards
- **Best practice**: Use dependencies to centralise resource validation and keep RESTful paths consistent so the same dependency can be reused across routes.【F:fastapi-best-practices.md†L310-L389】【F:fastapi-best-practices.md†L472-L512】
- **Issue**: Both `list_members` and `add_member` re-check that the `workspace_id` path parameter matches the header-provided workspace and then manually parse the body from `request` via the service. This duplicates logic and mixes concerns inside the handler.【F:backend/api/modules/workspaces/router.py†L55-L99】
- **Why it matters**: Inline guards are easy to forget when new endpoints are added, and reaching into `service.request` to read the body reintroduces the manual parsing issue. Moving this into a dependency both enforces the check everywhere and keeps handlers focused on business logic.
- ✅ **Suggested fix** – promote the guard into a reusable dependency:
  ```python
  async def validate_workspace_access(
      workspace_id: str,
      context: WorkspaceContext = Depends(bind_workspace_context),
  ) -> WorkspaceContext:
      if context.workspace.workspace_id != workspace_id:
          raise HTTPException(status.HTTP_400_BAD_REQUEST, "Workspace header mismatch")
      return context


  @router.post("/workspaces/{workspace_id}/members")
  async def add_member(
      workspace: WorkspaceContext = Depends(validate_workspace_access),
      payload: WorkspaceMemberCreate,
  ) -> WorkspaceMember:
      return await service.add_member(
          workspace_id=workspace.workspace.workspace_id,
          **payload.model_dump(),
      )
  ```
  Every route that needs the guard can now depend on `validate_workspace_access`, guaranteeing consistent behaviour.

## 7. Convert user-facing `ValueError`s into validation or HTTP errors *(Resolved)*
- **Best practice**: Raise `ValueError` inside request models (so FastAPI returns a 422) or translate them into `HTTPException`s; uncaught `ValueError`s bubble up as 500 responses.【F:fastapi-best-practices.md†L571-L605】
- ✅ **Status**: `/auth/login` now validates credentials via `LoginRequest`, so malformed emails/passwords still surface as 422 responses while the service layer works with normalised data.【F:backend/api/modules/auth/schemas.py†L1-L54】【F:backend/api/modules/auth/router.py†L28-L104】
- **Notes**: Future form-based routes should follow the same pattern—convert the raw form payload into a Pydantic schema before invoking service logic so validation stays at the boundary.

---

_Update this file as issues are resolved so future FastAPI audits can focus on new gaps instead of rediscovering the same problems._
