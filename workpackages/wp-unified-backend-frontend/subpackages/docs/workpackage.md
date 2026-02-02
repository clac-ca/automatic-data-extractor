# Work Package: Documentation Rewrite

Guiding Principle:
Make ADE a clean, unified, and easily operable system with one backend distribution, clear shared infrastructure, and a simple default workflow that still allows each service to run independently.


> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Rewrite documentation from scratch to reflect the unified backend layout, the new CLI (`ade`), and current deployment/development workflows. Replace outdated docs rather than modifying them in place.

Proposed documentation IA (minimal core):

```
docs/
  index.md
  getting-started/
    quickstart.md
    install.md
    first-run.md
  guides/
    developer.md
    deployment.md
  reference/
    cli.md
    env-vars.md
  troubleshooting/
    common-issues.md
```

Rationale (reader-first):

- Clear entry points: quickstart for new users, guides for core workflows, reference for commands.
- Progressive disclosure: start with outcomes, then just enough detail for common paths.
- Keep it lean: fewer pages, lower maintenance, easier to expand later.

### Scope

- In:
  - New documentation information architecture (IA).
  - Fresh getting started, development, deployment, and operations guides.
  - Update references to paths, commands, and Docker usage.
- Out:
  - Historical migration guides for prior layouts.
  - Deep API reference (beyond existing OpenAPI).

### Work Breakdown Structure (WBS)

1.0 Documentation plan
  1.1 Define new IA
    - [ ] Confirm the target IA above and adjust if needed.
    - [ ] Identify obsolete docs to remove/archive.

2.0 Author new docs
  2.1 Getting started
    - [ ] Fresh setup steps for backend + frontend.
    - [ ] New CLI overview and common workflows.
  2.2 Development
    - [ ] Dev environment and testing workflows.
    - [ ] Backend vs frontend responsibilities and where to work.
  2.3 Deployment
    - [ ] Single-image model and service composition options.
    - [ ] Docker compose examples (api+web, worker-only, all-in-one).
  2.4 Operations
    - [ ] Migration steps and database initialization.
    - [ ] Logs, troubleshooting, and common fixes.

3.0 Cleanup + validation
  3.1 Remove stale content
    - [ ] Remove or archive obsolete docs files.
  3.2 Check references
    - [ ] Ensure all links and command examples match the new layout.

### Open Questions

- Which existing docs (if any) should be retained as historical references?

---

## Acceptance Criteria

- Docs reflect the new `backend/` + `frontend/` layout.
- All CLI examples use `ade` and the updated commands.
- Deployment docs describe the single-image model with flexible service composition.

---

## Definition of Done

- New docs pass a sanity review: no broken links, no stale paths, and all commands runnable.
