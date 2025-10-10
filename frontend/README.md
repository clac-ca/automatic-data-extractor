# ADE Frontend

This directory contains the rebuilt ADE operator console. The stack is based on
Vite, React, TypeScript, Tailwind CSS, React Router, and TanStack Query. The
initial scaffold focuses on a dependable layout shell, deterministic data flow,
and a thin API client that can be expanded as features ship.

## Getting started

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on <http://localhost:5173>. Set `VITE_API_BASE_URL` in a
`.env` file to point at the FastAPI backend (defaults to `/api/v1`).

## Available scripts

| Command         | Description                                  |
| --------------- | -------------------------------------------- |
| `npm run dev`   | Start the Vite development server with HMR   |
| `npm run build` | Type-check and create the production bundle  |
| `npm run preview` | Preview the production bundle locally     |
| `npm run lint`  | Run ESLint with the shared project config    |

Add Vitest and story-based tooling when the first feature demands them.

## Project structure

```
frontend/
├─ index.html               # HTML entry point (fonts + meta tags)
├─ src/
│  ├─ app/                  # Application shell, router, and layouts
│  │  ├─ AppProviders.tsx   # React Query provider stack
│  │  ├─ AppRouter.tsx      # React Router configuration
│  │  └─ routes/            # High-level route components
│  ├─ shared/               # Environment utilities, API client, shared types
│  ├─ ui/                   # Future shared UI primitives live here
│  ├─ index.css             # Tailwind directives + global resets
│  └─ main.tsx              # Root render with providers + router
├─ tailwind.config.js       # Tailwind theme overrides (brand colours, shadows)
├─ postcss.config.js        # PostCSS pipeline for Tailwind + Autoprefixer
├─ tsconfig*.json           # TypeScript project references
└─ vite.config.ts           # Vite configuration (React plugin)
```

As features mature, keep code close to the owning feature folder to avoid
premature abstractions. Shared hooks and helpers should live under `src/shared`.

## Styling and design tokens

- Tailwind is configured with ADE brand colours and a reusable `shadow-soft`
  elevation token. Extend this file when additional spacing or typography scales
  are required.
- Global focus styles are exposed through the `.focus-ring` utility class. The shared primitives in `src/ui`
  (`Button`, `Input`, `FormField`, `Alert`) already consume it—mirror those patterns when adding more components.
- The shell layout demonstrates the navigation pattern: top bar (branding +
  secondary links), side navigation, and a constrained content container.
- Reusable loading/empty/error states live in `src/app/components/PageState.tsx`; wrap future route placeholders with this component for consistency.
- Workspace selection persists via local storage helpers in `src/shared/lib`, and shell breadcrumbs reflect the active route.

## API and configuration

`src/shared/api/client.ts` exposes a small `ApiClient` along with convenience
methods (`get`, `post`, `del`, `patch`). It automatically normalises the base
URL, attaches the CSRF token, and surfaces Problem Details in errors.

- `VITE_API_BASE_URL` — Base URL for the FastAPI application (`/api/v1` by default)
- `VITE_SESSION_CSRF_COOKIE` (optional) — Custom CSRF cookie name if it differs
  from `ade_csrf`

Additional environment helpers live in `src/shared/config/env.ts`.

## Next steps

- Replace placeholder routes with real feature implementations (setup, auth,
  workspaces, documents, jobs) and wire their data hooks.
- Extend the shared component library in `src/ui`/`src/app/components` with cards, modals, and tables as needed.
- Add Vitest when feature work introduces logic worth testing in isolation.

Keep the codebase boring, predictable, and easy to reason about. Favour small,
composable components and encapsulate data-fetching concerns in feature-specific
hooks backed by TanStack Query.
