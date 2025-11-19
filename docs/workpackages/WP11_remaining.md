# WP11 Remaining Work — Frontend Screen-First Refactor

> **Before touching this work package, read `apps/ade-web/AGENTS.md` in full.** It explains the routerless mental model, folder contracts, and navigation expectations we must follow.

The routerless refactor is partially landed. The items below close the gaps so the new screen-first layout, navigation helpers, and Config Builder UX are production ready. Work through the sections sequentially; each checkbox should end up green.

## A. Structure & Module Layout
- [x] **Config Builder adapters & boundaries.** Either move `apps/ade-web/src/screens/Workspace/api/adapters/*` into `screens/Workspace/sections/ConfigBuilder/adapters/` or re-export them behind a stable alias (`@screens/Workspace/sections/ConfigBuilder/adapters`). Update every consumer (e.g., `components/Workbench.tsx`, `hooks/useEditorState.ts`, `state/editorStore.ts`) so no file reaches back into `../api/adapters`.
- [x] **Replace `views/` with co-located modules.** Split the monolithic `views/ConfigDetail.tsx` into `panels/`, `components/`, and `types/` inside `sections/ConfigBuilder/`. Extract `ConfigHeader`, `ManifestPanel`, `ValidationPanel`, and helper types so the directory tree matches `components/`, `panels/`, `hooks/`, `state/`, `editor/`, `api/`, `adapters/`, `types/`.
- [x] **Config Builder entry screen.** `sections/ConfigBuilder/index.tsx` still renders a placeholder “No configurations available yet” block even when data exists. Replace it with a real configurations index (list view + “create/open” affordances) and ensure it stays within the section folder.
- [x] **Documents section parity.** Move `sections/Documents/views/DocumentDetail.tsx` under `sections/Documents/components/DocumentDetail.tsx` and align imports. Remove any stale `views/` folder left behind.
- [x] **Workspace nav slug alignment.** The workspace section resolver and nav still use the `/workspaces/:id/configs` slug. Update `WorkspaceNav`, `defaultWorkspaceSection`, and `resolveWorkspaceSection` to use `/config-builder` so URLs line up with the `ConfigBuilder` folder name and the work package spec. Add redirect handling for legacy `/configs` URLs if needed.
- [x] **Curated schema exports.** Established `apps/ade-web/src/schema/` with re-exports sourced from `@generated-types/openapi` (SessionEnvelope, WorkspaceProfile, UserSummary, etc.) so screens import via `@schema` only.
- [x] **UI primitives naming.** The spec calls for folder-based primitives (`ui/Button/`, `ui/Input/`, etc.). Normalize the existing lowercase files (`button.tsx`, `input.tsx`, `select.tsx`, `alert.tsx`, `code-editor.tsx`, `form-field.tsx`) into PascalCase subfolders with an `index.ts` barrel so imports become `@ui/Button` / `@ui/Input` / …. Update all callers to use the new paths.

## B. Navigation & Hosting
- [x] **Screen switch coverage.** Add unit tests that exercise `normalizePathname` and the screen routing matrix in `apps/ade-web/src/app/App.tsx`. Include assertions for `/`, `/login`, `/auth/callback`, `/setup`, `/workspaces`, `/workspaces/:id`, `/workspaces/:id/config-builder`, `/workspaces/:id/config-builder/:configId/editor`.
- [x] **Workspace section resolver tests.** Cover `resolveWorkspaceSection` in `screens/Workspace/index.tsx`, including redirects to the default section, slug fallbacks, config editor paths, and hash/search propagation.
- [x] **Testing utilities.** Update `apps/ade-web/src/test/test-utils.tsx` so every render helper wraps components in `<NavProvider>`. Adjust existing tests to remove bespoke wrappers.
- [x] **History regression tests.** Extend `apps/ade-web/src/app/nav/__tests__/urlState.test.tsx` (or add a sibling) to push multiple history entries, dispatch `popstate`, and assert `useLocation()` reflects pathname/search/hash changes.
- [x] **FastAPI SPA fallback.** Add a regression test around `apps/ade-api/src/ade_api/web/spa.py` (or manual verification notes) confirming `/workspaces/<id>/config-builder` refreshes return `index.html` while `/api/*` stays server-handled.
- [ ] **Legacy path redirects (optional).** If historic URLs such as `/configurations/:id` exist, document the redirect plan or implement a lightweight mapping in `ScreenSwitch`.

## C. Router Cleanup & Import Hygiene
- [x] **Dependency sweep.** Confirm `react-router`, `@react-router/dev`, and `@react-router/fs-routes` are removed from every `package.json`. Delete unused router-specific scripts (e.g., `npm run routes:frontend`) if they no longer make sense.
- [x] **Import audit.** Run `rg "react-router" apps/ade-web/src` and ensure zero matches. Also check for old relative paths referencing `app/routes` or `../../routes`. Update offenders to use the new aliases (`@app/nav/*`, `@screens/*`).
- [x] **Alias parity.** Updated `tsconfig.json`, `tsconfig.app.json`, `vite.config.ts`, and `vitest.config.ts` to expose `@app`, `@screens`, `@ui`, `@shared`, `@schema`, `@generated-types`, and `@test` aliases explicitly; document future alias additions alongside these files.
- [x] **Schema import guard.** Added ESLint `no-restricted-imports` for `@generated-types/openapi` so UI code leans on the curated `@schema` re-exports.
- [x] **README cleanup.** Rewrite `apps/ade-web/README.md` so it no longer references Remix/React Router templates. Highlight the history-based nav, screen-first folder layout, and path aliases.

