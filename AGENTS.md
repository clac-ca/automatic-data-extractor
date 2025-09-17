# AGENTS — Automatic Data Extractor

This file is the quick-start for coding agents. Pair it with `README.md` (human overview) and `ADE_GLOSSARY.md` (terminology).

---

## Quick facts

- **Mission** – Turn semi-structured spreadsheets and PDFs into deterministic tables with snapshot-controlled logic.
- **Packaging** – Ship everything as one Docker container with a FastAPI backend, Python processing engine, and Vite + TypeScript frontend.
- **Persistence** – Use SQLite at `var/ade.sqlite` and store uploaded documents under `var/documents/`. Keep both out of version control.
- **Priorities** – Determinism, debuggability, and simple operations beat raw throughput.

---

## Repository status

- The repo currently contains documentation only. Backend, frontend, and infra directories are not yet scaffolded.
- Follow the planned layout in `README.md` when creating new code. Create directories as needed.
- Update `AGENTS.md`, `README.md`, and the glossary whenever architecture or workflows change.

---

## Collaboration workflow

- We coordinate upcoming work through `CURRENT_TASK.md`. That file always contains the next build we plan to implement and the agreed definition of done.
- When refining a plan, update `CURRENT_TASK.md` in place. Once a plan is executed, clear or replace its contents before queuing the next task.
- Mention any new or revised task scope here in `AGENTS.md` so future agents know where to look.
- The current focus is **“Bootstrap the backend foundation”** as described in `CURRENT_TASK.md`.

---

## Architecture guide

- **Backend** – Python 3.11 with FastAPI and Pydantic v2. Keep extraction logic in pure functions (no I/O, randomness, or external calls). Put orchestration and persistence under `backend/app/services/` and processing utilities under `backend/processor/`.
- **Frontend** – Vite + React with TypeScript. Use functional components, strict TypeScript settings, and place API wrappers in `frontend/src/api/`.
- **Snapshots & runs** – Treat published snapshots as immutable. Allow runs to execute multiple snapshots so the UI can compare manifests side-by-side. Persist manifests and snapshot payloads as JSON.
- **Authentication** – Support username/password by default. Optional SSO (SAML or OIDC) can be added later. Admins issue API keys tied to user roles.
- **Storage** – Default to SQLite unless volume demands a change. Mount `./var` when running in Docker to persist the database and documents.

---

## Local development checklist

1. **Backend** – Create a Python 3.11 virtualenv and install dependencies via `pip install -r requirements.txt` (add the file when dependencies exist). Run `uvicorn backend.app.main:app --reload` for local API development.
2. **Frontend** – Inside `frontend/`, run `npm install` then `npm run dev`. The UI expects the backend at `http://localhost:8000`.
3. **Docker** – Provide a combined workflow via `docker compose up` that builds the app and mounts `./var` for persistence.
4. **Environment variables** – Use `.env` files that are gitignored for secrets (DB paths, SSO settings, API key salts, etc.).

---

## Quality and testing

Run the checks that match your changes:

```bash
pytest -q          # Backend tests
ruff check         # Python linting
mypy               # Python type checks
npm test           # Frontend unit tests
npm run lint       # Frontend linting
npm run typecheck  # Frontend type checks
```

- Documentation-only updates generally skip these commands; note the skip in your report.
- Add new tests alongside new features. Prefer deterministic fixtures stored under `examples/`.

---

## Data and security notes

- Treat `var/ade.sqlite` and everything in `var/documents/` as sensitive. Never commit their contents.
- Redact or hash personal data before logging.
- Enforce role-based access control on every endpoint. API keys inherit user scopes.

---

## Git workflow expectations

- Keep commits focused with descriptive messages (e.g., `backend: add snapshot publish route`).
- Ensure `git status` is clean before finishing.
- After committing, always call the `make_pr` tool to record the PR summary.
- Document architectural assumptions or open questions in the PR body so future contributors understand the decision.

---

When in doubt, favour simple, auditable solutions over premature abstractions, and record new findings here for the next agent.
