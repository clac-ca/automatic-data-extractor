# FastAPI Best Practice Violations

The following findings were documented after reviewing the repository against the guidance in `fastapi-best-practices.md`. Each item links to the relevant best-practice section and the exact location in the codebase so future contributors can quickly triage and address them.

## 1. Let FastAPI parse request bodies with Pydantic
- **Best practice**: “Excessively use Pydantic” to validate and transform request data directly in route signatures.【F:fastapi-best-practices.md†L200-L224】
- **Issue**: Multiple routes pull `request.json()` manually and then call `model_validate`, bypassing FastAPI’s automatic body parsing and native 422 error responses.
  - `AuthRoutes.create_api_key` uses the `_parse_api_key_issue_request` dependency to read JSON directly.【F:backend/api/modules/auth/router.py†L25-L107】
  - `JobsRoutes.submit_job` reads the raw request body and then validates it.【F:backend/api/modules/jobs/router.py†L30-L112】
  - `WorkspaceRoutes.add_member` fetches JSON from the request instead of letting FastAPI inject a `WorkspaceMemberCreate` instance.【F:backend/api/modules/workspaces/router.py†L26-L99】
- **Why it matters**: Manual parsing side-steps FastAPI’s validation pipeline, making error handling inconsistent and increasing boilerplate. Moving these payloads into the function signature (e.g., `payload: JobSubmissionRequest`) restores automatic 422 responses, ensures dependency caching, and simplifies unit testing.
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

## 2. Rely on response models instead of custom JSON serialization
- **Best practice**: Avoid instantiating/serialising Pydantic responses manually—FastAPI already validates and renders objects declared via `response_model`.【F:fastapi-best-practices.md†L514-L548】
- **Issue**: The health check endpoint wraps the `HealthCheckResponse` in a custom `JSONResponse`, defeating response-model validation and duplicating serialization logic.【F:backend/api/modules/health/router.py†L1-L30】【F:backend/api/modules/health/service.py†L12-L30】
- **Why it matters**: Returning `JSONResponse(content=result)` bypasses the declared `response_model`, so schema regressions won’t be caught. It also performs redundant JSON encoding even though `HealthService.status()` already returns a `HealthCheckResponse`. The route should simply `return result` and let FastAPI handle serialization.
- ✅ **Suggested fix** – return the schema instance directly:
  ```python
  @router.get("", response_model=HealthCheckResponse)
  async def read_health(service: HealthService = Depends(...)) -> HealthCheckResponse:
      return await service.status()
  ```
  FastAPI will encode the object once and validate it against the documented schema.

## 3. Expose documentation endpoints only in safe environments
- **Best practice**: Hide the OpenAPI/Swagger docs by default unless the API is public or the environment is explicitly allowed.【F:fastapi-best-practices.md†L609-L625】
- **Issue**: `Settings.enable_docs` defaults to `True`, which keeps `/docs`, `/redoc`, and `/openapi.json` available in every deployment.【F:backend/app/config.py†L14-L109】【F:backend/api/main.py†L1-L62】
- **Why it matters**: Always-on docs increase attack surface in production environments. Consider defaulting `enable_docs` to `False` and enabling docs only for local/staging (e.g., via an env var allow-list) so operators must opt in explicitly.
- ✅ **Suggested fix** – gate docs by environment:
  ```python
  class Settings(BaseSettings):
      enable_docs: bool = Field(
          default_factory=lambda: os.getenv("ADE_ENV") in {"local", "staging"}
      )

      @property
      def docs_urls(self) -> tuple[str | None, str | None]:
          return (self.docs_url, self.redoc_url) if self.enable_docs else (None, None)
  ```
  Production instances now hide interactive docs unless the environment explicitly opts in.

## 4. Split settings by domain instead of one monolithic `BaseSettings`
- **Best practice**: Break large configuration surfaces into focused `BaseSettings` classes per module or domain to keep concerns isolated and maintainable.【F:fastapi-best-practices.md†L259-L306】
- **Issue**: `backend/app/config.py` defines a single `Settings` class that mixes environment flags, database tuning, authentication secrets, SSO settings, retention policies, and documentation toggles in one object.【F:backend/app/config.py†L14-L109】
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
- ✅ **Status**: `/auth/token` now routes the OAuth2 form through the `TokenRequest` schema and a `parse_token_request` dependency so bad credentials surface as FastAPI 422 responses instead of leaking uncaught `ValueError`s.【F:backend/api/modules/auth/schemas.py†L1-L55】【F:backend/api/modules/auth/dependencies.py†L1-L53】【F:backend/api/modules/auth/router.py†L33-L62】
- **Notes**: Future form-based routes should follow the same pattern—convert the raw form payload into a Pydantic schema before invoking service logic so validation stays at the boundary.

---

_Update this file as issues are resolved so future FastAPI audits can focus on new gaps instead of rediscovering the same problems._