## D. Tabs Primitive & A11y
- [x] **Adopt `@ui/Tabs` everywhere.** Replace bespoke tab controls (e.g., the editor tab strip in `EditorSurface.tsx`, segmented controls in workspace settings) with `TabsRoot`/`TabsList`/`TabsTrigger`/`TabsContent`.
- [x] **Keyboard interaction.** Enhance `@ui/Tabs/Tabs.tsx` to support roving `tabIndex` and arrow-key/Home/End navigation per WAI-ARIA Authoring Practices.
- [x] **Unit tests.** Add Vitest + Testing Library coverage that asserts the shared tabs render correct roles/attributes and respond to keyboard interaction. Exercise at least one consumer (Config Builder console panel) to ensure integration parity.

## E. Config Builder UX & URL Schema
- [x] **Workbench foundation reset.** Remove the legacy editor implementation and ship the new VS Code–style workbench scaffold (Explorer, Editor, Output panel, Inspector) with collapsible/resizable regions and stubbed data so future work can layer in real adapters.
- [x] **URL contract.** Document and implement the shareable query params for the builder (e.g., `?tab=scripts&pane=validate&file=/src/ade_config/hooks.py&view=split`). Extend `@app/nav/urlState.ts` helpers and write tests for parse/serialize round-trips.
- [x] **Unsaved-changes guard.** Track dirty state across the new workbench and prompt on internal navigation (`useNavigate`) and `beforeunload`. Cover confirm/dismiss flows with unit tests.
- [x] **Monaco lazy loading.** Ensure the Monaco editor bundle only loads on demand (dynamic `import()` + suspense boundary). Record the pre/post bundle size or add a check in CI to guard against regressions.
- [x] **Workbench panel integration.** Wire the output panel and inspector to real validation/test adapters once they return, replacing the current placeholder content.
- [x] **Editor tab parity.** Restore persisted tab sets, dirty tracking tied to the guard, and keyboard affordances once backend save flows exist.

> **Current query params:** `file=<config-relative-id>`, `pane=console|validation`, `console=open|closed`. These values drive the explorer selection, bottom panel tab, and output visibility while staying backward-compatible with legacy `pane=logs|problems` URLs.

## F. Documentation & Messaging
- [x] **NotFound copy.** Update `screens/NotFound/index.tsx` to reference the screen-first folder layout instead of `app/routes`.
- [x] **Work package log.** Keep this checklist in sync as tasks complete—note decisions around schema exports, legacy redirects, and bundle budgets.
  - 2025-11-12: Normalized UI primitives into PascalCase folders with barrel exports so imports consistently use `@ui/<Component>`.
  - 2025-11-13: Removed the legacy React Router CLI/script, cleaned `.react-router` ignores, and documented that `rg "react-router"` returns no matches.
  - 2025-11-14: Adopted the shared Tabs primitive across the editor and workspace settings, added keyboard navigation, and covered the component with focused Vitest suites.
  - 2025-11-15: Broke the Config Builder detail experience into co-located components/panels, moved the console to `panels/`, and replaced the placeholder index with a real configurations list + creation form.
  - 2025-11-16: Added SPA fallback coverage, codified the Config Builder URL contract with query helpers/tests, enforced unsaved-change prompts, and lazy-loaded Monaco behind a suspense boundary.
  - 2025-11-17: Rebuilt the Config Builder editor from scratch with a VS Code–style workbench foundation; re-opened the URL schema, unsaved-change guard, and panel integration tasks for the new layout.
  - 2025-11-18: Refactored the workbench foundation into modular explorer/editor/panel components with injectable seeds to prep for real adapters.
  - 2025-11-19: Wired the workbench to the documented query params, added navigation/blocking tests, and reinstated unsaved-change prompts for the rebuilt editor.
- 2025-11-20: Replaced the stubbed workbench data with live config listings + file fetches, rendering explorer trees and editor tabs from the API while keeping output/inspector placeholders for follow-up wiring.
- 2025-11-21: Hooked the workbench header and bottom panel into the validation API, surfaced file metadata in the inspector, and noted that console streaming will activate once backend routes land.
- 2025-11-22: Persisted workbench tab sets per workspace, added Ctrl+Tab / Ctrl+W shortcuts, and wired the editor guard to the stored state.

## G. Quality Assurance
- [x] **Automated tests.** `npm run test` should pass locally with the new navigation and tabs coverage.
- [ ] **Full CI.** `ade ci` must be green. Resolve or document the existing Ruff backend lint errors so the pipeline is actionable.
- [ ] **Manual QA.** Verify direct navigation + refresh for `/login`, `/auth/callback`, `/workspaces`, `/workspaces/:id/overview`, `/workspaces/:id/config-builder`, `/workspaces/:id/config-builder/:configId`, and `/workspaces/:id/config-builder/:configId/editor`. Confirm history back/forward works, Config Builder query params restore state, tabs obey keyboard navigation, and unsaved-change guards trigger appropriately.
