# Access Management Documentation Final Resting Place Plan

Date: February 12, 2026

## Goal

Promote the access-management redesign package into first-class, canonical ADE documentation that fits existing section taxonomy and style conventions.

This plan answers:

1. What content from `docs/access-management-redesign` should be kept.
2. Where each kept artifact should live long-term.
3. How to integrate it into the existing docs look and feel.

## Canonical Destination Strategy

Use existing documentation taxonomy, not a parallel standalone island:

1. `docs/explanation/*` for system concepts and model rationale
2. `docs/how-to/*` for operator/admin tasks
3. `docs/reference/*` for stable contracts, matrices, and diagrams
4. `docs/reference/api/*` for endpoint-level contracts
5. `docs/troubleshooting/*` for incident and failure handling
6. `docs/standards/*` for maintenance rules and required test/doc updates

`docs/access-management-redesign` becomes a transition/decision package, then an archived provenance package.

## Final Resting Place (Target Tree)

```text
docs/
  explanation/
    access-management-model.md                       (new)
  how-to/
    manage-users-and-access.md                       (rewrite)
    auth-operations.md                               (update)
  reference/
    access/
      README.md                                      (new)
      permission-matrix.md                           (promote)
      endpoint-matrix.md                             (promote)
      test-matrix.md                                 (promote)
      diagrams/
        erd.mmd                                      (promote)
        sequence-diagrams.mmd                        (promote)
      implementation-notes.md                        (new, concise)
    api/
      access-management.md                           (new)
      authentication.md                              (update)
      workspaces.md                                  (update)
    api-capability-map.md                            (update)
    auth-architecture.md                             (update)
  troubleshooting/
    access-management-incident-runbook.md            (new)
  audits/
    access-management-redesign-2026Q1.md             (new, concise archive index)
```

## Keep / Promote / Archive Matrix

| Source in redesign package | Decision | Final resting place |
|---|---|---|
| `reference/erd.mmd` | keep (authoritative model artifact) | `docs/reference/access/diagrams/erd.mmd` |
| `reference/sequence-diagrams.mmd` | keep (authoritative flow artifact) | `docs/reference/access/diagrams/sequence-diagrams.mmd` |
| `reference/permission-matrix.md` | keep + promote | `docs/reference/access/permission-matrix.md` |
| `reference/endpoint-matrix.md` | keep + promote | `docs/reference/access/endpoint-matrix.md` and summarized in `docs/reference/api/access-management.md` |
| `reference/access-test-matrix.md` | keep + promote | `docs/reference/access/test-matrix.md` |
| `reference/bulk-user-acceptance-matrix.md` | keep as specialized appendix | `docs/reference/access/test-matrix.md` appendix or `docs/reference/access/batch-acceptance-matrix.md` |
| `reference/code-map.md` | keep as implementation note, reduce size | `docs/reference/access/implementation-notes.md` |
| `recommendations/target-model.md` | merge into canonical explanation/reference pages | `docs/explanation/access-management-model.md` + `docs/reference/access/*` |
| `recommendations/api-routes-hard-cutover.md` | merge | `docs/reference/api/access-management.md` |
| `recommendations/data-model-and-migrations.md` | merge | `docs/reference/access/implementation-notes.md` |
| `recommendations/authn-sso-group-sync-spec.md` | merge | `docs/how-to/auth-operations.md` + `docs/reference/auth-architecture.md` |
| `recommendations/provisioning-mode-spec.md` | merge | `docs/how-to/auth-operations.md` + `docs/reference/auth-architecture.md` |
| `recommendations/scim-adoption-recommendation.md` | merge | `docs/reference/api/access-management.md` (SCIM section) + `docs/how-to/auth-operations.md` |
| `recommendations/bulk-user-endpoint-plan.md` | merge | `docs/reference/api/access-management.md` + `docs/reference/access/test-matrix.md` |
| `recommendations/frontend-*.md` | keep as delivery workpackage during execution; archive after rollout | `docs/audits/access-management-redesign-2026Q1.md` links |
| `analysis/*` and `research/*` | keep as provenance evidence; do not duplicate in canonical docs | archive index links in `docs/audits/access-management-redesign-2026Q1.md` |

