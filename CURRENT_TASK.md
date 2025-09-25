# FastAPI Request Body Parsing Alignment – Implementation Plan

## Objective
Replace manual `request.json()` parsing in FastAPI routes with typed Pydantic payloads so handlers rely on FastAPI's body parsing and validation pipeline.

## Rationale
- Restores automatic 422 validation responses and dependency caching.
- Eliminates duplicated JSON handling logic across modules.
- Aligns with the repository's FastAPI best-practice guidance for clarity and maintainability.

## Scope
1. **Identify impacted routes**  
   Audit `backend/api/modules/**/router.py` for handlers that read the request body from `Request` rather than accepting a payload parameter.
2. **Define request schemas**  
   For each route, either reuse existing Pydantic models or introduce new ones in the appropriate module package (e.g., `schemas.py`) so the payload structure is explicit.
3. **Update route signatures**  
   Modify handlers to accept the schema instance directly, remove manual JSON parsing, and pass typed fields to services.
4. **Adjust services/tests**  
   Update service methods, fixtures, and tests to consume the new typed inputs. Ensure no callers rely on the old raw-dict shape.
5. **Documentation**  
   Capture the new pattern in `fastapi-best-practices.md` or module docs if adjustments are noteworthy for future contributors.

## Deliverables
- Cleaned route handlers using FastAPI's body parsing.
- Corresponding schema definitions and updated service signatures.
- Updated unit/integration tests covering the revised handler behaviour.
- Documentation notes highlighting the standard approach for payload parsing.

## Testing & Verification
- Run `pytest`, `ruff`, and `mypy` for backend modules.
- Hit representative endpoints (via existing tests or manual smoke checks) to confirm 422 errors surface correctly for invalid payloads.

## Out of Scope
- Broader refactors unrelated to request parsing (e.g., auth workflow changes, response model adjustments) unless required by the new payload schemas.
- Converting query/path parameter handling unless they also misuse manual parsing.
