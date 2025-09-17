# Agent Guide — Automatic Data Extractor

This document gives coding agents the context needed to work effectively inside the ADE repository. Pair it with `README.md` for the human-friendly overview.

---

## Project snapshot

- **Purpose** – Turn semi-structured spreadsheets and PDFs into deterministic tabular data using snapshot-based logic.
- **Packaging** – One Docker container that bundles a FastAPI backend, Python extraction engine, and Vite + TypeScript frontend.
- **Storage** – SQLite database at `var/ade.sqlite` plus a `var/documents/` directory for uploaded files and exports.
- **Design priorities** – Determinism, debuggability, and ease of operation outweigh raw throughput or multi-tenant scale.

---

## Repository layout (planned)

```
backend/   # FastAPI app + processing engine
frontend/  # Vite + TypeScript UI
infra/     # Dockerfile, docker-compose.yaml, deployment scripts
examples/  # Sample documents used in tests and demos
runs/      # Example manifest outputs
var/       # Local persistence (gitignored)
```

Missing folders simply mean the implementation has not been scaffolded yet.

---

## Local development

### Backend

1. Create a virtual environment with Python 3.11.
2. Install dependencies: `pip install -r requirements.txt` (file to be added when backend is scaffolded).
3. Run the API: `uvicorn backend.app.main:app --reload`.
4. Default settings assume SQLite at `var/ade.sqlite` and documents under `var/documents/`.

### Frontend

1. Use Node.js 20+.
2. Install dependencies: `npm install` inside `frontend/`.
3. Start the dev server: `npm run dev` (expects the backend at `http://localhost:8000`).

### Docker workflow

- Use `docker compose up` in the repo root to build and run the combined container.
- Mount the `./var` directory for persistence across restarts.

---

## Tests and quality checks

Run the relevant commands before sending work for review:

```bash
pytest -q          # Backend tests
ruff check         # Python linting
mypy               # Python type checks
npm test           # Frontend unit tests
npm run lint       # Frontend linting
npm run typecheck  # Frontend type checks
```

Documentation-only changes generally do not require running the test suite, but mention this explicitly in your final report.

---

## Style guidelines

### Python

- Target Python 3.11 and FastAPI with Pydantic v2.
- Prefer type hints everywhere; enable `from __future__ import annotations` where useful.
- Keep processing logic pure: no network calls, random seeds, or disk writes during a run.
- Use dependency injection for services and keep business logic inside `services/` or `processor/` modules.
- Format with Ruff (uses the Ruff formatter) and keep imports sorted via Ruff.

### Frontend

- Use functional React components with hooks.
- Enable strict TypeScript settings; define explicit types instead of relying on `any`.
- Keep API calls in `frontend/src/api/` as thin wrappers around the REST endpoints.
- Co-locate component-specific styles (CSS Modules or styled components) with the component.

### Documentation

- Optimise for clarity and step-by-step guidance.
- Use sentence-case headings and plain language.
- Keep terminology aligned with `ADE_GLOSSARY.md`.

---

## Working with snapshots

- Snapshots are immutable once published. Create a new draft when adjusting logic.
- Store detection, transformation, and validation code as deterministic callables that return predictable results.
- Snapshot manifests and payloads are JSON; prefer additive schema changes and maintain backward compatibility where possible.
- Comparison runs should accept multiple snapshot IDs and surface manifest diffs in both the UI and API responses.

---

## Data & security practices

- Treat the SQLite database and documents directory as sensitive; never commit their contents.
- Avoid embedding secrets in the repo. Use environment variables or `.env` files ignored by Git.
- When writing new processing logic, strip or hash personally identifiable information before logging.
- Ensure API endpoints enforce role-based access control and respect API key scopes.

---

## Git & review expectations

- Use focused commits with descriptive messages (`<area>: <summary>` works well).
- Keep the working tree clean before finishing a task; run `git status` to confirm.
- Reference relevant docs or tests in PR descriptions. Summaries should mention user-facing changes and technical highlights.
- Follow the testing matrix above and note any skipped checks along with the reason.

---

Questions or assumptions that affect architecture should be recorded in the PR description so future contributors understand the decision trail.
