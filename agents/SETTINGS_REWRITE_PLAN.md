# Settings Rewrite Plan

## Current Strengths
- Configuration is still concentrated in one `Settings` class with deterministic `.env` loading, so the runtime surface is simple to understand.【F:backend/api/settings.py†L14-L125】
- Validators normalise hostnames, ports, OIDC scope strings, and filesystem paths which keeps call sites predictable even when inputs vary.【F:backend/api/settings.py†L82-L125】
- A regression test suite already exercises defaults and overrides (`backend/tests/core/test_settings.py`), so we can refactor aggressively without fear of regressions.

## Gaps from a "standard" FastAPI configuration
Despite the strong baseline, a second pass highlighted naming and typing inconsistencies that diverge from common FastAPI/Pydantic conventions:

- Field names mix `backend_*`, `auth_*`, and `sso_*` prefixes even when they represent the same conceptual grouping (server, security, persistence).【F:backend/api/settings.py†L26-L109】
- Duration/configuration units are split across minutes, days, and seconds without type-level guarantees, leaving consumers to convert by hand.【F:backend/api/settings.py†L56-L115】
- List and filesystem fields rely on custom parsing/`Path` coercion instead of first-class Pydantic types, which hides validation and makes the code harder to skim.【F:backend/api/settings.py†L34-L125】
- Secrets remain plain strings, so logging or repr output can leak values during debugging.【F:backend/api/settings.py†L66-L98】

We also do not need to maintain backwards compatibility, so we can take the opportunity to adopt cleaner names and break out of the historical `ADE_*` env variable structure where it no longer serves clarity.

## Recommended end-state
Keep a single `Settings` object, but make it read like a FastAPI tutorial example: grouped, consistently named, strongly typed, and easy to override.

### 1. Re-map configuration groups with consistent prefixes
- Rename fields to align with common nomenclature while keeping everything on the same model (e.g., `server_host`, `server_port`, `server_public_url`; `database_dsn`; `jwt_secret`; `jwt_access_ttl`; `jwt_refresh_ttl`; `oidc_client_id`).
- Drop the bespoke `backend_`/`auth_` prefixes in favour of group-based ones (`server_`, `database_`, `jwt_`, `session_`, `oidc_`, `storage_`, `logging_`).
- Expose flat env vars that align with FastAPI defaults (for example `ADE_SERVER_HOST`, `ADE_JWT_ACCESS_TTL`) so developers can rely on the built-in naming convention without nested delimiters. Document the mapping inline so future fields follow the same pattern.

### 2. Tighten typing with first-class Pydantic primitives
- Replace the free-form strings with rich types: `SecretStr` for secrets, `HttpUrl/AnyHttpUrl` for URLs, `DirectoryPath` for directories, and `Literal`/Enums for log levels.【F:backend/api/settings.py†L26-L109】
- Model durations as `timedelta` values (seconds internally, but parsed via `PositiveInt` + `Field(validation_alias=...)` or `Json[dict]` support) so call sites receive consistent objects instead of mixed-minute/day integers.
- Swap the `cors_allow_origins` string + property for `server_cors_origins: list[AnyHttpUrl] = Field(default_factory=list)` with a validator that always includes `server_public_url`. This removes the extra computed property and matches Starlette's `CORSMiddleware` expectations.【F:backend/api/settings.py†L34-L73】
- Parse `oidc_scopes` into a `list[str]` (deduplicated + sorted) instead of a space-delimited string so downstream OpenID clients can reuse the list directly.

### 3. Let Settings create and validate filesystem paths
- Switch to `DirectoryPath` with `Field(validate_default=True)` for `storage_data_dir` and `storage_documents_dir`.
- Add a post-init validator that ensures directories exist (create with `exist_ok=True`) and resolves them to absolute paths. With no backwards compatibility to maintain, we can fail fast if creation is impossible.【F:backend/api/settings.py†L102-L125】

### 4. Encode feature toggles as computed properties with validation
- Promote `oidc_enabled` to a validator-backed field that errors when partially configured instead of a property that silently returns `False`.
- Introduce `api_docs_enabled` and `dev_mode` booleans that drive swagger UI, debug mode, and other developer niceties directly, instead of scattering the toggles across the app.

### 5. Align docs, tests, and CLI ergonomics
- Update `.env.example`, deployment docs, and operational runbooks to reflect the renamed fields and nested env structure.
- Refresh `backend/tests/core/test_settings.py` to cover: directory creation, TTL parsing into timedeltas, list parsing for CORS/OIDC scopes, and validation errors for inconsistent OIDC setups.
- Add a `settings dump` CLI helper (or extend existing CLI) to print the effective configuration with secrets masked, demonstrating the new structure in a developer-friendly way.

## Execution roadmap
1. **Model rewrite:** Rename fields and apply the new types/validators in `backend/api/settings.py`, deleting the bespoke `cors_allow_origins_list` helper once list parsing is native.
2. **Call-site update:** Touch routers/services/middleware to consume the renamed attributes (`settings.server_public_url`, `settings.jwt.access_ttl`) and adjust dependency wiring as needed.
3. **Test + doc sweep:** Update unit tests, `.env.example`, and onboarding docs to reference the new names and highlight the flat `ADE_*` environment variables.
4. **Developer tooling:** Add the optional CLI/settings dump if we find gaps after the rename; otherwise verify `uvicorn` boot scripts and deployment manifests pick up the new env vars.
5. **Monitor + iterate:** After the rewrite, treat the consolidated `Settings` class as the single entry point—new config should follow the established naming/typing conventions by default.
