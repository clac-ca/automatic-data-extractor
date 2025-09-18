The automatic-data-extractor (ADE) aims to transform semi-structured spreadsheets and PDFs into clean, structured tables using deterministic, revision-controlled logic.

## Repository layout (planned)
```
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ AGENTS.md
├─ backend/
│  ├─ app/            # FastAPI entrypoint, routes, schemas, services
│  ├─ processor/      # Table detection, column mapping, validation logic
│  └─ tests/
├─ frontend/
│  ├─ src/            # Pages, components, API client wrappers
│  └─ tests/
├─ infra/
│  ├─ Dockerfile
│  └─ docker-compose.yaml
├─ examples/          # Sample documents used in testing
├─ runs/              # Example job outputs
└─ var/
   ├─ documents/      # Uploaded files (gitignored)
   └─ ade.sqlite      # Local development database (gitignored)
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

### 2. Code Review

**When**: explicit request for “review” or code shown without a task.
**Goal**: critique and propose minimal, ADE-aligned rewrites.

**Checklist**:

* **Correctness** – invariants, nulls, uniqueness, race conditions, timezones.
* **Clarity** – remove dead code, avoid needless abstractions.
* **Maintainability** – small functions, explicit invariants, clear names.
* **Consistency** – FastAPI, Pydantic v2, SQLAlchemy patterns.
* **Performance (contextual)** – avoid N+1 queries, repeated serialization.
* **Security** – input validation, safe defaults, no sensitive leaks.
* **Operational** – logging signal/noise, DB constraints, migrations.
* **Testability** – seams for fixtures, return values > side effects.

**Outputs**: issue list, targeted rewrites, test gaps, ops notes.

---

## Guiding Principle

**When in doubt → choose simple, auditable solutions.**
Always leave clear notes for the next contributor or agent.
