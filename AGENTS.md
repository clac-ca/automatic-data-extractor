# AGENTS — Automatic Data Extractor

This guide captures the conventions and working agreements for coding agents. Pair it with `README.md` for the human-focused overview.

---

## Quick orientation

- **Goal** – Turn semi-structured spreadsheets and PDFs into deterministic tables using snapshot-based logic.
- **Packaging** – One Docker container bundles a FastAPI backend, Python extraction engine, and Vite + TypeScript frontend.
- **Persistence** – SQLite at `var/ade.sqlite` plus documents under `var/documents/`.
- **Priorities** – Determinism, easy debugging, and simple operations outrank raw throughput.

---

## Repository layout (planned)

```
backend/   # FastAPI app + processing engine
frontend/  # Vite + TypeScript UI
infra/     # Dockerfile, docker-compose.yaml, deployment helpers
examples/  # Sample documents used in tests and demos
runs/      # Example manifest outputs
var/       # Local persistence (gitignored)
```

Missing folders mean the implementation has not been scaffolded yet; follow this structure when adding code.

---

## Environment setup

### Backend

1. Use Python 3.11.
2. Create a virtual environment.
3. Install dependencies with `pip install -r requirements.txt` (add the file if missing).
4. Run the API with `uvicorn backend.app.main:app --reload`.
5. Defaults point to SQLite at `var/ade.sqlite` and documents in `var/documents/`.

### Frontend

1. Use Node.js 20 or newer.
2. Inside `frontend/`, run `npm install`.
3. Start the dev server with `npm run dev` (expects the backend at `http://localhost:8000`).

### Docker workflow

- `docker compose up` builds and runs the combined container from the repo root.
- Mount `./var` to persist the database and uploaded documents.

---

## Tests and quality checks

Run the commands that apply to your changes:

```bash
pytest -q          # Backend tests
ruff check         # Python linting
mypy               # Python type checks
npm test           # Frontend unit tests
npm run lint       # Frontend linting
npm run typecheck  # Frontend type checks
```

Documentation-only updates normally skip these checks; call that out in your report.

---

## Coding guidelines

### Python

- Target Python 3.11 and FastAPI with Pydantic v2.
- Type-hint everything; enable `from __future__ import annotations` when helpful.
- Keep processing logic pure—no network calls, randomness, or disk writes during a run.
- Centralise orchestration and persistence in `backend/app/services/` or `backend/processor/` modules.
- Format with Ruff (formatter + import sorting).

### Frontend

- Use functional React components with hooks.
- Enable strict TypeScript options; avoid `any`.
- Keep REST calls in `frontend/src/api/` as thin wrappers.
- Co-locate component styles (CSS Modules or styled components).

### Documentation

- Optimise for clarity and step-by-step instructions.
- Use sentence-case headings.
- Align terminology with `ADE_GLOSSARY.md`.

---

## Working with snapshots and runs

- Published snapshots are immutable—clone to a new draft for changes.
- Store detection, transformation, and validation logic as deterministic callables with digests for audit.
- Allow runs to reference multiple snapshot IDs so the UI can compare manifests across versions.
- Persist manifests and snapshots as JSON payloads; prefer additive schema changes.

---

## Data and security practices

- Treat the SQLite file and `var/documents/` as sensitive. Never commit their contents.
- Keep secrets out of source control; rely on environment variables or ignored `.env` files.
- Redact or hash personal data before logging.
- Enforce role-based access control on every endpoint and ensure API keys inherit user scopes.

---

## Git and PR workflow

- Use focused commits with descriptive messages (`<area>: <summary>` works well).
- Confirm a clean working tree before finishing (`git status`).
- Run applicable tests and note any that were skipped with a justification.
- PR descriptions should summarise user-facing impact, technical highlights, and testing results.
- After committing changes, call the `make_pr` tool to generate the PR message.

Document architectural assumptions or open questions in the PR body so future contributors understand the decision path.
