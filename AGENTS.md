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
├─ AGENTS.md                  # You are here: authoritative agent playbook
├─ agents/                    # AI-facing work packages, glossaries, process docs
│  ├─ ADE_GLOSSARY.md
│  ├─ CURRENT_TASK.md         # Current work package in flight (rotate after completion)
│  ├─ PREVIOUS_TASK.md        # Archive of the most recently completed task
│  ├─ fastapi-best-practices.md
│  ├─ code_review_instructions.md
│  └─ WP_*.md                 # Long-form work packages coordinating refactors
├─ ade/                       # Deployable FastAPI package (API + CLI + workers + static web)
│  ├─ __init__.py
│  ├─ main.py                 # App factory; mounts v1 router; serves SPA/static files
│  ├─ lifecycles.py           # Startup/shutdown hooks (SQLite PRAGMAs, health checks, JWKS warmup)
│  ├─ api/
│  │  ├─ __init__.py
│  │  ├─ deps.py              # Shared dependencies (db session, current user/workspace)
│  │  ├─ errors.py            # Problem+JSON exception handlers
│  │  └─ v1/router.py         # API version router; includes feature routers
│  ├─ core/
│  │  ├─ __init__.py
│  │  ├─ auth_backends.py     # Entra ID helpers, JWKS cache, token verification
│  │  ├─ config.py            # Pydantic settings split into focused config objects
│  │  ├─ logging.py           # Structured logging configuration
│  │  ├─ security.py          # OAuth/OpenID utilities, password hashing helpers
│  │  ├─ time.py              # Timezone and UTC helpers
│  │  └─ utils.py             # Small, pure helpers shared across features
│  ├─ db/
│  │  ├─ __init__.py
│  │  ├─ base.py              # Declarative Base, ID/timestamp/workspace mixins
│  │  ├─ session.py           # Engine/session factories (SQLite dev, Postgres prod)
│  │  └─ migrations/          # Alembic environment and versioned migrations
│  ├─ features/
│  │  ├─ auth/
│  │  │  ├─ router.py         # /auth endpoints (login redirect, callback, whoami)
│  │  │  ├─ schemas.py        # Request/response models for auth flows
│  │  │  ├─ models.py         # Auth persistence (if needed)
│  │  │  ├─ repository.py     # DB queries for identities and tokens
│  │  │  ├─ service.py        # Auth orchestration, provisioning, token validation
│  │  │  └─ tests/            # Feature-scoped tests (API + service)
│  │  ├─ users/
│  │  │  ├─ router.py         # /users CRUD and profile management
│  │  │  ├─ schemas.py
│  │  │  ├─ models.py
│  │  │  ├─ repository.py
│  │  │  ├─ service.py
│  │  │  └─ tests/
│  │  ├─ workspaces/
│  │  │  ├─ router.py         # Workspace CRUD, membership operations
│  │  │  ├─ schemas.py
│  │  │  ├─ models.py
│  │  │  ├─ repository.py
│  │  │  ├─ service.py
│  │  │  └─ tests/
│  │  ├─ documents/
│  │  │  ├─ router.py         # Upload/download, metadata endpoints
│  │  │  ├─ schemas.py
│  │  │  ├─ models.py
│  │  │  ├─ repository.py
│  │  │  ├─ service.py        # Storage orchestration, virus scans, job enqueue
│  │  │  ├─ workers.py        # Background helpers for extraction jobs
│  │  │  └─ tests/
│  │  ├─ configurations/
│  │  │  ├─ router.py         # Configuration CRUD, validation
│  │  │  ├─ schemas.py
│  │  │  ├─ models.py
│  │  │  ├─ repository.py
│  │  │  ├─ service.py
│  │  │  └─ tests/
│  │  ├─ jobs/
│  │  │  ├─ router.py         # Job lifecycle endpoints (status, retry, list)
│  │  │  ├─ schemas.py
│  │  │  ├─ models.py
│  │  │  ├─ repository.py
│  │  │  ├─ service.py        # Processing orchestration logic
│  │  │  ├─ workers.py        # Worker entry points
│  │  │  └─ tests/
│  │  └─ system_settings/
│  │     ├─ router.py         # System settings CRUD, feature toggles
│  │     ├─ schemas.py
│  │     ├─ models.py
│  │     ├─ repository.py
│  │     ├─ service.py
│  │     └─ tests/
│  ├─ services/
│  │  ├─ __init__.py
│  │  ├─ storage.py           # Shared storage adapters (only if truly shared)
│  │  ├─ mailer.py            # Transactional email integrations (optional)
│  │  └─ cache.py             # Cache adapter abstraction
│  ├─ workers/
│  │  ├─ __init__.py
│  │  └─ run_jobs.py          # Process-level worker entry point
│  ├─ cli/
│  │  ├─ __init__.py
│  │  ├─ main.py              # `ade` CLI entry point (Typer/Click)
│  │  ├─ dev.py               # Developer utilities (seed, wipe, fixtures)
│  │  └─ admin.py             # Operational/administrative commands
│  └─ web/
│     ├─ index.html
│     └─ assets/              # Compiled SPA artefacts served by FastAPI
├─ tests/
│  ├─ conftest.py             # Shared fixtures (app, db, auth helpers)
│  ├─ test_api_health.py
│  └─ test_security.py
├─ docs/                      # Human-facing documentation
├─ frontend/                  # SPA source (React/Vite) prior to build
├─ scripts/                   # Helper scripts, packaging, build tooling
├─ alembic.ini
├─ pyproject.toml
├─ .env.example
└─ README.md
```

### Module Responsibilities (Cheat Sheet)

- **Features own their HTTP contract.** Keep routers, schemas, models, repositories, services, workers, and feature tests together.
- **`ade/api/` is a thin shell.** Limit it to version routing, shared dependencies, and exception mapping. Never move business logic here.
- **`ade/core/` hosts cross-cutting concerns.** Settings, auth backends, logging, security helpers, and pure utilities belong here.
- **`ade/db/` centralises persistence glue.** Declarative base, session management, and migrations stay together for easy engine swaps.
- **`ade/web/static/` contains built assets only.** Source files for the SPA remain under `frontend/`.
- **Shared integrations live in `ade/services/` only when two or more features need them.** Otherwise, keep code inside the owning feature to avoid premature abstraction.

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

---

## Dependencies

- **Default stance:** Stay in the standard library when a clear native solution exists.
- **Adopt a dependency only if it is** widely used, actively maintained, and materially improves clarity or safety.

### Migrations

- **Single baseline migration:** There are no production installations yet, so all schema work happens in
  `ade/alembic/versions/0001_initial_schema.py`. When the schema evolves, update this file directly instead of adding new
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

- When you modify anything under `frontend/`, run `npm test -- --watch=false` and `npm run build` to ensure the SPA both passes unit tests and builds successfully.

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
