# Contributing to ADE Web

ADE Web’s architecture is already documented in the `docs/` series (`01`–`10`) and the main `README.md`. This page is the fast “instant understanding” checklist to keep new contributions consistent with that architecture.

## Instant understanding checklist

- **Name everything after the domain.** Types stay singular and domain-specific (`Workspace`, `Run`, `Configuration`, `ConfigVersion`, `Document`). Hooks follow the same pattern (`useRunsQuery`, `useStartRunMutation`). Routes and labels stay 1:1: `/documents`, `/runs`, `/config-builder`, `/settings`. Feature folders mirror routes: `screens/workspace-shell/sections/{documents|runs|config-builder|settings}`.
- **Use the canonical homes.** Build routes via `@shared/nav/routes`. Keep query parameter names in sync with `docs/03`, `docs/06`, `docs/07` and the filter helpers they describe (`parseDocumentFilters`, `parseRunFilters`, `build*SearchParams`). Permission keys live in `@schema/permissions` and helpers in `@shared/permissions`.
- **Respect the layers.** Never import from an "upwards" layer (`shared/` or `ui/` must not import `screens/` or `app/`). ESLint will fail fast if you try.
- **Do not reinvent patterns.** Need a list/detail surface? Start from Documents or Runs. Need URL-backed filters? Copy the `useDocumentsQuery` + `parseDocumentFilters` pattern. Need NDJSON streaming? Use the existing helper and event model instead of rolling your own.

If you add a new concept, update the relevant numbered doc so others can discover it; `CONTRIBUTING.md` should stay small and point at the canonical sources above.
