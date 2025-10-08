# ADE Frontend

This package contains the operator console for ADE. The app is a Vite + React +
TypeScript single-page application that consumes the REST contracts defined in
`agents/FRONTEND_DESIGN.md`. TanStack Query handles data fetching and caching.

## Getting started

```bash
npm install
npm run dev
```

The development server defaults to `http://localhost:5173` and proxies API
requests to the FastAPI backend exposed at `VITE_API_BASE_URL` (defaults to the
same origin).

## Scripts

| Command            | Description                                              |
| ------------------ | -------------------------------------------------------- |
| `npm run dev`      | Start Vite in development mode with hot module reload.    |
| `npm run build`    | Type-check and emit the production build.                 |
| `npm run lint`     | Run ESLint across the project.                            |
| `npm run test`     | Execute the Vitest suite in CI mode.                      |
| `npm run preview`  | Preview the production build locally.                     |

## Project layout

```
src/
├─ app/                # Application shell, providers, router
├─ features/
│  ├─ auth/            # Session management, login, logout, guards
│  ├─ setup/           # First-run setup wizard and status polling
│  └─ workspaces/      # Workspace shell, overview, document type detail
├─ shared/
│  ├─ api/             # API client wrapper, types, query keys
│  ├─ components/      # Tailwind-based UI primitives
│  └─ hooks/           # Cross-cutting React hooks
```

## Routing map

- `/setup` — Initial setup wizard that provisions the inaugural administrator.
- `/login` — Credential and SSO login surface with provider discovery.
- `/workspaces/:workspaceId` — Authenticated workspace overview.
- `/workspaces/:workspaceId/document-types/:documentTypeId` — Document type
  detail with configuration drawer.
- `/logout` — Clears the session then redirects back to `/login`.

## Data dependencies

The frontend relies on the following endpoints:

- `GET /setup/status`, `POST /setup`
- `GET /auth/session`, `POST /auth/session`, `DELETE /auth/session`
- `GET /auth/providers`
- `GET /workspaces`, `GET /workspaces/:workspaceId`
- `GET /workspaces/:workspaceId/document-types/:documentTypeId`
- `GET /configurations/:configurationId`

## Testing

Vitest and Testing Library power the component tests. Run `npm run test` to
execute the suite. Tests render components inside a TanStack Query client using
the helpers in `src/test/test-utils.tsx`.
