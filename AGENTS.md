The automatic-data-extractor (ADE) aims to transform semi-structured spreadsheets and PDFs into clean, structured tables using deterministic, revision-controlled logic.  This is the only AGENTS.md file in this repo.  Pay close attention to it.

## Repository layout (planned)
```
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ AGENTS.md
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

### 1. Task Implementation

**When**: default mode.
**Goal**: execute the active plan detailed in `CURRENT_TASK.md`, and update the `CURRENT_TASK.md` for the next run. No scope creep.
**Steps**:

1. Read `CURRENT_TASK.md` (source of truth).
2. Implement only the defined scope with production-ready code.
3. Add/update tests and deterministic fixtures in `examples/`.
4. Run quality gates (pytest, ruff, mypy, npm test/lint/typecheck).
5. Update docs if architecture or terminology changes.
6. Open a focused PR with summary, assumptions, follow-ups.
7. Rotate: `CURRENT_TASK.md → PREVIOUS_TASK.md` and draft next plan.

**Acceptance criteria**:

* CI checks pass.
* Matches `CURRENT_TASK.md` scope exactly.
* Deterministic behavior (no I/O or randomness in extraction).

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