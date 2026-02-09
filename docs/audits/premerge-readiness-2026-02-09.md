# Pre-Merge Readiness Report (development -> main)

- Branch: `codex/premerge-readiness-2026-02-09`
- Date: 2026-02-09
- Scope: strict-green pre-merge hardening only (no actual merge execution)
- Synced to latest `development`: `f6c2b5322db9b33bd6c6c5d8bcbe08edd5c8616d`

## Evidence Log

### 0. Setup
- Created dedicated readiness branch.
- This report records blockers, fixes, command outputs, and final go/no-go.

### 1. Implemented fixes
- Integration collection collision resolved by renaming duplicate basename test module:
  - `backend/tests/api/integration/features/documents/test_service.py` -> `backend/tests/api/integration/features/documents/test_documents_service.py`
- Config import flush-failure behavior fixed to preserve cleanup and return server error contract:
  - `backend/src/ade_api/features/configs/service.py`
  - `backend/src/ade_api/features/configs/endpoints/configurations.py`
- Dev/auth-disabled bootstrap now returns real workspace entries and meaningful preferred workspace:
  - `backend/src/ade_api/features/me/service.py`
  - covered by `backend/tests/api/integration/auth/test_auth_disabled_mode.py`
- Workspace profile create/list/get consistency for global-admin context:
  - `backend/src/ade_api/features/workspaces/service.py`
  - covered by `backend/tests/api/integration/auth/test_workspaces_profile_consistency.py`
- SQLAlchemy logs reduced by default in dev:
  - `backend/src/ade_api/common/logging.py`
- Frontend config listing now sends explicit status filters:
  - `frontend/src/api/configurations/api.ts`
  - `frontend/src/pages/Workspace/hooks/configurations/useConfigurationsQuery.ts`
  - `frontend/src/pages/Workspace/hooks/configurations/keys.ts`
  - `frontend/src/api/configurations/__tests__/api.test.ts`
- Additional regression/hardening fixes discovered during matrix runs:
  - Preserve non-500 HTTPException detail payloads (keep 500 opaque): `backend/src/ade_api/common/exceptions.py`
  - Avoid cross-session SQLAlchemy attachment in document comments: `backend/src/ade_api/features/documents/service.py`
  - Stabilize auth-session assertions against shared-state noise: `backend/tests/api/integration/auth/test_auth_sessions.py`
  - Align original-download integration test with storage versioning mode `off`: `backend/tests/api/integration/documents/test_documents_download.py`
  - Stabilize flaky SSO setup tests under full-suite load: `frontend/src/features/sso-setup/__tests__/SsoSetupFlow.test.tsx`

### 2. Strict gate command results (local)
- `cd backend && uv run ade api lint` -> **FAIL** (mypy 455 errors in 75 files)
- `cd backend && uv run ade api test` -> **PASS**
- `cd backend && uv run ade api test integration` -> **PASS** (`238 passed, 175 deselected`)
- `cd backend && uv run ade worker test` -> **PASS**
- `cd backend && uv run ade worker test integration` -> **PASS**
- `cd backend && uv run ade web lint` -> **PASS**
- `cd backend && uv run ade web typecheck` -> **PASS**
- `cd backend && uv run ade web test` -> **PASS** (`65 files, 308 tests`)
- `cd backend && uv run ade test` -> **PASS**
- Extra validation: `cd backend && uv run ade api types` -> **PASS**
- Flaky SSO file reruns (required): both consecutive reruns passed
  - `frontend/src/features/sso-setup/__tests__/SsoSetupFlow.test.tsx` (2/2 pass)

### 3. Manual live-stack smoke (`uv run ade dev --services api,worker,web`)
- Stack booted successfully:
  - API: `http://localhost:31040`
  - Web: `http://localhost:30040`
  - Worker: running and claiming runs
- Health/info:
  - `GET /health` -> 200
  - `GET /api/v1/info` -> 200
- Bootstrap/workspace consistency:
  - `GET /api/v1/me/bootstrap` returned non-empty workspace list and non-null `preferred_workspace_id`
  - Workspace create/list/get were consistent for new workspace `019c41d7-eb1b-7591-98d3-52f8ccdc76c5` (`profile` shape consistent across all)
- Document/config/run lifecycle:
  - Uploaded document `019c41d7-eb8f-7e5d-bede-4c3b17a4d118`
  - Created draft config `019c41d7-ec40-7b0d-998e-ed7b1918852e`
  - Invalid process run without input returned expected 422 contract
  - Publish run `31564792-dc6a-420f-8782-14161baa85cd` -> terminal `succeeded`
  - Process run `ff84a3c7-253e-43a3-b1a8-1b3d7d35dab8` -> terminal `succeeded`
  - Output download -> 200 (`/runs/{id}/output/download`)
  - Events download -> 200 (`/runs/{id}/events/download`)
  - Events SSE stream -> ready + message frames observed (`/runs/{id}/events/stream`)
- Runtime log review:
  - No unexplained API 5xx during smoke scenarios
  - SQL statement spam not observed
  - Azure SDK HTTP logging remains verbose (operational noise source, but not SQL noise)

### 4. CI gate coverage
- Added strict PR gate workflow: `.github/workflows/ci-pr-gates.yaml`
- Includes postgres + azurite services and required command matrix:
  - `ade api lint`, `ade api test`, `ade api test integration`
  - `ade worker test`, `ade worker test integration`
  - `ade api types`, `ade web lint`, `ade web typecheck`, `ade web test`, `ade test`

### 5. Merge rehearsal (no merge to main)
- Temporary rehearsal worktree from `origin/main` merged with `origin/development` using `--no-commit`
- Result: **clean merge**, `CONFLICT_COUNT=0`
- Rehearsal merge log: `Automatic merge went well; stopped before committing as requested`

### 6. Remaining blockers / risks
- **Primary blocker:** `uv run ade api lint` still fails.
  - Current branch: mypy reports `455` errors.
  - Clean `origin/development` comparison:
    - `uv run python -m mypy src/ade_api` -> `408` errors.
    - `uv run ade api lint` -> fails earlier at ruff with `129` findings.
- Interpretation:
  - API lint debt is pre-existing on `development`.
  - This branch improved runtime/test behavior and integration correctness, but strict lint gate remains red.

## Final Recommendation
- **NO-GO** for merge under strict-green policy until API lint policy debt is resolved (or gate policy is explicitly adjusted by release owner).
- All other validated gates and manual smoke scenarios are green.
