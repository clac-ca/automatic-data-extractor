# ADE test perf analysis
> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Establish current backend timing/failures baseline (e.g., `pytest --durations=20`) — latest run `pytest --durations=20` took 34.70s (all green; streaming dominates).
* [x] Cache engine/config builds for streaming tests (shared venv or wheel installs) so `_seed_real_configuration` in `apps/ade-api/tests/integration/runs/test_runs_router.py` stops rebuilding per test — now builds wheels once and installs from wheel per venv.
* [x] Reduce redundant streaming sheet-selection coverage (parameterize, mark slow, or move to lighter tests) while keeping one real E2E in `apps/ade-api/tests/integration/runs/test_runs_router.py` — consolidated sheet selection into a single multi-scenario test.
* [x] Add a fast-path identity seed for tests (lower-cost hashing or pre-hashed credentials) in `apps/ade-api/conftest.py::seed_identity` / `ade_api.features.auth.security.hash_password` to cut user router overhead — enabled via `ADE_TEST_FAST_HASH=1` in tests.
* [x] Fix `tests/unit/features/runs/test_runs_service.py::test_stream_run_emits_build_events_when_requested` mock signature to accept `workspace_id` kwarg on `fake_get_build_or_raise` — patched and test now passes.
* [x] Re-run targeted suite/`ade test` to confirm performance gains and clear current streaming 409/AttributeErrors — `pytest --durations=20` now green in 34.70s.

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] {{CHECK_TASK_1_SUMMARY}} — {{SHORT_STATUS_OR_COMMIT_REF}}`

---
## Commands observed
- `source .venv/bin/activate && ade test` — timed out at 120s (partial backend run shown).
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — completed in ~189.7s for 211 tests, surfaced slowest timings + failures.
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — completed in 80.47s, 1 failure (`test_stream_run_emits_build_events_when_requested`), slowest tests all in streaming runs (~10–11s each).
- `source .venv/bin/activate && cd apps/ade-api && pytest tests/unit/features/runs/test_runs_service.py::test_stream_run_emits_build_events_when_requested` — passed (fixed mock signature).
- `source .venv/bin/activate && cd apps/ade-api && pytest tests/integration/users/test_users_router.py::test_list_users_admin_success` — passed in 0.95s (fast-hash enabled).
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — passed in 56.31s; streaming tests still top at ~9–10s each.
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — passed in 45.36s after wheel caching; streaming tests now ~6–11s (first includes wheel build).
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — passed in 58.39s after adding reuse guard; streaming tests ~8–13s.
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — passed in 45.57s after consolidating sheet-selection tests; streaming tests ~7–11s.
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — passed in 38.19s after venv copy reuse; streaming tests ~1.7–13s (first still highest).
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — passed in 39.05s after warming runtime cache; streaming tests ~1.3–11.5s (setup for safe-mode run now pays the one-time cost).
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — passed in 34.70s after reusing config per workspace; streaming tests ~1–10.9s (one setup still highest).
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — passed in 34.70s after per-workspace config reuse and session warmup; safe-mode setup still pays the one-time cache build.

## Backend code observations (fresh pass)
- `apps/ade-api/tests/integration/runs/test_runs_router.py:304` `_seed_real_configuration` now installs from cached wheels, copies a cached venv when fingerprints match, and reuses the same configuration per workspace to avoid rebuilding; still writes config/build rows on first use.
- `BuildsService.prepare_build` and `VirtualEnvironmentBuilder` (`apps/ade-api/src/ade_api/features/builds/service.py`, `.../builder.py`) already reuse active builds when fingerprints match; tests approximate this via cached venv copy rather than calling the service reuse path.
- `apps/ade-api/conftest.py:155` `seed_identity` hashes six passwords with `hash_password` (scrypt N=2**14, r=8, p=1; see `ade_api/features/auth/security.py:49`). Fixture scope is function-level, so hashing repeats in every test needing identity data.
- Test env wiring (`apps/ade-api/conftest.py::_configure_database`) sets `ADE_PIP_CACHE_DIR`, `ADE_VENVS_DIR`, `ADE_CONFIGS_DIR` under a temp workspace, so wheel caching works.

## Findings (third-pass critical deep dive)
### Streaming runs (E2E) — primary bottleneck
- Latest baseline (34.70s total, all green): streaming tests in `apps/ade-api/tests/integration/runs/test_runs_router.py` still dominate, but cached venv + config reuse cut totals to ~1–10.9s. One safe-mode run setup still pays the one-time cache warmup:  
  - `test_stream_run_safe_mode` — 10.90s setup (pays warmup cost)  
  - `test_stream_run_processes_real_documents` — 1.20s call  
  - `test_stream_run_sheet_selection_variants` — 2.68s call (covers three sheet-selection cases in one test)  
  - `test_stream_run_processes_all_worksheets_when_unspecified` — 1.25s call
- Shared setup pattern: `_seed_real_configuration` installs from cached wheels, copies a cached venv when fingerprints match, and now reuses the same configuration per workspace; still creates per-workspace config/marker/build rows on first use. Warmup fixture builds the cached venv once per session.
- The actual engine run over CSV/XLSX input is cheap; remaining cost is the one-time cache warm and lightweight venv copy per workspace.

### User list test (secondary)
- `tests/integration/users/test_users_router.py::test_list_users_admin_success` took 1.90s with fast-hash enabled (down from 5.48s).
- Likely contributors:
  - Uses per-test `seed_identity` fixture (function scope) which hashes six passwords with scrypt (N=2^14) every time; scrypt dominates CPU and can add multiple seconds.
  - Test loops through paginated `/api/v1/users` calls, but with `page_size=100` it should be a single page; the HTTP loop itself should be cheap.
- Not a large share of total time, but scrypt-heavy seeding repeats across many tests, so dialing it down yields broad small wins.

### Current failures
- None — suite is green as of the latest `pytest --durations=20` run.

## Why it’s slow
- `_seed_real_configuration` copies a cached venv when fingerprints match and reuses the same configuration per workspace, but the first streaming setup (safe-mode run) still pays cache warm/build (~10.9s). Subsequent streaming runs are fast (~1–3s) but still create per-workspace config artifacts and copy venv.
- Streaming tests still write config/build rows; though we reuse the same workspace config, we could avoid re-copying the venv if we skip per-test config creation entirely or align tests to a single shared workspace/config.
- `seed_identity` hashes passwords with scrypt for six users on every test (function scope). Fast hash toggle shrinks this but identity-heavy paths still pay per-test hashing.

## Recommendations / next steps
- **Skip per-test config creation entirely:** Maintain a single shared workspace/config across streaming tests and reuse the cached venv directly to eliminate the remaining ~10.9s safe-mode warmup.
- **Trim/mark streaming scope:** With sheet selection consolidated, consider marking any remaining streaming variants as `slow` or moving option assertions to lighter tests, keeping only one real-engine E2E for default runs.
- **Consider stubbing the engine:** For API behaviors (sheet overrides, run metadata), use a fake engine runner that emits events quickly without venv creation. Reserve one true engine E2E for CI/nightly.
- **Tame password hashing in tests:** Already applied fast-hash toggle; consider session-scoping `seed_identity` if isolation allows, to shave another ~1–2s from identity-heavy paths.

## Do we need all four streaming tests as written?
- They all exercise the same run pipeline; differences are only input-sheet options. Maintaining four full E2E runs is likely unnecessary given the 20–30s setup cost each.
- Suggested split:
  - Keep one “happy path” streaming E2E validating real engine execution, artifact persistence, and logs.
  - Convert sheet-selection behaviors to lighter tests (unit/service with stubbed runner) or parameterize within a single streaming test that shares the built runtime.

## Candidate rewrites to make them faster
- Shared `_real_config` fixture (module/session scope) to build config/venv once; streaming tests consume it without rebuilding. Optionally pin a single `build_id` and skip `shutil.rmtree` if the marker matches.
- Introduce a fast runner stub for option coverage; mark the single real engine E2E as `slow` for default skips.
- Lower scrypt params under a test flag or use pre-hashed credentials so identity seeding is cheap; consider session-scoping `seed_identity` if test isolation allows.
