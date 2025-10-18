The automatic-data-extractor (ADE) turns semi-structured spreadsheets and PDFs into clean, structured tables using deterministic, revision-controlled logic. This is the **only** `AGENTS.md` in the repository—treat it as the source of truth for every automation run.

This playbook explains how agents should interpret human instructions, how to interact with supporting material under `agents/`, and the target backend layout we are migrating toward.

---

## TL;DR for Agents

- **Read this file first.** If a user references any document in `agents/`, open it before touching code.
- **Honor the planned layout.** Every backend task assumes the feature-first structure documented below.
- **Keep changes boring.** Prioritise clarity, deterministic behaviour, and simple abstractions.
- **Follow the shared authentication guards.** All authenticated routes rely on the dependencies described in
  `docs/authentication.md` (`require_authenticated`, `require_global`, `require_workspace`, and `require_csrf`). Update that doc
  and this file whenever authentication flows or credential types change.

---

## Target Backend & Docs Layout

The tree below describes the desired state of the repo once the restructure is complete. Use it as a north star when creating or moving files.

```
.
├─ AGENTS.md                  # Authoritative agent playbook
├─ agents/                    # Work packages & process docs (CURRENT_TASK, PREVIOUS_TASK, WP_*.md, glossary)
├─ ade/                       # FastAPI backend (API, workers, CLI)
│  ├─ app.py                  # App factory mounting API + static assets
│  ├─ lifecycles.py           # Startup/shutdown hooks (DB bootstrap, runtime dirs, queue)
│  ├─ adapters/               # External connectors (queue + storage)
│  ├─ api/                    # HTTP shell (errors, settings dependency, v1 router, tests)
│  ├─ db/                     # SQLAlchemy base/session, Alembic migrations, tests
│  ├─ features/               # Vertical slices (auth, documents, jobs, users, etc.)
│  ├─ platform/               # Cross-cutting plumbing (config, logging, middleware, pagination, responses, schema, security)
│  ├─ tests/                  # Shared backend test helpers (e.g., login utility)
│  ├─ workers/                # Task queue abstraction + worker entrypoints/tests
│  └─ web/static/             # Compiled SPA assets served by FastAPI
├─ frontend/                  # React/Vite SPA source
│  ├─ package.json            # Frontend dependencies/scripts
│  ├─ public/                 # Static assets copied verbatim into the build
│  └─ src/
│     ├─ app/                 # App shell, layouts, file-based routing
│     │  ├─ AppProviders.tsx  # Shared React Query providers
│     │  ├─ root.tsx          # Root route wrapping the router outlet
│     │  ├─ entry.server.tsx  # Minimal SSR entry for Vite builds
│     │  └─ routes/           # File-based route modules (auth, workspaces, documents…)
│     ├─ features/            # Feature-driven UI modules (documents, jobs, workspaces, etc.)
│     ├─ shared/              # Cross-feature utilities (clients, hooks, types)
│     ├─ test/                # Vitest setup and helpers
│     └─ ui/                  # Reusable design system primitives
├─ docs/                      # Human-facing documentation (auth guide, admin guide, reference)
├─ scripts/                   # Automation and build tooling
├─ alembic.ini                # Alembic configuration pointing at ade/db/migrations
├─ pyproject.toml             # Python packaging + tooling configuration
├─ README.md                  # Project overview & developer onboarding
└─ .env.example               # Sample environment configuration
```

### Module Responsibilities (Cheat Sheet)

- **Features own their HTTP contract.** Keep routers, schemas, models, repositories, services, workers, and feature tests together.
- **`ade/adapters/` wraps external connectors.** Queue and storage adapters live here; features talk to them through thin wrappers.
- **`ade/api/` is a thin shell.** Limit it to version routing, shared dependencies, and exception mapping. Never move business logic here.
- **`ade/platform/` hosts cross-cutting concerns.** Settings, logging, security helpers, and pure utilities belong here.
- **`ade/db/` centralises persistence glue.** Declarative base, session management, and migrations stay together for easy engine swaps.
- **`ade/workers/` owns background execution.** Task queues and worker entrypoints live here; they depend on features, not the other way around.
- **`ade/web/static/` contains built assets only.** Source files for the SPA remain under `frontend/`.
- **`ade/tests/` provides cross-cutting helpers.** Feature-specific tests should stay co-located under `features/*/tests/`.
- **Frontend routes live under `frontend/src/app/routes/`.** React Router’s framework mode auto-discovers files—add new URLs by creating route modules there instead of resurrecting `AppRouter.tsx`. Do not maintain a manual manifest; the file system is the single source of truth.
- **Workspace chrome lives beside the dynamic workspace route.** Navigation, loader, and top bar components sit under `frontend/src/app/routes/workspaces/$workspaceId/` so every workspace screen shares the same boundary.

---

## Decision Heuristics

1. **Clarity first.** Prefer straightforward, discoverable solutions. Optimise readability and deterministic behaviour before performance.
2. **Pragmatic optimisation.** Improve throughput only when it delivers tangible value and the resulting code stays maintainable.
3. **Simplicity over cleverness.** Choose slower but safer implementations when high-complexity alternatives would create maintenance risk.

