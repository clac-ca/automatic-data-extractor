# Work Package: Monorepo Structure Research and Recommendation

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Conduct deep, source-backed research on common monorepo structures used by real codebases (20+ references), analyze them against ADE constraints, and deliver a definitive, minimal-bespoke structure recommendation with a migration plan. The work includes online research, cloning sample repos for structure analysis, and synthesizing a comparative matrix.

### Scope

- In:
  - Identify 20+ representative open-source monorepos (Python + web, multi-service, polyglot).
  - Document real-world folder structures and packaging patterns.
  - Compare options vs ADE constraints (standalone API/worker, nginx web serving, single image, split containers, easy future repo split).
  - Produce a recommended structure and a step-by-step migration plan.
- Out:
  - Implementing the final migration (separate work package).
  - Changing runtime behavior beyond layout/packaging.

### Work Breakdown Structure (WBS)

1.0 Requirements and evaluation criteria
  1.1 Capture ADE constraints and priorities
    - [x] Confirm hard constraints (no shared Python modules between API/worker, separate CLI commands, nginx standard config, one image + split containers).
    - [x] Capture naming preferences (ade-web, ade-api, ade-worker).
    - [x] Define success criteria for "standard" (e.g., familiar tree, separate deployables, minimal bespoke tooling).
  1.2 Define evaluation rubric
    - [x] Define criteria: deployable boundaries, packaging isolation, dev UX, Docker/compose clarity, future repo split ease.

2.0 Research and source collection
  2.1 Online discovery (codebases + docs)
    - [x] Identify 20+ reference repos with different but common structures (e.g., backend/frontend split, apps/ services/ packages/).
    - [x] Capture primary sources (repo trees, READMEs) for each.
  2.2 Clone and inspect sample repos (temporary)
    - [x] Shallow clone a representative subset into `/tmp/ade-monorepo-research/<repo>`.
    - [x] Record top-level tree and per-service packaging artifacts.
    - [x] Clean up all temp clones after analysis.

3.0 Comparative analysis
  3.1 Build structure matrix
    - [x] Summarize each repo: layout, service boundaries, Python packaging strategy, JS app placement, docker/compose pattern.
  3.2 Evaluate against ADE rubric
    - [x] Score or categorize each structure vs ADE constraints.

4.0 Recommendation and migration plan
  4.1 Recommend 1-2 candidate layouts
    - [x] Provide a primary recommendation + a fallback option.
    - [x] Explain how each satisfies "standard" and "non-bespoke".
  4.2 Migration plan outline
    - [x] Provide staged migration steps (move folders, update CLI usage, update Docker/compose, update docs, update CI).
    - [x] List risks and mitigations (e.g., lockfile strategy, local dev ergonomics).

5.0 Validation and handoff
  5.1 Review with stakeholder
    - [x] Present recommendation and capture approval or edits.
  5.2 Final deliverable package
    - [x] Publish the matrix, recommendation, and migration plan in docs/workpackage notes.

### Open Questions

- None. Primary recommendation uses `apps/`; fallback option shows a `services/`-style layout for teams that prefer that naming.

---

## Acceptance Criteria

- At least 8 real-world repos surveyed with citations.
- A comparative matrix of structures is delivered.
- A definitive primary recommendation (plus one fallback) is documented.
- Migration plan includes concrete steps, risks, and verification.
- Temporary clones are removed after analysis.

---

## Definition of Done

- Workpackage checklist items are complete and up to date.
- Recommendation is clear enough to implement without further structure research.
