# Unified Settings Research Pack

This folder contains the research and UX blueprint artifacts used to implement the unified `/settings` admin console.

## Artifacts

- `source-log.md`: internet reference corpus and key takeaways.
- `pattern-matrix.md`: scored pattern inventory (findability, density, actions, deep-linking, mobile, accessibility).
- `ux-blueprint.md`: implementation-ready IA, route map, page templates, and interaction rules.
- `capture-checklist.md`: headed browser capture checklist for `admin.microsoft.com` and `entra.microsoft.com`.
- `qa-checklist.md`: verification scenarios for implementation and regression checks.

## Current status

- Unified settings shell implemented at `/settings` with dedicated settings sidebar.
- Entity list/detail routes implemented with route-driven full-page detail surfaces (no narrow right-side panes).
- Legacy `/organization/*` route entry removed from app routing.
- Legacy `/workspaces/:workspaceId/settings/*` section resolution removed (now unknown section).
- SSO setup popup flow preserved in Authentication settings.
