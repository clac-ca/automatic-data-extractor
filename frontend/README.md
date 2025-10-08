# ADE Frontend

This package hosts the ADE operator console. The single-page application is built
with Vite, React, TypeScript, Tailwind, and TanStack Query following the
architecture captured in [`agents/FRONTEND_DESIGN.md`](../agents/FRONTEND_DESIGN.md).

## Getting started

```bash
npm install
npm run dev
```

The development server listens on `http://localhost:5173` and forwards API calls
to the FastAPI backend. Configure the target origin with the `VITE_API_BASE_URL`
environment variable when the backend is not running on the same host/port.

## Scripts

| Command           | Description                                                 |
| ----------------- | ----------------------------------------------------------- |
| `npm run dev`     | Start Vite in development mode with hot module replacement. |
| `npm run build`   | Type-check the project and emit a production build.         |
| `npm run lint`    | Run ESLint using the shared configuration.                  |
| `npm run test`    | Execute the Vitest suite once in CI mode.                   |
| `npm run preview` | Preview the production bundle locally.                      |

## Project layout

```
src/
├─ app/                # Application shell (providers, router, error boundary)
├─ features/
│  ├─ auth/            # Session guard, login/logout flows, provider discovery
│  ├─ setup/           # First-run setup wizard and status polling
│  └─ workspaces/      # Workspace shell, overview, and document type detail
├─ shared/
│  ├─ api/             # API client, typed contracts, problem+JSON helpers
│  ├─ components/      # Tailwind-based UI primitives
│  ├─ hooks/           # Cross-cutting hooks (local storage, etc.)
│  └─ utils/           # Formatting helpers
└─ test/               # Vitest suites covering critical flows
```

## Routing map

- `/setup` — First-run setup wizard available only until an administrator exists.
- `/login` — Credential login plus SSO provider discovery; redirects to `/setup`
  if provisioning is still required.
- `/workspaces/:workspaceId` — Authenticated workspace overview with persistent
  navigation state.
- `/workspaces/:workspaceId/document-types/:documentTypeId` — Document type
  detail view with configuration drawer and status strip.
- `/logout` — Clears the current session before redirecting to `/login`.

## Data dependencies

The SPA expects the following backend endpoints:

- `GET /setup/status`, `POST /setup`
- `GET /auth/session`, `POST /auth/session`, `DELETE /auth/session`,
  `POST /auth/session/refresh`
- `GET /auth/providers`
- `GET /workspaces`
- `GET /workspaces/:workspaceId/document-types/:documentTypeId`

## Testing

Vitest and Testing Library power the component and hook tests. Run `npm run test`
to execute the suite. Tests mock TanStack Query hooks where appropriate to keep
assertions deterministic and focused on component behaviour.
