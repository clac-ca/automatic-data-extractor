# Work Package: Version Reporting Refresh (API + Web)

Guiding Principle:
Make ADE a clean, unified, and easily operable system with one backend distribution, clear shared infrastructure, and a simple default workflow that still allows each service to run independently.


> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Update version reporting to reflect the unified backend distribution name (`automatic-data-extractor`) and align the API response schema + frontend UI with a more standard representation.

Locked decision:

- Versions response shape: simple string fields `backend`, `engine`, `web`.
- Web version source: generated from `frontend/ade-web/package.json` at build time and exposed via a small `version.json` file; API reads it and falls back to `unknown` if missing.
- Web version file path: `/usr/share/nginx/html/version.json` inside the image (API reads from there by default).

### Scope

- In:
  - Update API version reporting to use the unified backend distribution.
  - Update OpenAPI schema + generated types if needed.
  - Update frontend version display to match new fields.
- Out:
  - New endpoints beyond the current versions endpoint.
  - Changes to ade-engine version retrieval logic beyond naming alignment.

### Work Breakdown Structure (WBS)

1.0 Backend version reporting
  1.1 Define new version fields
    - [x] Update backend models/schemas and endpoint logic.
  1.2 Wire unified distribution name
    - [x] Use `automatic-data-extractor` for backend version lookup.
    - [x] Keep ade-engine reporting intact.
  1.3 Add web version source
    - [x] Generate `version.json` from frontend package metadata during build.
    - [x] Read `version.json` in the API (fallback to `unknown` when absent).
    - [x] Default to `/usr/share/nginx/html/version.json` with an override env var if needed.

2.0 Frontend updates
  2.1 Types + UI
    - [x] Regenerate OpenAPI types if needed.
    - [x] Update frontend version UI to display new fields.

3.0 Compatibility
  3.1 Adjust docs + tests
    - [x] Update docs referencing version fields.
    - [x] Update any tests expecting old version response shape.

### Open Questions

- None.

---

## Acceptance Criteria

- Versions endpoint reports the unified backend distribution name.
- Frontend version display matches the updated API response.
- Tests and docs updated for the new response shape.

---

## Definition of Done

- API and frontend are in sync on version naming.
- No references to old version field names remain.
