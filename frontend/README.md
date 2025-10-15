# ADE Angular frontend

This workspace hosts the in-progress Angular refactor described in [`agents/frontend_refactor_plan.md`](../agents/frontend_refactor_plan.md).
The scaffold now targets **Angular 19** standalone conventions so we can incrementally light up the
navigation shell, `/setup` onboarding, and workspace-first experience outlined in the plan.

## Quick start

| Task | Command |
| --- | --- |
| Install dependencies | `npm install` |
| Start dev server | `npm start` (aliases `ng serve`) |
| Run unit tests | `npm test` (watch) or `npm run test:ci` (headless, no watch) |
| Lint the project | `npm run lint` |
| Build for production | `npm run build` |

> ℹ️  Karma remains the default unit runner while we evaluate Jest migration options
> later in Phase 0. End-to-end coverage will be revisited once the navigation
> shell stabilises.

## Project structure

```
src/
  app/
    app.component.ts         # Bootstraps the router
    app.config.ts            # Global providers + router configuration
    app.routes.ts            # Route table with /setup guard + shell children
    core/
      layout/                # AppShellComponent (header + collapsible workspace sidebar)
      setup/                 # Placeholder /setup guard (replace with service in Phase 2)
    features/
      setup/                 # First-run admin creation placeholder view
      settings/              # Global admin settings stub view
      workspaces/
        documents/           # Default workspace landing page stub
    shared/                  # Reserved for shared UI primitives (empty for now)
    testing/                 # Reserved for TestBed helpers (empty for now)
  index.html
  main.ts
  styles.scss
```

As the refactor progresses each feature folder will grow into its own lazy-loaded route
with typed services and focused tests. The `shared` and `testing` directories are pre-created to
keep future contributions consistent with the plan.

## Roadmap alignment

Phase 0 focuses on reproducible tooling and a guarded `/setup` path. The workspace currently ships with:

- Angular 19 CLI scaffold pinned to Node 20 compatible tooling
- Placeholder `/setup` route protected by a stub `setupGuard`
- Shell layout stub that already honors the collapsible sidebar + default Documents navigation requirement
- Default workspace route that redirects `/workspaces/:id` (simulated) to Documents, ready for data wiring in later phases

Update progress and follow-on work directly in the work package as new milestones land.