## Stale Canonical Pages to Update During Consolidation

1. `docs/how-to/manage-users-and-access.md`
   - currently CLI and role flows are legacy-shaped and need rewrite to principal/assignment model.
2. `docs/reference/api/workspaces.md`
   - currently documents removed `/members` endpoints.
3. `docs/reference/api-capability-map.md`
   - update route casing and capability pointers (`/roleAssignments`, access endpoints).
4. `docs/reference/auth-architecture.md`
   - replace boolean JIT framing with provisioning mode model (`disabled|jit|scim`), and sign-in hydration behavior.
5. `docs/how-to/auth-operations.md`
   - align with final provisioning and group-sync behavior.
6. `docs/reference/api/README.md`
   - add `Access Management API` page link.

## Look-and-Feel Integration Rules

Follow `docs/standards/documentation-style-guide.md` and keep consistent page shape:

1. Explanation pages:
   - `Purpose`
   - core model narrative
   - glossary/definitions
   - links to how-to and reference pages
2. How-to pages:
   - `Goal`
   - `Before You Start`
   - `Steps`
   - `Verify`
   - `If Something Fails`
3. Reference pages:
   - `Purpose`
   - definitions (if needed)
   - stable tables/matrices
   - examples and related links
4. API reference pages:
   - endpoint matrix with `method/path/auth/status/request/response/errors`
   - core endpoint details
   - error handling
   - related how-to links

## Execution Phases

## Phase 1: Canonical skeleton and navigation

1. Create `docs/reference/access/README.md` and `docs/reference/api/access-management.md`.
2. Update nav/index files:
   - `docs/README.md`
   - `docs/reference/README.md`
   - `docs/reference/api/README.md`
3. Add placeholders with correct style-guide page structure.

## Phase 2: Migrate authoritative artifacts

1. Promote matrices and diagrams:
   - permission matrix
   - endpoint matrix
   - test matrix
   - ERD and sequence diagrams
2. Ensure links between reference pages are bi-directional.

## Phase 3: Rewrite operator and architecture pages

1. Rewrite `docs/how-to/manage-users-and-access.md`.
2. Update `docs/how-to/auth-operations.md`.
3. Update `docs/reference/auth-architecture.md`.
4. Update `docs/reference/api/workspaces.md` and capability map.

## Phase 4: Archive redesign package cleanly

1. Add `docs/audits/access-management-redesign-2026Q1.md`:
   - what was decided
   - where canonical docs now live
   - evidence links back to redesign research/analysis
2. Update `docs/access-management-redesign/README.md`:
   - mark as historical design package
   - point to canonical final pages
3. Keep redesign files for provenance; do not treat them as live operational docs.

## Quality Gates

Run docs checks at each phase:

```bash
DOCS_FILES="$(find docs -type f -name '*.md' ! -path 'docs/audits/*' -print)"
npx --yes markdownlint-cli2 --config .docs.markdownlint-cli2.jsonc $DOCS_FILES
python3 scripts/docs/check_api_docs_coverage.py
```

Optional link check:

```bash
FILES="$(find docs -type f -name '*.md' -print) README.md CONTRIBUTING.md $(find backend -mindepth 2 -maxdepth 2 -name README.md -print)"
lychee --no-progress $FILES
```

## Definition of Done

1. Access-management canonical docs live under standard `explanation/how-to/reference/reference-api/troubleshooting` sections.
2. Matrices and diagrams are preserved and discoverable from `docs/reference/access/README.md`.
3. Legacy/stale route docs are corrected to hard-cutover contracts.
4. `docs/access-management-redesign` is clearly marked as historical/provenance, not operational source of truth.
5. Docs navigation (`docs/README.md` and section READMEs) exposes the new canonical access docs clearly.

