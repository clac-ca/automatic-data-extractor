# ADE Frontend

This package bootstraps the Automatic Data Extractor (ADE) frontend using Vite, React, TypeScript, and the shared tooling described in `FRONTEND_DESIGN.md`.

## Getting started

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on [http://localhost:5173](http://localhost:5173) by default.

## Available scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start the Vite development server. |
| `npm run build` | Type-check the project and produce an optimized production build. |
| `npm run preview` | Preview the production build locally. |
| `npm run lint` | Run ESLint using the project TypeScript configuration. |
| `npm run typecheck` | Run the TypeScript compiler in no-emit mode. |
| `npm run test` | Execute unit tests with Vitest. |
| `npm run test:watch` | Start Vitest in watch mode. |
| `npm run playwright:test` | Placeholder for future Playwright smoke tests. |

## Directory structure

```text
frontend/
├─ public/           # Static assets served by Vite
├─ src/
│  ├─ app/           # Application shell, routing, providers
│  ├─ api/           # API client wrappers and React Query hooks
│  ├─ components/    # Reusable UI primitives
│  ├─ pages/         # Route-level views
│  └─ styles/        # Global design tokens and CSS utilities
└─ tests/            # Vitest and Testing Library-based tests
```

## Next steps

- Replace mocked API responses with real `fetch` calls once authentication is wired.
- Implement the authentication screens and workspace switching experience.
- Add real styling and theming based on the design system decisions.
