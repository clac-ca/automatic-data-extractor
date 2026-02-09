# Work Package: Standardize Health Endpoints

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Refactor ADE health checks to a standard, minimal, unversioned contract (liveness + readiness) that is API-only and infrastructure-friendly. Remove legacy health routes and update docs, CLI wait logic, and tests to match the new contract.

### Scope

- In:
  - Replace current health endpoints with standard unversioned paths and minimal JSON responses.
  - Remove versioned health route(s) and any old root health paths.
  - Update CLI startup health probe, tests, and docs to the new endpoints.
  - Clarify how probes should reach the API in single-container and split deployments.
- Out:
  - Backward compatibility or transitional routing.
  - Auth changes or broader API routing refactors beyond health endpoints.

### Work Breakdown Structure (WBS)

1.0 Health contract definition
  1.1 Standard endpoint names and payloads
    - [ ] Choose final paths (for example: /healthz and /readyz).
    - [ ] Define exact JSON response shapes for liveness and readiness.
    - [ ] Decide whether health endpoints appear in OpenAPI (default: no).
  1.2 Deletions and invariants
    - [ ] Confirm removal of /health, /ready, and /api/v1/health routes.
    - [ ] Confirm readiness checks only the database (no other dependencies).

2.0 Backend implementation
  2.1 Router changes
    - [ ] Update ops router paths and handlers to new endpoints.
    - [ ] Remove health router from the API v1 router.
  2.2 Response models
    - [ ] Simplify or replace HealthCheckResponse schema to match the new contract.
    - [ ] Ensure readiness returns 503 on DB failure and 200 otherwise.
  2.3 CLI startup gating
    - [ ] Update ade root CLI wait-for-API URL to the new liveness path.
  2.4 Tests
    - [ ] Update integration tests to new paths and response shapes.
    - [ ] Add/adjust tests for readiness failure behavior.

3.0 Deployment/proxy alignment
  3.1 Probe routing policy
    - [ ] Decide whether probes must hit the API port directly in single-container mode.
    - [ ] If direct probing is required, update compose docs to expose/target the API port.
    - [ ] If proxying via nginx is required, add explicit proxy rules for the new paths.

4.0 Documentation
  4.1 References and guides
    - [ ] Update admin/developer/reference docs to the new endpoint names and responses.
    - [ ] Update templates/snippets that reference old health endpoints.

### Open Questions

- Which naming convention should we standardize on: /healthz + /readyz or /health + /ready?
- Should health endpoints be excluded from OpenAPI (recommended) or documented there?
- Should liveness include any extra fields beyond a simple {"status": "ok"}?
- For single-container deployments, do we require probes to hit the API port directly, or should nginx proxy the health paths?

---

## Acceptance Criteria

- Liveness endpoint responds 200 with the new minimal JSON contract.
- Readiness endpoint responds 200 when the database is reachable and 503 when it is not.
- Old health endpoints are removed and no longer present in the app or OpenAPI.
- CLI startup health wait uses the new liveness endpoint.
- Docs and templates reference only the new health endpoints.
- Updated tests pass for the new paths and responses.

---

## Definition of Done

- WBS tasks completed and checked off.
- `ade api test` (or relevant test subset) runs cleanly.
- No references to old health endpoints remain in code or docs.
