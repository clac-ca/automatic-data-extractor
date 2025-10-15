# ADE Frontend

This directory hosts a clean Angular 19 workspace generated with the Angular CLI. The project keeps the default structure so future contributors can rely on familiar conventions.

## Quick start

| Task | Command |
| --- | --- |
| Install dependencies | `npm install` |
| Start dev server | `npm start` |
| Run unit tests | `npm test` |
| Lint the project | `npm run lint` |
| Build for production | `npm run build` |

Visit `http://localhost:4200/` while the dev server is running to view the app. Changes in the `src/` directory trigger automatic reloads.

## Project layout

```
src/
  app/
    app.component.*          # Root component hosting the router outlet
    app.routes.ts            # Route table with /setup guard + shell children
    core/
      layout/                # AppShellComponent (header + collapsible workspace sidebar)
      setup/                 # Placeholder /setup guard (replace with service in later phases)
    features/
      setup/                 # First-run admin creation placeholder view
      settings/              # Global admin settings stub view
      workspaces/
        documents/           # Default workspace landing page stub
        configurations/      # Placeholder for workspace configuration views
        jobs/                # Placeholder for job monitoring
  index.html                 # Root document
  main.ts                    # Bootstraps the standalone app
  styles.scss                # Global styles
public/                      # Static assets copied as-is during builds

The workspace shell defaults to the fake workspace identifier `demo-workspace`. Update
`src/app/core/constants.ts` when the backend provides real workspace ids.
```

Generate additional components, routes, or services using standard Angular CLI schematics (for example `ng generate component feature/example`).

## Testing

Unit tests run through Karma and Jasmine:

```bash
npm test
```

The default configuration runs tests in Chrome Headless and watches for file changes. For one-off CI runs use `npm test -- --watch=false`.

Run Angular ESLint with:

```bash
npm run lint
```

> Unit tests run in Chrome Headless. If Chrome is not installed on your machine or CI
> runner, set the `CHROME_BIN` environment variable to the Chromium executable before
> running `npm test`.

## Building

Create an optimized production build with:

```bash
npm run build
```

Artifacts are emitted to `dist/frontend/`. Serve the contents of that directory through FastAPI or any static host.

## Further reading

Consult the [Angular CLI documentation](https://angular.dev/tools/cli) for details on available commands and recommended patterns.
