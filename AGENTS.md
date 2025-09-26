The automatic-data-extractor (ADE) aims to transform semi-structured spreadsheets and PDFs into clean, structured tables using deterministic, revision-controlled logic.  This is the only AGENTS.md file in this repo.  Pay close attention to it.

AGENTS.md is provided to every Codex AI agent run; it explains how agents should interpret user instructions and interact with the repository.

All agent-facing playbooks now live under `agents/` so the repository root can stay focused on human-facing docs and source.

## Repository layout (planned)
```
.
├─ README.md
├─ AGENTS.md
├─ agents/
│  ├─ ADE_GLOSSARY.md
│  ├─ BACKEND_REWRITE_PLAN.md
│  ├─ BEST_PRACTICE_VIOLATIONS.md
│  ├─ DOCUMENTATION_REWRITE_PLAN.md
│  ├─ FRONTEND_DESIGN.md
│  ├─ PREVIOUS_TASK.md
│  ├─ code_review_instructions.md
│  └─ fastapi-best-practices.md
├─ backend/
│  ├─ app/            # FastAPI entrypoint, routes, schemas, services
│  ├─ data/           # Gitignored runtime artefacts (database, documents, caches)
│  └─ tests/
├─ frontend/
│  ├─ src/            # Pages, components, API client wrappers
│  └─ tests/
├─ examples/          # Sample documents used in testing
```

---

**Priorities (in strict order)**

1. **Clarity** – Favor solutions that are simple, readable, and easy to debug. Clear code prevents silent errors and makes future changes safe.
2. **Pragmatic Optimization** – Improve performance where it delivers real value, but only if the solution remains maintainable. Skip complex edge-case handling that is unlikely to occur in practice.
3. **Throughput** – Make the system fast and efficient once clarity and pragmatic optimization are satisfied. Speed is valuable, but never at the expense of reliability or simplicity.

**Baseline Assumptions**

* **Scale** – Built for modest, internal line-of-business usage (not internet-scale with millions of users).
* **Style** – Use clear names, minimal abstractions, and deterministic functions. Code should be straightforward to read and audit.
* **Trade-offs** – Prefer simple, reliable solutions over clever but fragile ones. Choose slower but clearer implementations if performance gains would add disproportionate complexity.

---

## Modes of Operation

### Default Mode — Direct User Instructions

**Trigger:** The user provides instructions without referencing a file under `agents/`.

**How to proceed:**
1. Follow the user's latest instructions exactly.
2. Use the priorities and baseline assumptions above to guide decisions.
3. Ask for clarification only when the instructions conflict or are ambiguous.

### Work Package Mode — agents/* Playbooks

**Trigger:** The user mentions one or more work packages in `agents/` (for example `agents/CURRENT_TASK.md` or `agents/DOCUMENTATION_REWRITE_PLAN.md`).

**How to proceed:**
1. Read every referenced work package in `agents/` before making changes.
2. Execute only the scope defined in each work package with production-ready code (no scope creep).
3. Add or update deterministic tests and fixtures in `examples/` when relevant.
4. Run the appropriate quality gates (pytest, ruff, mypy, npm test/lint/typecheck).
5. Update each referenced work package with the current status and any next steps that remain. When working from `agents/CURRENT_TASK.md`, rotate it to `agents/PREVIOUS_TASK.md` and draft the next plan.

---

## Dependencies

Keep the dependency footprint small. ADE should only add a library when it is a **well-maintained, widely used dependency** that makes the code significantly clearer, safer, or simpler. If the same result can be achieved with a few lines of straightforward native code (`pathlib`, `uuid`, `json`, etc.), prefer the standard library.

**Rule of thumb**  
- *Native if simple* → a few clear lines.  
- *Library if complex* → edge-case heavy tasks (e.g., date parsing, schema validation, async HTTP).  

**Process**  
If the current task can only be completed after a new dependency is added:  
1. Add it to `pyproject.toml` with pinned version(s).  
2. End the current task with a PR updating only that file.  
3. Note in the PR that the dependency was required for the task.  
4. Resume development in the next PR once merged.

This ensures dependency decisions are explicit, auditable, and reversible.

## Testing

ADE uses **pytest** as the primary test runner, with **pytest-asyncio** for async tests.  
Tests live under `backend/tests/` and follow the `test_*.py` / `test_*` convention.  

Key tools:
- **pytest** → run all unit and integration tests.
- **pytest-asyncio** → allows `async def` tests (`asyncio_mode="auto"` enabled).
- **pytest-cov** → optional coverage reports.
- **Ruff** → enforces code style and catches common errors.
- **MyPy** → type checking with Pydantic plugin.

---

## Guiding Principle

**Consistency, clarity, and pragmatism beat cleverness.**
Structure your code so every developer knows where things live, write routes and dependencies in the simplest correct form, and lean on Pydantic and FastAPI’s patterns rather than inventing your own abstractions. Prefer async where it matters, validate at the edges, and use tools (Ruff, Alembic, type checking) to enforce consistency so the team can focus on business logic instead of style debates.