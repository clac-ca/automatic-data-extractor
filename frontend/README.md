# ADE Frontend

The ADE frontend is a single-page React application built with Vite, TypeScript,
Tailwind CSS, React Router, and TanStack Query. It delivers the operator console
used to set up the platform, manage authentication, and navigate between
workspaces and document types. The behaviour, UX contract, and roadmap are
defined in [`agents/FRONTEND_DESIGN.md`](../agents/FRONTEND_DESIGN.md).

## Design principles

- **Predictable navigation.** Keep one primary action per screen, respect the
  workspace-first layout, and reuse common entry points (top bar, navigation
  rail, dialog patterns).
- **Accessible, standard components.** Prefer semantic HTML and Tailwind utility
  classes over custom widgets, with focus management handled by shared
  components.
- **Deterministic data flow.** Fetch server state through typed TanStack Query
  hooks and keep mutations isolated to feature directories. Cache invalidation
  happens at the feature boundary so related views stay in sync.
- **Boundary validation.** Validate input at form submission, surface inline
  errors, and let the backend remain the source of truth for permissions and
  business rules.

## Project structure

```
frontend/
├─ index.html              # Vite entry point served during development
├─ public/                 # Static assets copied as-is into the build output
├─ src/
│  ├─ ade/                 # Application shell (providers, router, error boundary)
│  ├─ features/            # Feature-first modules (auth, setup, workspaces, ...)
│  │  └─ workspaces/       # Workspace shell, overview, document type routes
│  ├─ shared/
│  │  ├─ api/              # API client, typed contracts, error helpers
│  │  ├─ components/       # Tailwind-based UI primitives
│  │  ├─ hooks/            # Cross-cutting hooks (local storage, media queries)
│  │  └─ utils/            # Formatting helpers and pure utilities
│  └─ test/                # Vitest suites and shared test helpers
├─ vite.config.ts          # Vite build configuration
├─ tailwind.config.ts      # Tailwind theme and plugin configuration
└─ tsconfig*.json          # TypeScript project references
```

Each feature folder owns its API hooks, components, routes, and Vitest coverage.
Cross-cutting primitives live under `src/shared/` to avoid circular dependencies
and keep imports explicit.

## Backend integration

- **HTTP client.** `src/shared/api/client.ts` wraps the browser `fetch` API to
  include credentials, parse JSON Problem Details, and apply the
  `VITE_API_BASE_URL` environment variable that points to the FastAPI backend.
- **Contracts.** TypeScript interfaces in `src/shared/api/types.ts` mirror the
  backend response models. Update these alongside backend changes to keep the
  SPA and API in lockstep.
- **Data fetching.** TanStack Query hooks (for example,
  `useSessionQuery`, `useWorkspacesQuery`, `useCreateWorkspaceMutation`) live in
  their feature directories and are responsible for caching, optimistic updates,
  and error handling.
- **Routing.** Authenticated routes rely on the session query to guard access and
  redirect unauthenticated users to `/login`. Workspace-aware routes read the
  active workspace from the selector and pass identifiers to feature hooks that
  call `/workspaces` and document-type endpoints.

## Development workflow

1. Install dependencies: `npm install`
2. Run the development server: `npm run dev`
   - The dev server listens on `http://localhost:5173` and proxies API calls to
     the origin defined by `VITE_API_BASE_URL` (defaulting to
     `http://localhost:8000`). Adjust this when the FastAPI backend runs on a
     different host or port.
3. Build for production: `npm run build`
4. Preview the production bundle: `npm run preview`

## Quality gates

When modifying frontend code, run both commands to keep CI parity:

- `npm run build` — Type-checks the project and emits the production bundle.
- `npm test -- --watch=false` — Executes the Vitest suite once in CI mode.

ESLint (`npm run lint`) is available for targeted linting during development.

## Testing philosophy

Vitest and Testing Library back component and hook tests. Prefer shallow
feature-level tests that exercise user flows, stubbing TanStack Query hooks or
API helpers only when external dependencies would make assertions brittle.

## Additional resources

- [`agents/FRONTEND_DESIGN.md`](../agents/FRONTEND_DESIGN.md) — Product
  specification and UX contract.
- [`agents/WP_FRONTEND_REBUILD.md`](../agents/WP_FRONTEND_REBUILD.md) — Delivery
  plan for ongoing frontend workstreams.
- [`AGENTS.md`](../AGENTS.md) — Repository-wide conventions and testing
  expectations.
