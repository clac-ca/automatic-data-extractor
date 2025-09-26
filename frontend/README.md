# ADE Frontend

This package houses the Automatic Data Extractor (ADE) web client. It uses [Vite](https://vitejs.dev/) with React and TypeScript in a conventional, minimal setup so new contributors can navigate the codebase quickly.

## Getting started

```bash
cd frontend
npm install
npm run dev
```

The development server runs on [http://localhost:5173](http://localhost:5173) by default.

## Available scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start the Vite development server. |
| `npm run build` | Type-check the project and create a production build. |
| `npm run preview` | Preview the production build locally. |
| `npm run lint` | Run ESLint across the TypeScript source files. |
| `npm run typecheck` | Type-check the project without emitting files. |
| `npm run test` | Execute the Vitest unit test suite. |
| `npm run test:watch` | Run Vitest in watch mode. |

## Directory structure

```text
frontend/
├─ src/            # React components and route definitions
├─ tests/          # Vitest + Testing Library test suites
├─ index.html      # Vite entry HTML
└─ vite.config.ts  # Vite configuration
```

## Next steps

- Replace the placeholder workspace data with real API responses once endpoints are available.
- Flesh out document upload flows with progress indicators and error handling.
- Expand the design system into reusable components as the application grows.
