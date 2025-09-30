# ADE frontend

This package hosts the rebuilt ADE web client. It focuses on the core authentication loop so we can validate the backend contracts end-to-end before layering additional product features.

## Available scripts

- npm run dev - start Vite locally on http://localhost:5173.
- npm run build - type-check and produce a production build.
- npm run lint - run ESLint with the project defaults.
- npm run test - execute Vitest in CI mode.

## Authentication flow

The login form posts credentials to POST /api/auth/login, expects cookies to be set by the backend, and then renders the authenticated dashboard. The dashboard fetches the current user via GET /api/auth/me on initial load and calls POST /api/auth/logout with the CSRF token when signing out.

## Project structure

- src/pages/LoginPage.tsx - accessible login form with client-side validation and server error handling.
- src/pages/DashboardPage.tsx - minimal authenticated landing page showing the signed-in account and a sign-out action.
- src/context/AuthContext.tsx - shared authentication state with bootstrap logic and helpers for API access.
- src/api/ - typed API helpers for authentication endpoints.
- src/pages/__tests__/ - smoke-level tests covering the login and sign-out flows.

Future frontend work should extend these foundations without reintroducing unused scaffolding or dependencies.