### Baseline Assumptions

- **Scale:** Internal line-of-business usage (not internet-scale).
- **Style:** Clear names, minimal abstractions, deterministic functions.
- **Trade-offs:** Reliability beats clever tricks. When in doubt, favour boring code that is easy to audit.

---

## Operating Modes

### Default Mode – Direct User Instructions

- Trigger: The user gives instructions without pointing to a specific work package.
- Playbook:
  1. Follow the latest user instructions verbatim.
  2. Apply the decision heuristics above.
  3. Ask for clarification only when instructions conflict or are ambiguous.

### Work Package Mode – `agents/*`

- Trigger: The user references one or more work packages under `agents/`.
- Playbook:
  1. Read every referenced document before writing code.
  2. Execute the scoped tasks exactly—no scope creep or speculative changes.
  3. Add or update deterministic tests/fixtures when relevant.
  4. Run all required quality gates (pytest, ruff, mypy, npm test/lint/typecheck, etc.).
  5. Update the referenced work package(s) with status notes. If you complete the active task in `agents/CURRENT_TASK.md`, move it to `agents/PREVIOUS_TASK.md` and draft the next actionable plan.

### Reference Study Ability – Temporary Library Sandbox

- Trigger: The user explicitly asks to vendor or explore an external open-source template or library for inspiration.
- Playbook:
  1. Create a throwaway subdirectory inside the repo (for example under `tmp/` or another clearly temporary folder) and scaffold the requested library or template using the official installation command.
  2. Treat the vendored code as read-only research material: document its location, avoid wiring it into the ADE build, and do not mutate the upstream files unless the user instructs otherwise.
  3. Analyse the imported project to capture architecture, patterns, and conventions that can inform ADE. Apply relevant lessons in the main codebase through focused follow-up changes.
  4. Remove the temporary subdirectory once it no longer provides value, or leave clear breadcrumbs in the docs/README so future contributors know why it exists and how to clean it up.

---

## Dependencies

- **Default stance:** Stay in the standard library when a clear native solution exists.
- **Adopt a dependency only if it is** widely used, actively maintained, and materially improves clarity or safety.

### Migrations

- **Single baseline migration:** There are no production installations yet, so all schema work happens in
  `ade/db/migrations/versions/0001_initial_schema.py`. When the schema evolves, update this file directly instead of adding new
  versioned migrations.

### Dependency Protocol

1. Add the requirement to `pyproject.toml` with explicit version pins.
2. Open a PR that introduces only the dependency change and explains why it is required.
3. Resume feature development once that PR lands.

This keeps dependency drift intentional and auditable.

---

## Testing Expectations

- Primary test runner: `pytest` (with `pytest-asyncio` for async tests).
- Async tests rely on `asyncio_mode="auto"`.
- Additional tools in use: Ruff (lint), MyPy (type checking with Pydantic plugin), optional `pytest-cov` for coverage.
- Tests live under `tests/` and follow the `test_*.py` / `test_*` naming convention.

Run the quality gates appropriate for the scope of your change set.

### Frontend-specific expectations

- When you modify anything under `frontend/`, run `npm test -- --watch=false` (Vitest jsdom suite) and `npm run build` to ensure the SPA both passes unit tests and builds successfully. Use `npm run test:coverage` when coverage metrics are required.
- Co-locate React tests beside the modules they exercise (for example `src/features/auth/__tests__`) and rely on `src/test/test-utils.tsx` for rendering so shared providers remain consistent.

---

## CHANGELOG expectations

- Maintain `CHANGELOG.md` using the [Keep a Changelog](https://keepachangelog.com/) structure already seeded in the repo.
- Update the `## [Unreleased]` section whenever you ship a behaviour change, workflow tweak, or documentation update that users or operators should know about. Examples include API changes, CLI flags, release automation adjustments, and notable bug fixes.
- File entries under the appropriate subsection (`### Added`, `### Changed`, `### Deprecated`, `### Removed`, `### Fixed`, `### Security`). Add the subsection if it does not yet exist beneath `## [Unreleased]`.
- Use short, imperative bullet points ("Add", "Fix", "Document") that describe the effect of the change—not the git diff.
- Only promote `## [Unreleased]` to a dated release when explicitly instructed. Use `scripts/finalize_changelog.py` to roll the unreleased notes into a tagged version and regenerate the empty `Unreleased` skeleton.
- Never manually duplicate, rename, or otherwise "roll" the `Unreleased` heading—running `scripts/finalize_changelog.py` automatically moves the section into the new release and restores a fresh `Unreleased` template.

## Guiding Principle

> **Consistency, clarity, and pragmatism beat cleverness.**

Structure code so every developer can quickly find what they need. Keep routes and dependencies simple, lean on FastAPI and Pydantic idioms, validate at the boundaries, and rely on tooling (Ruff, Alembic, MyPy) to enforce consistency. Spend your energy on business logic rather than reinvention.
