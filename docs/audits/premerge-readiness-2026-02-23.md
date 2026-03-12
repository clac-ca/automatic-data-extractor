# Pre-Merge Readiness Report (development -> main)

- Date: 2026-02-23
- Merge method: Rebase and merge
- Primary path attempted: direct `development -> main` PR
- Final path used: promotion branch fallback (`codex/dev-main-promotion-2026-02-23`)
- Final result: merged to `main`, release automation completed

## 0. Gate 0 prerequisite on development

- Cleanup branch: `codex/remove-obsolete-skills`
- PR: [#316](https://github.com/clac-ca/automatic-data-extractor/pull/316)
- Merge commit on `development`: `5c3382abb97ddbb7305c00596eae634946530f80`
- Scope landed:
  - deleted `.codex/skills/workpackage-executor/SKILL.md`
  - deleted `.codex/skills/workpackage-writer/SKILL.md`
  - deleted `.codex/skills/workpackage-writer/assets/workpackage.template.md`
  - deleted `.codex/skills/workpackage-writer/references/workpackage-guidelines.md`

## 1. Gate 1 baseline snapshot

- After Gate 0:
  - `git rev-list --left-right --count origin/main...origin/development` -> `7 29`
- Top `development`-only commits and `main`-only commits were captured before promotion.
- Merge window freeze was applied for promotion execution.

## 2. Gate 2 direct PR outcome

- Direct draft PR created: [#317](https://github.com/clac-ca/automatic-data-extractor/pull/317)
- GitHub mergeability result: conflicted (`mergeStateStatus: DIRTY`)
- Disposition: superseded and closed in favor of fallback path.

## 3. Gate 3 fallback promotion branch and conflict resolution

- Promotion branch created from `origin/development`:
  - `codex/dev-main-promotion-2026-02-23`
- Rebase command:
  - `git rebase origin/main`
- Conflict set handled during rebase (representative files):
  - `.github/workflows/ci-pr-gates.yaml`
  - `docs/reference/release-process.md`
  - `infra/README.md`
  - `infra/azure/**`
  - `docs/index.md` (delete/keep reconciliation)
- Resolution policy applied:
  - kept `development` functional/API/auth direction
  - preserved `main` release-process correctness in docs
  - kept infra/docs consistent with current CI/CD paths
  - regenerated derived artifacts where required; no conflict markers remained

## 4. Gate 4-5 readiness validation

### Required local command matrix

- `cd backend && uv run ade api lint` -> PASS
- `cd backend && uv run ade api types` -> PASS
- `cd backend && uv run ade api test` -> PASS (`223 passed`)
- `cd backend && uv run ade api test integration` -> PASS (`284 passed, 223 deselected`)
- `cd backend && uv run ade worker test` -> PASS (`17 passed`)
- `cd backend && uv run ade worker test integration` -> PASS (`14 passed, 17 deselected`)
- `cd backend && uv run ade web lint` -> PASS
- `cd backend && uv run ade web typecheck` -> PASS
- `cd backend && uv run ade web test` -> PASS (`76 files, 351 tests`)
- `cd backend && uv run ade test` -> PASS

### Manual smoke (`uv run ade dev --services api,worker,web`)

- First attempt exposed worker UV cache corruption in local env cache (not code regression).
- Retried with fresh cache dir (`ADE_WORKER_CACHE_DIR=/tmp/ade-worker-cache-smoke-20260223`) -> smoke PASS:
  - `/health` 200
  - `/api/v1/info` 200
  - `/api/v1/me/bootstrap` 200
  - document upload, publish run, process run all succeeded
  - output download 200
  - events download 200
  - SSE stream produced `ready` and `message` frames

## 5. Gate 6 merge execution

- Final promotion PR: [#318](https://github.com/clac-ca/automatic-data-extractor/pull/318)
- Required checks on PR head were green:
  - Backend Lint + API Types
  - Backend Unit Tests
  - Backend API Integration
  - Backend Worker Integration
  - Frontend Checks
- PR checks run URL: [PR Gates run 22327004787](https://github.com/clac-ca/automatic-data-extractor/actions/runs/22327004787)
- Merged via rebase at commit:
  - `2547c9586aad070c8dcb748633edba74df5d43e0`

## 6. Gate 7 post-merge release automation verification

- Main-branch Release Please run after promotion merge:
  - [Run 22327343293](https://github.com/clac-ca/automatic-data-extractor/actions/runs/22327343293) -> success
- Release PR opened and merged:
  - [#319](https://github.com/clac-ca/automatic-data-extractor/pull/319)
  - merge commit `f70fc5089df720bfa13d2c46921eb13099655c0c`
- Release Please run on release commit:
  - [Run 22327515604](https://github.com/clac-ca/automatic-data-extractor/actions/runs/22327515604) -> success
- Docker image publication:
  - [Run 22327514038 (push)](https://github.com/clac-ca/automatic-data-extractor/actions/runs/22327514038) -> success
  - [Run 22327532536 (release tag v1.9.0)](https://github.com/clac-ca/automatic-data-extractor/actions/runs/22327532536) -> success
- Published release:
  - [v1.9.0](https://github.com/clac-ca/automatic-data-extractor/releases/tag/v1.9.0)
  - target commit: `f70fc5089df720bfa13d2c46921eb13099655c0c`

## 7. Final SHAs and branch state

- `origin/development`: `5c3382abb97ddbb7305c00596eae634946530f80`
- `origin/main`: `f70fc5089df720bfa13d2c46921eb13099655c0c` (`v1.9.0`)
- Note: after rebase promotion, `origin/main...origin/development` remains diverged by commit identity (`27 29`) as expected for rebased history.

## Final Decision

- Go/No-Go: GO
- Merge result: completed (`development` promoted to `main` through fallback promotion branch, rebase merge, all required checks green).
- Release result: completed (`v1.9.0` published and docker publish workflows successful).
